# 在 Colab 运行时里执行（colab exec -f cr_setup_lv2.py）
# 与 cr_setup.py 相同，但主模型换成原版 large-v2（Systran CT2，即 Purfview XXL 所用权重）
# 用于验证「ChickenRice 无主模型版管线 × Purfview 的 large-v2」组合
import os, subprocess, sys
os.environ.setdefault("MPLBACKEND", "Agg")

def run(cmd):
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)

run("nvidia-smi -L")
REPO = "/content/chickenrice"
if not os.path.isdir(REPO):
    run(f"git clone -q --depth 1 https://github.com/TransWithAI/Faster-Whisper-TransWithAI-ChickenRice {REPO}")
subprocess.run(f"{sys.executable} -m pip uninstall -y onnxruntime onnxruntime-gpu", shell=True)
run(f"{sys.executable} -m pip install -q faster-whisper pyjson5 'onnxruntime-gpu==1.22.0' librosa 'av==13.1.0'")

from huggingface_hub import hf_hub_download, snapshot_download
os.makedirs(f"{REPO}/models", exist_ok=True)
for src, dst in [("model.onnx", "whisper_vad.onnx"),
                 ("model_metadata.json", "whisper_vad_metadata.json")]:
    p = hf_hub_download("TransWithAI/Whisper-Vad-EncDec-ASMR-onnx", src)
    run(f"cp '{p}' {REPO}/models/{dst}")
    print("VAD:", dst, os.path.getsize(f"{REPO}/models/{dst}"), flush=True)

snapshot_download("Systran/faster-whisper-large-v2", local_dir=f"{REPO}/models/large-v2")
sz = os.path.getsize(f"{REPO}/models/large-v2/model.bin")
print("MODEL: large-v2", sz, flush=True)
assert sz > 2_900_000_000, "large-v2 model.bin too small"

url = os.environ.get("INPUT_URL", "")
os.makedirs("/content/input", exist_ok=True)
_name = url.split("?")[0].rstrip("/").split("/")[-1] if url else ""
dst = f"/content/input/{_name}" if _name and "." in _name else f"/content/input/{_name or 'input'}.mp4"
if url and not os.path.exists(dst):
    run(f"curl -sL -o {dst} '{url}'")
if os.path.exists(dst):
    print("VIDEO:", os.path.getsize(dst), flush=True)
print("CR_SETUP_DONE", flush=True)
