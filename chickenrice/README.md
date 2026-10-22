# ChickenRice 路线（本分支）

在 Google Colab（colab CLI）上运行 [TransWithAI/Faster-Whisper-TransWithAI-ChickenRice](https://github.com/TransWithAI/Faster-Whisper-TransWithAI-ChickenRice) 的两个版本，与主线（main 分支）的 Purfview Faster-Whisper-XXL 路线做同片对比。

- **翻译版**：海南鸡 v2 模型（`chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2`，large-v2 经 5000 小时日中数据微调），task=translate，**直接输出中文字幕**。
- **转录版**：日文转录模型（`TransWithAI/whisper-ja-1.5B-ct2`，源自 efwkjn/whisper-ja-1.5B），task=transcribe，输出日文字幕。
- 两版共用其**音声优化 VAD**（`TransWithAI/Whisper-Vad-EncDec-ASMR-onnx`，ONNX）+ 智能分块（≤30s/块）+ segment_merge 后处理，全部使用仓库 `generation_config.json5` 的出厂配置。

## 文件

| 文件 | 作用 |
|---|---|
| `cr_setup.py` | 在 Colab VM 内执行：克隆 ChickenRice 仓库、装依赖、下 VAD 与两个模型（各约 3.1GB）、按 `INPUT_URL` 环境变量下载视频 |
| `cr_setup_lv2.py` | setup 变体：主模型只下原版 large-v2（混搭实验用，见文末） |
| `cr_setup_hj_nosmart.py` | setup 变体：只下海南鸡模型，并关掉智能 VAD（C2 配置，见文末） |
| `cr_launch.py` | 按 `TASK=translate\|transcribe` 环境变量脱钩启动 infer.py 后台进程，日志/标记在 `/content/out_<task>/`。输入文件可用 `INPUT_FILE` 指定（视频或音频均可，如 mp3/m4a/flac/wav），不指定时自动取 `/content/input/` 里的第一个文件；setup 脚本经 `INPUT_URL` 下载时按 URL 原名保存 |
| `cr_poll.py` | 查看后台任务状态、日志尾部与产物 |
| `compare.py` | 本地三方字幕量化对比工具（条数、时间轴覆盖、缺陷计数、指定时间窗抽查、关键术语计数） |
| `pool_upload.py` | 本地工具：把生成的中文成品字幕上传到公共字幕池（见下方「字幕池上传」） |

## Colab 快速开始

```bash
colab new -s purfview --gpu T4
# setup（约 2-4 分钟；INPUT_URL 为视频直链，可选）
colab exec -s purfview --timeout 3600 --env "INPUT_URL=https://example.com/video.mp4" -f chickenrice/cr_setup.py
# 依次跑两个任务（不要并行，显存与 CPU VAD 都会打架）
colab exec -s purfview --timeout 120 --env "TASK=translate"  -f chickenrice/cr_launch.py
colab exec -s purfview --timeout 120 --env "TASK=transcribe" -f chickenrice/cr_launch.py
# 轮询（把 TASK 换成对应任务），出现 STATUS DONE 后下载
colab exec -s purfview --timeout 120 --env "TASK=translate" -f chickenrice/cr_poll.py
colab download -s purfview /content/out_translate/114820.srt  out-zh.srt
colab download -s purfview /content/out_transcribe/114820.srt out-ja.srt
colab stop -s purfview
```

注：本路线不需要挂载 Google Drive（模型从 HuggingFace 现下、产物直接回传），省去每台新 VM 的 Drive 授权点击。

### 字幕池上传

生成的中文成品（海南鸡直出等）可上传到公共字幕池 `chickenrice-subtitle-pool.jzdxjk.workers.dev`（与 subtitle-modal-web 同一接口），供他人按番号检索复用：

```bash
POOL_UPLOAD_KEY=<上传密钥> python3 chickenrice/pool_upload.py --dir <字幕目录>
python3 chickenrice/pool_upload.py --dry-run out/*.srt   # 只验过滤与去重，不上传
python3 chickenrice/pool_upload.py --stats               # 查池内总数
```

规则与服务端一致并在本地先行过滤：仅 srt/ass/ssa、≤2MiB、合法 UTF-8、至少 1 个汉字、假名占比 >0.20 判为日文字幕跳过（双语稿也会被跳，池子只收纯中文成品）；番号从文件名提取（`ABC-123`、`FC2-1234567`、`abc123` 三种格式，提不到时用 `--code` 指定）；按内容 sha256 去重，台账在 `~/.chickenrice-pool-uploaded.json`。密钥只从环境变量或 `--key-file` 读，**不写进代码与仓库**；401/403 整批中止、429 停、410 跳过、5xx 重试 3 次。上传是显式动作，不随转录自动执行——介意公开分享就不要跑它。

### 直接喂音频

引擎只用音轨（Whisper 内部统一重采样为 16kHz 单声道），**可以直接给音频文件**（mp3/m4a/flac/wav/aac 等），识别质量与喂视频无差别，文件却小一个量级——1.2GB 的视频抽成 128kbps 音频约 100MB（本地提取：`ffmpeg -i in.mp4 -vn -c:a copy out.m4a`）：

- `INPUT_URL` 给音频直链即可，setup 会按原名存入 `/content/input/`；
- 本地音频先 `colab upload -s purfview <文件> /content/input/`，多文件时用 `--env "INPUT_FILE=/content/input/xxx.m4a"` 写明；
- 不指定 `INPUT_FILE` 时，`cr_launch.py` 自动取 `/content/input/` 里的第一个文件，后缀过滤随扩展名自动适配。

## 环境坑（2026-10 实测，Colab 当前镜像）

1. **PyAV 版本不兼容**：pip 最新 av 与 faster-whisper 冲突，`decode_audio` 报 `TypeError: open() got an unexpected keyword argument 'metadata_errors'`。`cr_setup.py` 已钉 `av==13.1.0`。
2. **libcublas.so.12 找不到**：Colab 镜像已是 CUDA 13（torch 2.11+cu130），CTTranslate2 的 CUDA 12 构建找不到 `libcublas.so.12`（pip 的 nvidia-cublas-cu12 装了但不在加载路径）。`cr_launch.py` 的 worker 已自动把 `dist-packages/nvidia/*/lib` 加进 `LD_LIBRARY_PATH`。
3. **VAD 进度是 `\r` 回车刷新的**：看日志要用 `tr '\r' '\n'` 转换，否则 tail/grep 会整段刷屏或误判。
4. **完成标记别信残留**：`cr_launch.py` 启动前会清掉旧的 DONE/FAILED（已内置）；判断完成以「DONE 标记 + SRT 存在 + 日志 exit: 0」三证为准。
5. VM 内会出现 `HF_TOKEN secret timed out` 警告——模型都是公开仓库，无视即可。
6. **onnxruntime 必须用 GPU 版且钉版本**：装 CPU 版 `onnxruntime` 时 VAD 只能跑 CPU（外层 VAD 约 9 分钟）。换 `onnxruntime-gpu` 后 VAD 可走 GPU，但**最新版（1.31，CUDA 13 构建）的 CUDA provider 在 Colab 镜像上一加载就段错误**，ORT 会静默回落 CPU、日志照常写 `on CPU`，极具迷惑性；`cr_setup.py` 已钉 `onnxruntime-gpu==1.22.0`（CUDA 12 构建，配合坑 2 的库路径可用）。验证方法：日志出现 `VAD Progress: ... on GPU (CUDA)`，外层 VAD 约 2 分钟（2026-10-22 实测）。

## 实测数据（测试片 1:38:13，T4，免费层）

| 阶段 | 耗时 |
|---|---|
| setup（克隆+依赖+6.2GB 模型+视频） | 约 2-4 分钟 |
| 外层 VAD（196 块扫描） | CPU 约 9 分钟/任务；GPU（onnxruntime-gpu==1.22.0）约 2 分钟/任务 |
| 智能分块生成（217 块逐块串行） | 约 26 分钟/任务 |
| **单任务合计** | **约 35 分钟** |

其 VAD 检出语音占比 38.4%（37分37秒）。等值消耗：含两次崩溃重试的整会话约 78 分钟 ≈ 1.39 CU（免费层不实际扣费，速率为 T4 1.07 CU/小时）。

## 三方质量对比（同一视频）

| | Purfview XXL（main 路线） | ChickenRice 转录版 | ChickenRice 翻译版 |
|---|---|---|---|
| 条数 | 769 | 855 | 728 |
| 时间轴覆盖 | 19.1% | 44.8% | 55.9% |
| 0 时长条 / <0.8s 碎条 | 6 / 230 | 0 / 56 | 0 / 1 |
| >12s 长条 | 1（51.8s） | 23 | 62 |
| 耗时 | 约 5 分钟 | 约 35 分钟 | 约 35 分钟 |

- **术语准确率**：转录版碾压 Purfview 的系统性错词——マンコ:マンゴー = 8:2（XXL 为 0:21）、中出し:仲出し = 6:2、「精神→精子」误认 0 次、「寝てる」串扰基本消失、お掃除フェラ 写对。日文微调模型 + 细 VAD 的组合在对白准确率上确实更强。
- **幻觉**：XXL 在安静段出现整段虚构（「犬が心臓の筋肉を使って醫院へ行きます」）；转录版同位置为场景内碎片，无整段幻觉；翻译版无虚构剧情，但呻吟段会出现拟声词刷屏（如 `biu biu`）。
- **翻译版**：中文直出、对白流畅、术语地道，可作独立成品；缺点是人名偶串味（「小栗みそお」）、合并长句多（62 条 >12s）、无日文对照可核。
- **结论**：要日文原稿质量 → 转录版（慢 7 倍）；要速度与批量 → XXL 路线 + 错词词典修正；翻译版适合快速看懂剧情，或与 XXL 日文稿交叉校验错漏（本次它把 XXL 听错的几处全翻对了）。

## 后续实验：无主模型版管线 × 原版 large-v2（2026-10-22）

用 `cr_setup_lv2.py` 把主模型换成 Systran 原版 large-v2（即 Purfview XXL 所用权重），其余管线不变，同片再跑转录（`cr_launch.py` 已泛化：可用 `MODEL`/`TAG` 环境变量指定模型与输出目录）：

| | XXL（原管线） | 混搭版（本管线 × large-v2） | 转录版（本管线 × 1.5B） |
|---|---|---|---|
| 条数 / 覆盖 | 769 / 19.1% | 737 / 35.6% | 855 / 44.8% |
| マンコ : マンゴー | 0 : 21 | 2 : 8 | 8 : 2 |
| 0 时长 / 51 秒挂屏 | 6 / 1 | 0 / 0 | 0 / 0 |
| 52 分幻觉段 | 整段虚构（狗/医院） | 整段漏检（空白） | 场景内碎片 |
| 耗时 | 约 5 分钟 | **8 分 28 秒**（GPU VAD） | 约 35 分钟（CPU VAD 时代） |

结论：同权重换管线后，时间轴卫生与幻觉明显改善（管线之功），但术语错词基本保留、覆盖率反而下降（细 VAD 对原版模型漏检更多）——XXL 的优势确实来自它自己的 VAD 配方，而本管线里模型微调的收益（1.5B）大于管线本身。另注意翻译任务挂原版 large-v2 只会出英文字幕（Whisper translate 的定义是译入英语），中文直出是海南鸡权重的能力，与管线无关。

## 后续实验之二：智能 VAD 关闭（C2，2026-10-22）

用 `cr_setup_hj_nosmart.py` 把海南鸡翻译的 `smart_split_with_vad` 关掉（复现 subtitle-modal-web 的实际生效配置），其余参数与翻译版完全相同，同片再跑：

| | C（智能开） | C2（智能关） |
|---|---|---|
| 条数 / 覆盖 | 728 / 55.9% | 835 / 40.2% |
| >12 秒长条 | 62 | **0** |
| <0.8 秒碎条 / >60 秒空白 | 1 / 4 | 9 / 2 |
| 语音检出 | 38.4% | 39.1% |
| 耗时 | 约 35 分钟（CPU VAD 时代） | 约 10 分半（GPU VAD） |

结论：该部署文档警告的「关闭智能 VAD 会时间轴漂移」在本片未出现（两版首尾锚点一致、都在 5862 秒以同一句收尾）。真正的变化是字幕形态：关掉后生成走原始 VAD 段 + segment_merge，翻译版最被诟病的合并长句直接归零；覆盖率下降只是长条消失的统计效应。翻译对错大体同级（代价：人名从译错变为未译出的假名残段、片尾多一条串译）。**就观看体验而言，海南鸡直出场景关掉智能 VAD 反而更好**——本仓库后续生产已采用 C2 配置（实例：ABF-395，2:14:25 的片子约 8 分半出稿，并已上传字幕池）。四方+C2 的完整数据见 main 分支 `reports/114820/` 与 Issue #1。
