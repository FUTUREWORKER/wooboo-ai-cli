---
name: wooboo-video-suying-2-5-flash
description: 通过挖宝AI“速影 2.5Flash”生成视频，支持文生视频、单图生视频、首尾帧和图片或音频参考创作。
---

# 挖宝AI速影 2.5Flash 视频生成

使用 `wooboo` CLI，并通过系统显示名“速影 2.5Flash”选择模型和说明结果。

## 参数补全与追问

- 先从用户消息、对话上下文和已提供的附件中提取参数；能够安全推断时直接使用，不重复询问。
- 必须有明确的视频画面或动作要求。用户没有说明要生成什么时，先追问创作内容。
- 纯文字创作使用文生视频；单图生视频必须有起始图片；首尾帧生成必须同时有首帧和尾帧；参考生成必须有至少一项图片或音频素材。
- 用户选择的模式缺少对应素材时，先请用户补充素材，不要改用其他模式代替。
- 时长、比例、分辨率和输出目录不是阻塞参数；用户未指定时使用当前默认值。
- 如果同时缺少多个必要信息，合并成一次简短提问。

提交前运行 `wooboo video models`，确认该系统模型当前处于启用状态。当前支持 4–12 秒、720P，以及 `9:16`、`16:9`、`1:1`、`4:3`、`3:4`、`21:9` 比例；如果平台返回的能力发生变化，以平台结果为准。

文生视频：

```bash
wooboo video generate \
  --model "速影 2.5Flash" \
  --mode t2v \
  --prompt "电影感产品广告，柔和灯光扫过主体，镜头缓慢推进" \
  --duration-seconds 5
```

单图生视频：

```bash
wooboo video generate \
  --model "速影 2.5Flash" \
  --mode i2v \
  --prompt "保持人物和服装一致，自然转头并微笑" \
  --first-frame /path/to/image.png \
  --duration-seconds 5
```

首尾帧生成：

```bash
wooboo video generate \
  --model "速影 2.5Flash" \
  --mode first_last_frame \
  --prompt "镜头从首帧平滑运动到尾帧，主体变化自然连续" \
  --first-frame /path/to/first.png \
  --last-frame /path/to/last.png \
  --duration-seconds 5
```

参考生成最多使用 5 张图片和 3 段音频，不支持参考视频：

```bash
wooboo video generate \
  --model "速影 2.5Flash" \
  --mode r2v \
  --prompt "保持参考人物和产品一致，并参考音频节奏生成品牌短片" \
  --reference-image /path/to/person.png \
  --reference-image /path/to/product.png \
  --reference-audio /path/to/voice.mp3 \
  --duration-seconds 8 \
  --output-dir ./generated-videos
```

用户未指定比例或时长时使用平台默认值。完成后报告任务 ID、状态、视频 URL 和本地下载路径；失败时直接反馈平台错误。
