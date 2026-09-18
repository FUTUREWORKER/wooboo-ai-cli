# Wooboo AI CLI

`wooboo` 是挖宝AI（Wooboo AI）的本地命令行入口。用户通过网页登录后，即可在本机调用图片、视频、数字人和创作 Agent 等功能。

CLI 只有一个版本，通过配置切换环境。默认生产地址为 `https://wooboo.ycszai.com`，本机凭据保存在 `~/.wooboo-ai/credentials.json`。

## 安装 CLI

使用 npm 从 GitHub 安装：

```bash
npm install -g github:FUTUREWORKER/wooboo-ai-cli
wooboo --version
```

使用 pipx：

```bash
pipx install git+https://github.com/FUTUREWORKER/wooboo-ai-cli.git
```

使用 GitHub raw 安装脚本：

```powershell
irm https://raw.githubusercontent.com/FUTUREWORKER/wooboo-ai-cli/main/install-wooboo-ai-cli.ps1 | iex
```

```bash
curl -fsSL https://raw.githubusercontent.com/FUTUREWORKER/wooboo-ai-cli/main/install-wooboo-ai-cli.sh | sh
```

npm 安装方式仍需要本机 Python 3.9+；npm 包中的 `wooboo` 启动器会调用 Python CLI。

## 安装 Agent Skills

CLI 执行平台命令，Agent skill 告诉 Codex、OpenClaw、Hermes 等 Agent 何时以及如何调用它。推荐按需安装：

```bash
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-image-generation
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-video-shanying
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-video-lingguang
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-video-suying-2-5-flash
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-video-package
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-digital-human-avatar
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-voice-clone
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-voice-list
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-digital-human-video
npx -y skills add FUTUREWORKER/wooboo-ai-cli --skill wooboo-creative-agent
```

也可以把 `skills/<skill-name>` 整个目录复制到目标 Agent 的 skill/instruction 目录。仓库里的 skill 是 Agent 通用格式，不依赖 Codex 专属目录。

Skill 全程使用挖宝AI系统名称：图片使用“专业模型”“标准模型”“基础模型”，视频使用“闪影”“灵光”“速影 2.5Flash”。IP 分身、爆款视频拆解、历史和收藏仍可直接通过 CLI 使用，但不再提供独立 Agent Skill。

各 Skill 会先从用户消息、对话上下文和附件中补全参数。只有缺少无法推断且会阻止任务提交的必要信息时才向用户追问；可选参数或已有默认值的参数不会逐项询问，同时缺少多个必要信息时会合并成一次简短提问。

## 登录与配置

```bash
wooboo login web --open
wooboo account
wooboo logout
```

环境覆盖优先级为命令参数、环境变量、持久配置、生产默认值：

```bash
wooboo config set api-base http://127.0.0.1:3000
wooboo config set h5-base http://127.0.0.1:5174
wooboo config set output-dir ./downloads
wooboo config list
```

也支持 `--api-base`、`--h5-base`、`WOOBOO_API_BASE`、`WOOBOO_H5_BASE` 和 `WOOBOO_OUTPUT_DIR`。

## 图片创作

```bash
wooboo image models
wooboo image generate --model "专业模型" --prompt "高级棚拍产品图，电影感灯光"
```

图片生成支持“专业模型”“标准模型”“基础模型”。未指定时按专业模型处理；需要切换时使用 `--model "标准模型"` 或 `--model "基础模型"`。

参考图生成或改图：

```bash
wooboo image generate \
  --model "专业模型" \
  --prompt "保留主体，改成日落海边广告大片" \
  --reference-image ./product.png \
  --aspect-ratio 16:9 \
  --quality 2k
```

Skill 在用户未指定模型时会显式选择“专业模型”；未指定档位、比例或质量时，CLI 使用该系统模型的当前默认值。

## 普通视频创作

```bash
wooboo video models
wooboo video optimize-prompt --series "闪影" --mode t2v --prompt "未来城市夜景"
```

CLI 支持服务端按模型动态开放的 `t2v`、`i2v`、`first_last_frame`、`r2v`、`video_extend` 和 `video_edit`。

闪影文生视频：

```bash
wooboo video generate \
  --series "闪影" \
  --mode t2v \
  --prompt "电影感城市夜景，镜头缓慢推进" \
  --duration-seconds 10
```

