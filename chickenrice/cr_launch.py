# 在 Colab 运行时里执行（colab exec --env TASK=translate|transcribe -f cr_launch.py）——立即返回
# 职责：把 infer.py 以脱离 kernel 的后台进程启动，日志与完成标记写到 /content/out_<task>/
# 输入文件：可用 --env INPUT_FILE=/content/input/xxx.mp3 指定（视频/音频均可，音频如 mp3/m4a/flac/wav）；
# 不指定时自动取 /content/input/ 里的第一个文件。后缀过滤默认取输入文件的扩展名，可用 AUDIO_SUFFIX 覆盖。
import os, subprocess, textwrap, glob
os.environ.setdefault("MPLBACKEND", "Agg")
TASK = os.environ.get("TASK", "translate")
MODEL = os.environ.get("MODEL", {"translate": "hainanji", "transcribe": "ja15b"}[TASK])
TAG = os.environ.get("TAG", "")
OUT = f"/content/out_{TASK}" + (f"_{TAG}" if TAG else "")
INPUT_FILE = os.environ.get("INPUT_FILE", "")
if not INPUT_FILE:
    cands = sorted(glob.glob("/content/input/*"))
    assert cands, "no input file: set INPUT_FILE or put a file in /content/input/"
    INPUT_FILE = cands[0]
AUDIO_SUFFIX = os.environ.get("AUDIO_SUFFIX", "") or \
    os.path.splitext(INPUT_FILE)[1].lstrip(".").lower() or "mp4"
os.makedirs(OUT, exist_ok=True)
for stale in ("DONE", "FAILED"):
    p = os.path.join(OUT, stale)
    if os.path.exists(p):
        os.remove(p)

worker = textwrap.dedent(f'''
    import subprocess, os, glob
    OUT = "{OUT}"
    LOG = open(os.path.join(OUT, "run.log"), "a", buffering=1)
    nv = sorted(glob.glob("/usr/local/lib/python3.*/dist-packages/nvidia/*/lib"))
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(nv) + ":" + env.get("LD_LIBRARY_PATH", "")
    cmd = ["python3", "infer.py",
           "--model_name_or_path", "models/{MODEL}",
           "--device", "cuda", "--compute_type", "float16",
           "--task", "{TASK}",
           "--audio_suffixes", "{AUDIO_SUFFIX}", "--sub_formats", "srt",
           "--output_dir", OUT, "--overwrite",
           "--log_level", "INFO",
           "{INPUT_FILE}"]
    print("+", " ".join(cmd), file=LOG)
    r = subprocess.run(cmd, cwd="/content/chickenrice", stdout=LOG, stderr=subprocess.STDOUT, env=env)
    print("exit:", r.returncode, file=LOG)
    open(os.path.join(OUT, "DONE" if r.returncode == 0 else "FAILED"), "w").write(str(r.returncode))
''')
wp = os.path.join(OUT, "worker.py")
open(wp, "w").write(worker)
p = subprocess.Popen(["python3", wp], stdout=open(os.path.join(OUT, "worker_out.log"), "w"),
                     stderr=subprocess.STDOUT, start_new_session=True)
print("WORKER_PID", p.pid)
print("LAUNCHED", TASK, MODEL, OUT, "| input:", INPUT_FILE, "| suffix:", AUDIO_SUFFIX)
