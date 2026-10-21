# 在 Colab 运行时里执行（colab exec -f cr_setup.py）
# 职责：克隆 ChickenRice 仓库、装依赖、下 VAD + 两个模型、下载视频
# 注意：onnxruntime-gpu 必须钉 1.22.0（CUDA 12 构建）——最新版（1.31，CUDA 13 构建）
# 的 CUDA provider 在 Colab 镜像上一加载就段错误，VAD 会静默回落 CPU（2026-10-22 实测）
import os, subprocess, sys
os.environ.setdefault("MPLBACKEND", "Agg")

def run(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run("nvidia-smi -L")
REPO = "/content/chickenrice"
if not os.path.isdir(REPO):
    run(f"git clone -q --depth 1 https://github.com/TransWithAI/Faster-Whisper-TransWithAI-ChickenRice {REPO}")
subprocess.run(f"{sys.executable} -m pip uninstall -y onnxruntime", shell=True)
run(f"{sys.executable} -m pip install -q faster-whisper pyjson5 'onnxruntime-gpu==1.22.0' librosa 'av==13.1.0'")

from huggingface_hub import hf_hub_download, snapshot_download
os.makedirs(f"{REPO}/models", exist_ok=True)
for src, dst in [("model.onnx", "whisper_vad.onnx"),
                 ("model_metadata.json", "whisper_vad_metadata.json")]:
    p = hf_hub_download("TransWithAI/Whisper-Vad-EncDec-ASMR-onnx", src)
    run(f"cp '{p}' {REPO}/models/{dst}")
    print("VAD:", dst, os.path.getsize(f"{REPO}/models/{dst}"), flush=True)

for repo_id, name in [("chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2", "hainanji"),
                      ("TransWithAI/whisper-ja-1.5B-ct2", "ja15b")]:
    snapshot_download(repo_id, local_dir=f"{REPO}/models/{name}")
    sz = os.path.getsize(f"{REPO}/models/{name}/model.bin")
    print("MODEL:", name, sz, flush=True)
    assert sz > 3_000_000_000, f"{name} model.bin too small"

url = os.environ.get("INPUT_URL", "")
os.makedirs("/content/input", exist_ok=True)
dst = "/content/input/114820.mp4"
if url and not os.path.exists(dst):
    run(f"curl -sL -o {dst} '{url}'")
if os.path.exists(dst):
    print("VIDEO:", os.path.getsize(dst), flush=True)
print("CR_SETUP_DONE", flush=True)