闪影全能参考：

```bash
wooboo video generate \
  --series "闪影" \
  --mode r2v \
  --prompt "参考人物、动作和旁白节奏生成品牌短片" \
  --reference-image ./person.png \
  --reference-video ./motion.mp4 \
  --reference-audio ./voice.mp3 \
  --duration-seconds 15 \
  --audio
```

图片和视频生成通过JSON提交参数；参考素材先经系统授权直传，再提交上传标识。模型显示名以`wooboo video models`的实际输出为准（含空格），也可用`--model-config-id`指定。

速影 2.5Flash 文生视频：

```bash
wooboo video generate \
  --model "速影 2.5Flash" \
  --mode t2v \
  --prompt "电影感产品广告，柔和灯光扫过主体" \
  --duration-seconds 5
```

闪影还支持一个 `--reference-file` 或一个 `--reference-link`，两者不能同时使用。素材数量、格式、时长、输出时长和分辨率以 `wooboo video models` 返回能力为准。

```bash
wooboo video status <task-id>
wooboo video download <task-id> --output-dir ./downloads
```

## 视频智能包装

视频包装用于处理已有视频，不是生成新镜头：

```bash
wooboo video-package bootstrap
wooboo video-package templates
wooboo video-package music
```

```bash
wooboo video-package generate \
  --video ./source.mp4 \
  --title "3分钟看懂AI工作流" \
  --duration-seconds 86.4 \
  --style-id <template-id> \
  --music-id <music-id> \
  --identity-name "胡老师" \
  --identity-desc "AI产品顾问"
```

还支持 `video-package list|status|download|delete`。

## 数字人

```bash
wooboo avatar create --video ./avatar-training.mp4 --title "品牌主理人"
wooboo avatar list
wooboo voice clone --audio ./voice.wav --name "品牌音色"
wooboo voice list
```

```bash
wooboo digital-human generate \
  --avatar-record-id <avatar-id> \
  --drive-mode text \
  --voice-record-id <voice-id> \
  --text "大家好，欢迎来到今天的分享" \
  --subtitle
```

```bash
wooboo digital-human generate \
  --avatar-record-id <avatar-id> \
  --drive-mode audio \
  --audio ./speech.mp3
```

## 创作 Agent

```bash
wooboo agent bootstrap creative-agent
wooboo agent chat creative-agent --text "为新品写一个短视频脚本"
wooboo agent chat creative-agent --conversation-id <id> --file ./brief.docx --text "结合附件继续"
```

```bash
wooboo agent conversations creative-agent
wooboo agent messages <conversation-id>
wooboo agent clear creative-agent
wooboo agent cancel creative-agent <job-id>
```

也可以把 `creative-agent` 换成平台已发布的其他 Agent code。

## IP 分身

```bash
wooboo ip-clone create --name "胡老师" --company "未来工作室" --business "AI产品培训与咨询"
wooboo ip-clone list
wooboo ip-clone upload <id> --type photo --file ./portrait.png
wooboo ip-clone upload <id> --type video --file ./intro.mp4
wooboo ip-clone upload <id> --type voice --file ./voice.wav
wooboo ip-clone parse-file --file ./profile.docx
```

还支持 `ip-clone update` 和 `ip-clone delete`。

## 爆款视频拆解

```bash
wooboo viral-video analyze --url "https://v.douyin.com/..."
wooboo viral-video latest
wooboo viral-video status <task-id>
```

## 历史和收藏

```bash
wooboo history list
wooboo history download <record-id> --output-dir ./downloads
wooboo history delete <record-id>

wooboo favorite list
wooboo favorite add --kind image --record-id <record-id>
wooboo favorite remove <favorite-id>
```

收藏是平台保存的独立副本；删除创作历史和移除收藏是两个不同操作。

## 账号管理

```bash
wooboo account points --page 1 --page-size 20
wooboo account bind-invitation <invitation-code>
wooboo account avatar --image ./avatar.png
wooboo account redeem <recharge-card-code>
wooboo account change-password --old-password <old> --new-password <new>
```

## 使用边界

- 创作功能使用当前登录的挖宝AI账户。
- 登录凭据保存在本机 `~/.wooboo-ai/credentials.json`。
- CLI 不包含 Admin 管理后台和 PC 画布管理命令。
