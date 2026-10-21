# 在 Colab 运行时里执行（colab exec --env TASK=... -f cr_poll.py）
# 职责：报告后台 infer 的状态、日志尾部与产物
import os
TASK = os.environ.get("TASK", "translate")
OUT = f"/content/out_{TASK}"
print("STATUS", "DONE" if os.path.exists(f"{OUT}/DONE") else
      "FAILED" if os.path.exists(f"{OUT}/FAILED") else "RUNNING")
for name in ("run.log",):
    p = os.path.join(OUT, name)
    if os.path.exists(p):
        print(f"--- {name} tail ---")
        lines = open(p, errors="replace").read().splitlines()
        print("\n".join(lines[-15:]))
print("outputs:", sorted(os.listdir(OUT)) if os.path.isdir(OUT) else "none")
