# 在 Colab 运行时里执行（colab exec --timeout 3600 -f setup_xxl.py）
# 职责：验 GPU → 下载并解压 Purfview Faster-Whisper-XXL Linux 版 → 自检二进制
# 注意：XXL 的 .7z 用了 BCJ2 滤镜，py7zr 解不了，必须用官方 7zz 二进制解压
import os, subprocess, sys, glob, tarfile

os.environ.setdefault("MPLBACKEND", "Agg")  # r245.3 修过 Colab 的 matplotlib 后端问题，加上双保险

BASE = "/content/purfview"
PKG_URL = "https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_linux.7z"
LIBS_URL = "https://github.com/Purfview/whisper-standalone-win/releases/download/libs/cuBLAS.and.cuDNN_CUDA11_linux_v4.7z"
SEVENZIP_URL = "https://www.7-zip.org/a/7z2501-linux-x64.tar.xz"
EXPECTED_PKG_SIZE = 1657690937

def sh(cmd, **kw):
    print("+", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, **kw)
    if r.returncode != 0:
        raise SystemExit(f"命令失败({r.returncode}): {cmd}")

os.makedirs(BASE, exist_ok=True)

# 1) GPU 自检：XXL 是 CTranslate2/CUDA 二进制，必须 NVIDIA GPU（TPU 用不了）
sh("nvidia-smi || true")
try:
    import torch
    print("torch cuda:", torch.cuda.is_available(),
          torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
except Exception as e:
    print("torch 检查跳过:", e)

# 2) 准备 7zz（官方独立二进制，tar.xz 用标准库 tarfile 解）
seven = os.path.join(BASE, "7z", "7zz")
if not os.path.exists(seven):
    tgz = os.path.join(BASE, "7z.tar.xz")
    sh(f"curl -L -o {tgz} {SEVENZIP_URL}")
    with tarfile.open(tgz) as t:
        t.extractall(os.path.join(BASE, "7z"))
    os.chmod(seven, 0o755)
print("7zz ready:", seven)

# 3) 拿 XXL Linux 包：Drive 有就从 Drive 拷（内网，快），没有才从 GitHub 下
#    （幂等：大小精确对上就跳过）
pkg = os.path.join(BASE, "xxl_linux.7z")
DRV_PKG = "/content/drive/MyDrive/purfview/xxl_linux.7z"
if not (os.path.exists(pkg) and os.path.getsize(pkg) == EXPECTED_PKG_SIZE):
    if os.path.exists(DRV_PKG) and os.path.getsize(DRV_PKG) == EXPECTED_PKG_SIZE:
        print("从 Drive 拷贝 XXL 包 ...", flush=True)
        sh(f"cp {DRV_PKG} {pkg}")
    else:
        sh(f"curl -L -C - -o {pkg} {PKG_URL}")
assert os.path.getsize(pkg) == EXPECTED_PKG_SIZE, f"包大小不对: {os.path.getsize(pkg)}"
print("pkg size OK:", os.path.getsize(pkg))

# 4) 解压（7zz；包内自带 CUDA 12 的 cuBLAS/cuDNN 8.9.7，一般无需另补库）
dest = os.path.join(BASE, "xxl")
bins = glob.glob(os.path.join(dest, "**", "faster-whisper-xxl"), recursive=True)
if not bins:
    sh(f"{seven} x -y -o{dest} {pkg} > /dev/null")
    bins = glob.glob(os.path.join(dest, "**", "faster-whisper-xxl"), recursive=True)
assert bins, "解压后没找到 faster-whisper-xxl 二进制"
BIN = bins[0]
os.chmod(BIN, 0o755)
print("BIN:", BIN)
print("XXL 目录内容:", sorted(os.listdir(os.path.dirname(BIN)))[:10])

# 5) 二进制自检（--help 能跑通 = 动态库基本齐）
r = subprocess.run([BIN, "--help"], capture_output=True, text=True,
                   env={**os.environ, "MPLBACKEND": "Agg"})
print((r.stdout or r.stderr)[:800])
if r.returncode != 0:
    print("!! --help 失败，尝试补官方 cuBLAS/cuDNN Linux 库包到二进制同目录")
    sh(f"curl -L -o {BASE}/libs.7z {LIBS_URL}")
    sh(f"{seven} x -y -o{os.path.dirname(BIN)} {BASE}/libs.7z > /dev/null")
    r = subprocess.run([BIN, "--help"], capture_output=True, text=True)
    print((r.stdout or r.stderr)[:800])
# 6) 模型：Drive 有播种好的就拷进本地 _models（避免每次从 HF 重下 ~3GB）
DRV_MODELS = "/content/drive/MyDrive/purfview/models"
local_models = os.path.join(os.path.dirname(BIN), "_models")
if os.path.exists(f"{DRV_MODELS}/faster-whisper-large-v2/model.bin"):
    if not os.path.exists(f"{local_models}/faster-whisper-large-v2/model.bin"):
        print("从 Drive 拷贝模型 ...", flush=True)
        os.makedirs(local_models, exist_ok=True)
        sh(f"cp -r {DRV_MODELS}/. {local_models}/")
    print("models ready:", os.listdir(local_models))
else:
    print("Drive 上还没有模型（首次运行会在转写时下载，之后跑 sync_to_drive.py 播种）")

print("SETUP_DONE", BIN)
