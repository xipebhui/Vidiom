# Vidiom

Vidiom 是一个从“一句话”生成短剧的 agent 画布产品。用户输入一句故事种子，系统创建一个可运行的画布流程，由 Premise、Character、Beat、Script、Production 等 agent 节点逐步产出短剧脚本和拍摄包。

## 能力

- 导入故事/灵感文本到待处理队列
- Studio Web 产品：一句话输入、项目列表、agent 画布、节点检查器、脚本预览
- 草稿项目可在 Seed Inspector 中编辑标题和一句话，并持久化到画布与生成队列
- Timeline 面板展示项目创建、每个 agent 节点状态、更新时间、输出摘要和错误
- Agent 画布工作流：Premise Agent、Character Agent、Beat Agent、Script Agent、Production Agent
- 使用 OpenAI Responses API 生成 JSON 结构化短剧
- 保存生成状态、错误信息、成品脚本和运行日志
- 支持手动执行一次、常驻调度器、cron、systemd、Docker、GitHub Actions
- 内置单元测试，核心管线可用假生成器稳定验证

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
vidiom init-db
vidiom serve
```

打开 `http://127.0.0.1:8000`。

在 Studio 中创建画布后，选中 Seed 节点可编辑草稿标题和一句话；运行 Agent 后项目进入生成流程，Timeline 会展示节点状态、更新时间、输出摘要和错误，已生成内容保持可检查、可预览。

必须配置：

```bash
OPENAI_API_KEY=...
VIDIOM_OPENAI_MODEL=gpt-5.5
VIDIOM_DATABASE_PATH=./data/vidiom.sqlite3
```

## 每小时运行

本机 cron：

```bash
crontab deploy/crontab.example
```

常驻进程：

```bash
vidiom scheduler
```

systemd：

```bash
sudo cp deploy/vidiom.service /etc/systemd/system/vidiom.service
sudo systemctl daemon-reload
sudo systemctl enable --now vidiom
```

Docker：

```bash
docker build -t vidiom .
docker run --env-file .env -p 8000:8000 -v "$PWD/data:/data" vidiom
```

## 常用命令

```bash
vidiom init-db
vidiom ingest-text "灵感文本"
vidiom ingest-file data/inspirations.jsonl
vidiom run-once --limit 5
vidiom list-productions --limit 10
vidiom export-production <production-id> --output out/script.json
vidiom serve
vidiom scheduler
```

`ingest-file` 支持 JSONL，每行格式：

```json
{"text":"一个家庭群里的语音意外揭穿了十年前的秘密。","source_type":"seed","source_ref":"manual-001"}
```

## 数据

默认数据库路径为 `./data/vidiom.sqlite3`。生产环境建议设置为 `/data/vidiom.sqlite3` 或 `/var/lib/vidiom/vidiom.sqlite3`。

生成成品以 JSON 保存，便于后续接入分镜、视频合成、审核、人审后台或发布系统。
