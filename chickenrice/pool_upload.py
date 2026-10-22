#!/usr/bin/env python3
# 字幕池上传：把生成的中文成品字幕上传到公共字幕池（subtitle-modal-web 同款接口）。
#
# 接口规范（据 jzdxjk/subtitle-modal-web 文档）：
#   Base: https://chickenrice-subtitle-pool.jzdxjk.workers.dev
#   POST /api/v1/subtitles  multipart 字段：code（番号）、format、language=zh、file
#   鉴权：Authorization: Bearer <上传密钥>；请求头 Idempotency-Key 传文件 sha256
#   GET  /api/v1/stats      无鉴权，查池内总数
# 本地过滤（与服务端一致，先筛掉免得白跑）：仅 srt/ass/ssa、≤2MiB、合法 UTF-8、
#   至少 1 个汉字、假名占（汉字+假名）比例 >0.20 判为日文字幕跳过；
#   按内容 sha256 去重（本地台账记录传过的，不再重复传）。
# 密钥不写死在脚本里：环境变量 POOL_UPLOAD_KEY，或 --key-file 指定存放密钥的文件。
# 上传是显式动作：本脚本不会被其他脚本自动调用，跑一次传一次。
import argparse, hashlib, json, os, re, sys, time
import urllib.request, urllib.error

BASE = "https://chickenrice-subtitle-pool.jzdxjk.workers.dev"
UA = "chickenrice-pool-uploader/1.0"
MAX_SIZE = 2 * 1024 * 1024
OK_EXTS = {".srt", ".ass", ".ssa"}
DEFAULT_LEDGER = os.path.expanduser("~/.chickenrice-pool-uploaded.json")

CODE_PATTERNS = [
    re.compile(r"FC2(?:-PPV)?-\d{6,7}", re.I),
    re.compile(r"\b[A-Z]{2,6}-\d{3,5}\b", re.I),
    re.compile(r"\b[a-z]{3,}\d{3,}\b", re.I),  # abc123 式
]

def extract_code(stem):
    for pat in CODE_PATTERNS:
        m = pat.search(stem)
        if m:
            return m.group(0).upper()
    return None

def text_stats(text):
    kanji = kana = 0
    for ch in text:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            kanji += 1
        elif 0x3040 <= o <= 0x30FF:
            kana += 1
    return kanji, kana

def check_file(path, code_override=""):
    """返回 (ok, info)；ok=False 时 info['reason'] 说明跳过原因。"""
    ext = os.path.splitext(path)[1].lower()
    if ext not in OK_EXTS:
        return False, {"reason": f"格式不支持 {ext or '(无扩展名)'}"}
    data = open(path, "rb").read()
    if len(data) > MAX_SIZE:
        return False, {"reason": f"文件过大 {len(data)} > {MAX_SIZE}"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False, {"reason": "非合法 UTF-8"}
    kanji, kana = text_stats(text)
    if kanji == 0:
        return False, {"reason": "无汉字"}
    ratio = kana / (kanji + kana) if (kanji + kana) else 0.0
    if ratio > 0.20:
        return False, {"reason": f"判为日文字幕（假名占比 {ratio:.2f}）"}
    code = code_override or extract_code(os.path.splitext(os.path.basename(path))[0])
    if not code:
        return False, {"reason": "文件名提取不到番号（可用 --code 指定）"}
    return True, {"code": code, "format": ext.lstrip("."),
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "size": len(data), "data": data}

def load_ledger(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_ledger(path, ledger):
    tmp = path + ".tmp"
    json.dump(ledger, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)

def multipart_body(fields, filename, data):
    boundary = "----poolupload" + hashlib.md5(str(time.time()).encode()).hexdigest()
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return boundary, b"".join(parts)

def upload_one(info, filename, key):
    """返回 (outcome, detail)：outcome ∈ created/duplicate/removed/failed/abort/retry-exhausted"""
    boundary, body = multipart_body(
        {"code": info["code"], "format": info["format"], "language": "zh"},
        filename, info["data"])
    req = urllib.request.Request(BASE + "/api/v1/subtitles", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Idempotency-Key", info["sha256"])
    req.add_header("User-Agent", UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read().decode("utf-8", "replace")
                return ("created", f"HTTP {resp.status} {payload[:120]}")
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", "replace")[:200] if e.fp else ""
            if e.code in (401, 403):
                return ("abort", f"HTTP {e.code} 密钥无效，整批中止：{payload}")
            if e.code == 429:
                return ("abort", f"HTTP 429 限流（Retry-After: {e.headers.get('Retry-After')}），整批中止")
            if e.code == 410:
                return ("removed", "HTTP 410 内容已下架，跳过")
            if 500 <= e.code < 600 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return ("failed", f"HTTP {e.code} {payload}")
        except Exception as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return ("failed", f"{type(e).__name__}: {e}")
    return ("failed", "重试耗尽")

def pool_stats():
    req = urllib.request.Request(BASE + "/api/v1/stats")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    ap = argparse.ArgumentParser(description="上传中文字幕到公共字幕池")
    ap.add_argument("paths", nargs="*", help="字幕文件路径")
    ap.add_argument("--dir", default="", help="扫描目录（与 paths 可同时给）")
    ap.add_argument("--code", default="", help="统一指定番号（覆盖文件名提取）")
    ap.add_argument("--key-file", default="", help="存放上传密钥的文件（或用环境变量 POOL_UPLOAD_KEY）")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER, help="去重台账路径")
    ap.add_argument("--dry-run", action="store_true", help="只做本地过滤与去重检查，不上传")
    ap.add_argument("--stats", action="store_true", help="只查询池内总数")
    a = ap.parse_args()

    if a.stats:
        print("池内字幕总数:", pool_stats().get("subtitle_count"))
        return 0

    files = list(a.paths)
    if a.dir:
        for name in sorted(os.listdir(a.dir)):
            p = os.path.join(a.dir, name)
            if os.path.isfile(p):
                files.append(p)
    if not files:
        print("没有给出任何文件（paths 或 --dir）")
        return 2

    key = os.environ.get("POOL_UPLOAD_KEY", "")
    if a.key_file:
        key = open(a.key_file, encoding="utf-8").read().strip()
    if not a.dry_run and not key:
        print("缺上传密钥：设置环境变量 POOL_UPLOAD_KEY 或 --key-file（--dry-run 可免）")
        return 2

    ledger = load_ledger(a.ledger)
    n_up = n_skip = n_fail = 0
    for path in files:
        name = os.path.basename(path)
        ok, info = check_file(path, a.code)
        if not ok:
            print(f"跳过 {name}：{info['reason']}")
            n_skip += 1
            continue
        if info["sha256"] in ledger:
            print(f"跳过 {name}：已上传过（台账记录）")
            n_skip += 1
            continue
        if a.dry_run:
            print(f"可传 {name}：番号 {info['code']}，{info['size']} 字节，sha256 {info['sha256'][:12]}…")
            n_up += 1
            continue
        outcome, detail = upload_one(info, name, key)
        print(f"{outcome} {name}（{info['code']}）：{detail}")
        if outcome in ("created", "duplicate"):
            ledger[info["sha256"]] = {"code": info["code"], "file": name,
                                       "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                       "status": outcome}
            save_ledger(a.ledger, ledger)
            n_up += 1
        elif outcome == "removed":
            n_skip += 1
        elif outcome == "abort":
            print("中止后续上传。")
            n_fail += 1
            break
        else:
            n_fail += 1
    print(f"汇总：成功 {n_up}，跳过 {n_skip}，失败 {n_fail}")
    return 0 if n_fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
