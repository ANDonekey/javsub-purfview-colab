# 实测报告：同一视频四路日语字幕管线对比（114820，1:38:13）

> 本报告配套的全部字幕实物就在本目录（A–E 五个文件，见下表链接）。
> 测试环境：Google Colab 免费层 T4，管线脚本见仓库 `main` 分支（Purfview 路线）与 `chickenrice` 分支（ChickenRice 路线）。
> 测试片为 720p、时长 1:38:13 的日语对白视频，同一输入、四路独立运行。

## 四路配置

| 编号 | 管线 | 主模型 | 任务 | 字幕文件 |
|---|---|---|---|---|
| A | Purfview Faster-Whisper-XXL r245.4（出厂配方） | large-v2 原版 | transcribe | [A_purfview-xxl_large-v2.ja.srt](A_purfview-xxl_large-v2.ja.srt) |
| B | ChickenRice | whisper-ja-1.5B（日文微调 CT2） | transcribe | [B_chickenrice_transcribe_ja-1.5B.ja.srt](B_chickenrice_transcribe_ja-1.5B.ja.srt) |
| C | ChickenRice | 海南鸡 v2（large-v2 JA→ZH 微调） | translate（中文直出） | [C_chickenrice_translate_hainanji-v2.zh.srt](C_chickenrice_translate_hainanji-v2.zh.srt) |
| D | ChickenRice（无主模型版用法） | large-v2 原版（Systran CT2，与 A 同权重） | transcribe | [D_hybrid_chickenrice-pipeline_large-v2.ja.srt](D_hybrid_chickenrice-pipeline_large-v2.ja.srt) |
| 附 | A 的日文稿 + 中文译文合成的双语 ASS（上中下日） | — | — | [E_purfview-xxl_bilingual.zh-ja.ass](E_purfview-xxl_bilingual.zh-ja.ass) |

关键参数：A 的 VAD 为 `silero_v4_fw`、最小静音 3000ms、speech pad 900ms、beam/best_of 5/5、condition_on_previous_text（即 WhisperJAV issue #464 的胜出配方，核对过系 XXL 出厂默认）；B/C/D 用 ChickenRice 自带 ASMR 音声 VAD（EncDec ONNX；静音阈值 100ms、智能切块 ≤30s、segment_merge 间隔 ≤2s/最长 20s、repetition_penalty 1.1）。

## 量化对比（同一脚本统计）

| 指标 | A (XXL) | B (转录版) | C (翻译版) | D (混搭) |
|---|---|---|---|---|
| 字幕条数 | 769 | 855 | 728 | 737 |
| 时间轴覆盖率 | 19.1% | 44.8% | 55.9% | 35.6% |
| 0 时长条目 | 6 | 0 | 0 | 0 |
| <0.8 秒碎条 | 230 | 56 | 1 | 16 |
| >12 秒长条 | 1（51.8 秒挂屏） | 23 | 62 | 24 |
| >60 秒空白段 | 5 | 3 | 4 | 9 |

注：覆盖率口径为字幕时间轴占视频总时长；各家 VAD 对语音的检出口径不同（ChickenRice 的 VAD 全片只判定 38.4% 为语音），覆盖率高低不能直接等同漏检率，需结合下文抽查。

## 术语错误计数（日文稿，全片计次）

| 错误→正确 | A (XXL) | B (转录版) | D (混搭，同 A 权重) |
|---|---|---|---|
| マンゴー → マンコ | **21 : 0** | 2 : 8 | 8 : 2 |
| 仲出し → 中出し | 3 : 1 | 2 : 6 | 0 : 1 |
| 精神 → 精子 | 3 次 | 0 次 | 1 次 |
| 「寝てる」误检簇 | 约 31 条 | 0 | 3 |
| お掃除セラー → フェラ | 3 次 | 0 次 | 0 次 |
| ちんぽん → ちんぽ | 7 次 | 0 次 | 0 次 |

C 为中文直出、无此项错误：对应段落「无套内射」「清洁口交」等术语翻译正确。

## 定性抽查

- **开头采访段（0:00–1:40）**：B/C 内容最完整准确（人名、"ゴムなし派" 等都对）；A 基本可用但有错词；D 人名串成「おグリミさん」、还把「（ゴムなし）生派です」听成「生放送です」。
- **52:21–53:47 多人嘈杂段**：A **整段幻觉**——生成「小狗用心脏肌肉去医院」式与画面无关的完整句子共 5 条；B 为场景内碎片、无虚构；C 中文通顺可用；D **整段漏检**（该段空白，幻觉消失的代价是没了）。
- **女优名**：A/B 正确作「小栗みそお」；C 串味成「小栗味噌汤」（音译字面化）；D 串成「おグリミさん」。
- **呻吟段**：C 出现拟声词刷屏（"biu biu…"）；A 有「アデル」等 stray 词；B/D 相对克制。

## 速度（T4）

| 路线 | 任务耗时 |
|---|---|
| A | 转写约 4 分 54 秒（约 20 倍实时） |
| D | 8 分 28 秒（外层 VAD GPU 约 2 分 + 生成约 6 分半） |
| B / C | 约 35 分钟/任务（其中外层 VAD 在 CPU 上约 9 分钟；换 GPU VAD 后预计与 D 同量级，未全程复测） |

**VAD 的 GPU 坑（重要）**：ChickenRice 的音声 VAD 并不强制 CPU——其代码在 onnxruntime 提供 CUDA provider 时自动走 GPU。但 pip 装 CPU 版 `onnxruntime` 时只能跑 CPU（外层 VAD 约 9 分钟）；最新版 `onnxruntime-gpu` 1.31（CUDA 13 构建）的 CUDA provider 在当前 Colab 镜像上**一加载就段错误**，ORT 静默回落 CPU 且无任何报错。钉 `onnxruntime-gpu==1.22.0`（CUDA 12 构建）+ 注入 nvidia 库路径后正常（外层 VAD 约 2 分钟）。`chickenrice` 分支的 `cr_setup.py` 已按此钉版。

## 结论与选型建议

1. **日文原稿质量：B（转录版）最好。** A 的系统性错词在 B 基本治愈，也没有整段幻觉；代价是慢（逐块生成；GPU VAD 后预计约 10 分钟量级）。
2. **速度与批量：A（XXL）最优。** 约 5 分钟/片，清晰对白段质量足够；错词可后处理词典修正，主要风险是嘈杂段整段幻觉，需人工抽查。
3. **中文直出：C 可直接用**于看懂内容/粗剪；人名串味、长句合并（62 条 >12 秒）、拟声词刷屏是其固有毛病，精翻仍需以 B 的日文稿为底。
4. **D（混搭）证明了变量分解**：同权重换管线，时间轴卫生与幻觉明显改善，但术语错词保留、覆盖率下降——**XXL 的优势主要来自它自己的粗 VAD 配方；在 ChickenRice 管线里，模型微调（B）的收益大于管线本身。**
5. 交叉校验值得做：C 曾把 A 听错的多处重灾区全部翻对，不同路线的错误不相关，可互为校验。

## 复现

- A：`main` 分支 `./run.sh '<视频直链>'`（参数见根 README）。
- B/C：`chickenrice` 分支 `cr_setup.py` → `cr_launch.py`（TASK=transcribe/translate）。
- D：`chickenrice` 分支 `cr_setup_lv2.py` → `cr_launch.py`（TASK=transcribe、MODEL=large-v2、TAG=lv2）。
- 统计工具：`chickenrice` 分支 `compare.py`。
