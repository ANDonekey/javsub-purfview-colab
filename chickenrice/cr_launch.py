# 在 Colab 运行时里执行（colab exec --env TASK=translate|transcribe -f cr_launch.py）——立即返回
# 职责：把 infer.py 以脱离 kernel 的后台进程启动，日志与完成标记写到 /content/out_<task>/
import os, subprocess, textwrap
os.environ.setdefault("MPLBACKEND", "Agg")
TASK = os.environ.get("TASK", "translate")
MODEL = {"translate": "hainanji", "transcribe": "ja15b"}[TASK]
OUT = f"/content/out_{TASK}"
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
           "--audio_suffixes", "mp4", "--sub_formats", "srt",
           "--output_dir", OUT, "--overwrite",
           "--log_level", "INFO",
           "/content/input/114820.mp4"]
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
print("LAUNCHED", TASK, MODEL, OUT)
