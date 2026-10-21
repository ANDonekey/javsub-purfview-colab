# javsub-purfview-colab

在 **Google Colab 免费 GPU** 上跑 **Purfview Faster-Whisper-XXL**（large-v2）生成日语字幕，
全程通过 Colab 官方新 CLI（`google-colab-cli`）在命令行编排，不用开 Colab 网页。
参数配方取自 WhisperJAV issue
[#464](https://github.com/meizhong986/WhisperJAV/issues/464) 的三方实测对比结论：
XXL large-v2 在日语（JAV）素材上准确率与稳定性最好。

## 为什么是这个组合

- **Purfview XXL 赢在预设，不只是模型**：它的粗 VAD 长段（3 秒静音才切、0.9 秒留白、
  不限段长）保住了 large-v2 的 30 秒窗口上下文；细切 VAD 会切断日语的主语省略与
  句尾语气，是其他管线幻觉多的主要原因。实测核对过：#464 的胜出配方就是
  XXL r245.4 的**出厂默认**（见 `docs/xxl-help-r245.4.txt`）。
- **Colab 免费 T4 足够**：large-v2 + `int8_float16` 实测约 **6.5 倍实时**
  （1 小时视频约 10 分钟）。不需要本地显卡。
- **Drive 当仓库**：XXL 包（1.6GB）和模型（2.9GB）播种到 Google Drive 后，
  新会话直接拷，不再每次从 GitHub/HuggingFace 下载；视频放 Drive 的
  `purfview/input`，字幕自动回写 `purfview/out`。

## 流程

```
本地 run.sh
  └─ colab new --gpu T4            开会话
  └─ colab drivemount              挂 Drive（见下方注意事项）
  └─ colab exec setup_xxl.py       VM 内：从 Drive 拷包+模型（没有才下载）→ 7zz 解压 → 自检
  └─ colab exec launch_xxl.py      VM 内：转写以脱离 kernel 的后台进程启动，立即返回
  └─ colab exec poll_xxl.py ×N     每分钟轮询状态/日志（顺带保活会话）
  └─ SRT 同步回 Drive purfview/out + colab download 取回本地 → colab stop 关会话
```

## 快速开始

前置：Linux 或 macOS（CLI 不支持 Windows，可用 WSL）；一个 Google 账号
（免费层即可，T4）；本地 Python 3。

```bash
# 1) 安装 Colab CLI（任选其一）
uv tool install google-colab-cli
# 或 pip install google-colab-cli

# 2) 首次授权：任跑一条命令（如 colab sessions），按提示打开链接、
#    把 Google 落地页显示的授权码粘回终端（远程复制粘贴流程，只需一次）

# 3) （可选）打补丁，见下方「补丁」一节，按需

# 4) 克隆本仓库，一条龙跑一个视频
git clone https://github.com/ANDonekey/javsub-purfview-colab
cd javsub-purfview-colab
./run.sh /path/to/video.mp4
# 或者大文件给直链，让 Colab 自己下：
INPUT_URL=https://example.com/video.mp4 ./run.sh
```

**第一次运行**会从 GitHub 下载 XXL 包并在转写时下载模型（Colab 机房带宽，几分钟）。
之后在挂着 Drive 的会话里跑一次 `sync_to_drive.py` 把包和模型播种到 Drive，
后续会话就走 Drive 拷贝：

```bash
colab exec -s purfview --timeout 1800 -f sync_to_drive.py
```

Drive 布局（自动创建）：

```
MyDrive/purfview/
├── xxl_linux.7z      # XXL r245.4 Linux 包
├── models/           # faster-whisper-large-v2
├── input/            # 把要转的视频扔这里，run.sh 不带参数即可
└── out/              # SRT 自动同步到这里
```

## 当前参数（launch_xxl.py 写死）

| 项 | 值 | 说明 |
|---|---|---|
| 模型 | `large-v2` | **必须显式指定**，XXL 默认是 medium |
| 语言 | `ja` | 写死日语，不靠自动检测 |
| compute_type | `int8_float16` | #464 作者同款量化 |
| VAD | `silero_v4_fw`，min_silence `3000ms`，speech_pad `900ms`，max_speech 不限 | 粗切长段，配方的核心 |
| beam / best_of | 5 / 5 | |
| 输出格式 | SRT + `--standard_asia` | 16 字/行亚洲排版断行 |
| 防幻觉（默认） | compression 2.4 / logprob -1.0 / no_speech 0.6 | XXL 出厂默认，未改 |
| 上下文（默认） | condition_on_previous_text=True，prompt_reset 0.5，fallback 步进 0.2 | XXL 出厂默认，未改 |

未启用（可自行加）：人声分离 `--ff_vocal_extract mdx_kim2`、说话人分离
`--diarize`、逐句断句 `--sentence`。本仓库只做**日语原稿识别**；
翻译/校对/断句排版请接 WhisperJAV、Subtitle Edit 或 pyVideoTrans 等工具。

## 实测数据（2026-10-21，免费层 T4）

- 开会话 → setup 完成：GitHub 直下模式约 **2 分 46 秒**；Drive 模式约 **4 分 20 秒**
  （瓶颈是 2.9GB 模型经 Drive 挂载层拷贝，约 30MB/s。Drive 模式图的是免外部
  下载和输入输出持久化，不是更快。）
- 冒烟测试：gTTS 合成日语短文（`examples/test_ja.txt`），转写 50 秒内完成
  （含首次模型下载），4 句与原文几乎逐字一致，结果见 `examples/test_ja.srt`。
- 容量估算：免费层单会话最长 12 小时但 GPU 是动态配额；按实测速度，
  每天大约能跑 15~30 小时时长的视频字幕，日常几部片绰绰有余。

## 补丁（patches/，按需）

对 `google-colab-cli 0.7.5` 的两个小补丁，都是实测踩出来的：

1. `colab-cli-proxy-411.patch` — 若你的网络出口有代理会剥掉无 body POST 的
   `Content-Length: 0`，`colab new` 会死在 Google 的 **411 Length Required**。
   补丁让空 POST 自动带一个 `{}` body。直连环境不需要。
2. `colab-cli-drivemount-timeout.patch` — `drive.mount` 默认超时 120 秒，
   短于人工点授权链接的往返，第一次挂载很容易超时失败。补丁放到 600 秒。

应用方式（在 CLI 的安装目录里）：`patch -p1 < patches/xxx.patch`，路径前缀对应
包内 `colab_cli/...`。改完删掉对应的 `__pycache__` 再运行。

## 已知坑清单

- `colab exec` 默认超时只有 **30 秒**：长步骤必须显式 `--timeout`；
  转写这种几十分钟的活要像 `launch_xxl.py` 那样脱钩成后台进程 + 轮询，
  不能指望一次 exec 跑完。
- **Drive 授权绑 VM**：每台新 VM 第一次 `drivemount` 都需要人在浏览器点一次
  授权链接（同意是存着的，点开即完成），CLI 会停住等你回车。这是 Colab 的机制
  （网页版靠浏览器登录态静默完成），不是脚本 bug。
- XXL 的 `.7z` 用了 **BCJ2** 压缩，`py7zr` 解不开，必须用官方 `7zz`
  （setup 脚本会自动下载）。包内自带 CUDA 12 的 cuBLAS/cuDNN 8.9.7，
  Colab 的驱动直接兼容，无需另装库。
- 必须用 **GPU 运行时**：XXL 是 CUDA 二进制，TPU（v5e/v6e）用不了。
- Drive 免费空间 15GB：包+模型约 4.5GB，往 `input` 囤大文件时留意余量。

## 目录

- `run.sh` — 本地一条龙编排
- `setup_xxl.py` — VM 内准备 XXL（Drive 优先、幂等、自检）
- `launch_xxl.py` / `poll_xxl.py` — 后台转写启动与轮询
- `sync_to_drive.py` — 把包和模型播种到 Drive（跑过一次转写后执行）
- `gen_test_input.py` — 合成日语测试语音做冒烟测试
- `prep_input.py` — 建输入目录
- `patches/` — 上述两个 CLI 补丁
- `docs/xxl-help-r245.4.txt` — XXL r245.4 的完整 `--help`（参数默认值核对依据）
- `examples/` — 冒烟测试的原文与 SRT 结果

## 声明

- 本仓库只是编排脚本，不包含 Purfview Faster-Whisper-XXL 本体与模型权重，
  它们由脚本在运行时从官方渠道下载（XXL：github.com/Purfview/whisper-standalone-win；
  模型：HuggingFace 上的 faster-whisper-large-v2）。
- Colab 免费层有动态配额与使用条款，请勿用于滥用性/全天候无人值守负载。
- 脚本以 MIT 许可发布。
