# 在 Colab 运行时里执行（colab exec -f launch_xxl.py）——立即返回
# 职责：把转写 worker 以脱离 kernel 的后台进程启动，日志写 /content/out/run.log
# 原因：colab exec 默认超时 30s，转写要跑几十分钟，必须脱钩 + 轮询
import os, subprocess, textwrap

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = "/content/purfview"
OUT = "/content/out"
os.makedirs(OUT, exist_ok=True)
INPUT_URL = os.environ.get("INPUT_URL", "")

worker = textwrap.dedent('''
    import os, subprocess, glob, sys
    os.environ.setdefault("MPLBACKEND", "Agg")
    BASE = "/content/purfview"; OUT = "/content/out"
    LOG = open(os.path.join(OUT, "worker.log"), "a", buffering=1)
    def log(*a):
        print(*a, file=LOG); print(*a)
    try:
        bins = glob.glob(os.path.join(BASE, "xxl", "**", "faster-whisper-xxl"), recursive=True)
        assert bins, "no xxl binary; run setup first"
        BIN = bins[0]; XXL_DIR = os.path.dirname(BIN)
        INPUT_URL = os.environ.get("INPUT_URL", "")
        inputs = []
        if INPUT_URL:
            name = INPUT_URL.split("?")[0].rstrip("/").split("/")[-1] or "input.mp4"
            dst = os.path.join("/content/input", name)
            os.makedirs("/content/input", exist_ok=True)
            subprocess.run(f"curl -L -o {dst} '{INPUT_URL}'", shell=True, check=True)
            inputs = [dst]
        else:
            inputs = sorted(glob.glob("/content/input/*"))
            # Drive input 目录（用户直接把视频扔进 Drive 的 purfview/input）
            drv_in = "/content/drive/MyDrive/purfview/input"
            if os.path.isdir(drv_in):
                inputs += sorted(glob.glob(drv_in + "/*"))
        assert inputs, "no input files"
        log("inputs:", inputs)
        for src in inputs:
            cmd = [BIN, src, "-l", "ja", "-m", "large-v2",
                   "--compute_type", "int8_float16",
                   "-o", OUT, "-f", "srt",
                   "--standard_asia",
                   "--verbose", "True",
                   "--vad_method", "silero_v4_fw",
                   "--vad_min_silence_duration_ms", "3000",
                   "--vad_speech_pad_ms", "900",
                   "--beam_size", "5", "--best_of", "5"]
            log("+", " ".join(cmd))
            r = subprocess.run(cmd, cwd=XXL_DIR, stdout=LOG, stderr=subprocess.STDOUT)
            log("exit:", r.returncode, src)
        # 产物同步一份到 Drive 的 purfview/out（会话关了也不丢，用户在 Drive 里直接拿）
        drv_out = "/content/drive/MyDrive/purfview/out"
        if os.path.isdir("/content/drive/MyDrive"):
            os.makedirs(drv_out, exist_ok=True)
            for srt in glob.glob(os.path.join(OUT, "*.srt")):
                subprocess.run(["cp", srt, drv_out])
            log("srt copied to Drive out")
        open(os.path.join(OUT, "DONE"), "w").write("ok")
        log("WORKER_DONE")
    except Exception as e:
        open(os.path.join(OUT, "FAILED"), "w").write(repr(e))
        log("WORKER_FAILED", repr(e))
''')

wpath = os.path.join(BASE, "worker.py")
with open(wpath, "w") as f:
    f.write(worker)
for marker in ("DONE", "FAILED"):
    p = os.path.join(OUT, marker)
    if os.path.exists(p):
        os.remove(p)

env = {**os.environ, "MPLBACKEND": "Agg", "INPUT_URL": INPUT_URL}
proc = subprocess.Popen(
    ["python3", wpath],
    stdout=open(os.path.join(OUT, "run.log"), "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True,   # 脱离 kernel 进程组，exec 返回后继续跑
    env=env,
)
print("WORKER_PID", proc.pid)
print("LAUNCHED")
