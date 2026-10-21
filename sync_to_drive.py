# 在 Colab 运行时里执行（需先 drivemount 成功）
# 职责：把 XXL 包和已下载的模型播种到 Drive 的 purfview 目录（只需播种一次）
#       并建好 input / out 目录。已存在的跳过，幂等。
import os, glob, shutil, subprocess

DRV = "/content/drive/MyDrive/purfview"
BASE = "/content/purfview"

assert os.path.isdir("/content/drive/MyDrive"), "Drive 没挂上，先跑 colab drivemount"
os.makedirs(f"{DRV}/input", exist_ok=True)
os.makedirs(f"{DRV}/out", exist_ok=True)

def du(p):
    return subprocess.run(["du", "-sh", p], capture_output=True, text=True).stdout.split()[0]

# 1) XXL 包
src_pkg = f"{BASE}/xxl_linux.7z"
dst_pkg = f"{DRV}/xxl_linux.7z"
if os.path.exists(src_pkg) and not os.path.exists(dst_pkg):
    print("copy pkg -> Drive ...", flush=True)
    shutil.copy2(src_pkg, dst_pkg)
print("pkg on Drive:", os.path.exists(dst_pkg), du(dst_pkg) if os.path.exists(dst_pkg) else "-")

# 2) 模型（转写跑过一次后 _models 才有内容）
bins = glob.glob(f"{BASE}/xxl/**/faster-whisper-xxl", recursive=True)
if bins:
    models_src = os.path.join(os.path.dirname(bins[0]), "_models")
    models_dst = f"{DRV}/models"
    if os.path.isdir(models_src) and os.listdir(models_src):
        if not os.path.exists(f"{models_dst}/faster-whisper-large-v2/model.bin"):
            print("copy models -> Drive ...", flush=True)
            os.makedirs(models_dst, exist_ok=True)
            subprocess.run(["cp", "-r", f"{models_src}/.", models_dst], check=True)
        print("models on Drive:", du(models_dst))
    else:
        print("本地 _models 还是空的（还没跑过转写），模型待下次播种")
print("SYNC_DONE")
