# 在 Colab 运行时里执行（colab exec -f poll_xxl.py）——秒回
# 打印 worker 状态、日志尾巴和产物列表
import os

OUT = "/content/out"
done = os.path.exists(os.path.join(OUT, "DONE"))
failed = os.path.exists(os.path.join(OUT, "FAILED"))
print("STATUS", "DONE" if done else "FAILED" if failed else "RUNNING")
for name in ("worker.log", "run.log"):
    p = os.path.join(OUT, name)
    if os.path.exists(p):
        lines = open(p, errors="replace").read().splitlines()
        print(f"--- {name} tail ---")
        print("\n".join(lines[-15:]))
print("outputs:", sorted(os.listdir(OUT)) if os.path.exists(OUT) else [])
