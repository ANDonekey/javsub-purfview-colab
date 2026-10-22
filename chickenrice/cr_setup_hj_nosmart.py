# 在 Colab 运行时里执行（colab exec -f cr_setup_hj_nosmart.py）
# 与 cr_setup.py 相同，但只下海南鸡模型，并把 generation_config 的智能 VAD 关掉，
# 复现 subtitle-modal-web 的实际生效配置（enable_smart_vad=false）
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

snapshot_download("chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2",
                  local_dir=f"{REPO}/models/hainanji")
sz = os.path.getsize(f"{REPO}/models/hainanji/model.bin")
print("MODEL: hainanji", sz, flush=True)
assert sz > 2_900_000_000, "hainanji model.bin too small"

# 关键一步：关掉智能 VAD（与 subtitle-modal-web 的热补丁等效）
cfg = f"{REPO}/generation_config.json5"
s = open(cfg, encoding="utf-8").read()
assert '"smart_split_with_vad": true' in s, "smart key not found in generation_config.json5"
open(cfg, "w", encoding="utf-8").write(s.replace('"smart_split_with_vad": true',
                                                 '"smart_split_with_vad": false'))
print("SMART_VAD: disabled", flush=True)

url = os.environ.get("INPUT_URL", "")
os.makedirs("/content/input", exist_ok=True)
_name = url.split("?")[0].rstrip("/").split("/")[-1] if url else ""
dst = f"/content/input/{_name}" if _name and "." in _name else f"/content/input/{_name or 'input'}.mp4"
if url and not os.path.exists(dst):
    run(f"curl -sL -o {dst} '{url}'")
if os.path.exists(dst):
    print("VIDEO:", os.path.getsize(dst), flush=True)
print("CR_SETUP_DONE", flush=True)
