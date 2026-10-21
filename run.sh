#!/usr/bin/env bash
# 本地编排：colab CLI 开 T4 会话 → 挂 Drive → 准备 XXL → (上传|Drive输入|直链) → 后台转写 → 轮询 → 关会话
# 用法：
#   ./run.sh /path/to/video.mp4                # 本地文件上传模式
#   INPUT_URL=https://.../video.mp4 ./run.sh    # Colab 内直链下载模式（大文件推荐）
#   ./run.sh                                    # 转写 Drive 的 purfview/input 里已有的文件
# 环境变量：
#   COLAB_BIN  colab 命令路径（默认从 PATH 找；找不到时用 ~/workspace/colab-purfview/venv/bin/colab）
#   GPU        默认 T4；有 Pro 可改 L4/A100
# 注意：colab exec 默认超时 30s，所有长步骤显式 --timeout，且转写走 launch+poll 脱钩模式
set -euo pipefail
cd "$(dirname "$0")"

if [ -n "${COLAB_BIN:-}" ]; then
  COLAB="$COLAB_BIN"
elif command -v colab >/dev/null 2>&1; then
  COLAB=colab
else
  COLAB="$HOME/workspace/colab-purfview/venv/bin/colab"
fi
SESSION=purfview
GPU="${GPU:-T4}"
VIDEO="${1:-}"

"$COLAB" new -s "$SESSION" --gpu "$GPU"
trap '"$COLAB" stop -s "$SESSION" || true' EXIT

# 0) 挂 Drive（账号授过一次权后通常自动传播凭证；若卡住说明该 VM 需要人工点一次授权链接，见 README）
"$COLAB" drivemount -s "$SESSION" || echo "警告：Drive 未挂上，将走 GitHub 下载模式"

# 1) 准备 XXL（Drive 有包/模型就拷，没有才下载；给足 1 小时超时；setup 幂等）
"$COLAB" exec -s "$SESSION" --timeout 3600 -f setup_xxl.py

# 2) 输入
"$COLAB" exec -s "$SESSION" --timeout 120 -f prep_input.py
if [ -n "$VIDEO" ]; then
  "$COLAB" upload -s "$SESSION" "$VIDEO" "/content/input/$(basename "$VIDEO")"
fi

# 3) 启动后台转写（立即返回），INPUT_URL 经 --env 注入远程 kernel
if [ -n "${INPUT_URL:-}" ]; then
  "$COLAB" exec -s "$SESSION" --timeout 120 --env "INPUT_URL=$INPUT_URL" -f launch_xxl.py
else
  "$COLAB" exec -s "$SESSION" --timeout 120 -f launch_xxl.py
fi

# 4) 轮询（每 60s，最多约 2 小时）。SRT 同时已同步到 Drive 的 purfview/out
for i in $(seq 1 120); do
  sleep 60
  OUT=$("$COLAB" exec -s "$SESSION" --timeout 60 -f poll_xxl.py || echo "STATUS POLL_ERROR")
  echo "$OUT" | head -20
  case "$OUT" in
    *"STATUS DONE"*) break ;;
    *"STATUS FAILED"*) echo "转写失败，见上方日志"; exit 1 ;;
  esac
done

# 5) 取回 SRT 到本地 out/
mkdir -p out
for f in $("$COLAB" ls -s "$SESSION" /content/out | grep -E '\.srt$' || true); do
  "$COLAB" download -s "$SESSION" "/content/out/$f" "out/$f"
done
ls -lh out/
echo "完成。会话将随脚本退出自动关闭（trap）。"
