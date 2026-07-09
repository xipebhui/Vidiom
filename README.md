# Vidiom

Vidiom 是一个从“一句话”生成短剧的 agent 画布产品。用户输入一句故事种子，系统创建一个可运行的画布流程，由 Premise、Character、Beat、Script、Production 等 agent 节点逐步产出短剧脚本和拍摄包。

## 能力

- 导入故事/灵感文本到待处理队列
- Studio Web 产品：一句话输入、可搜索/筛选的项目工作队列、agent 画布、节点检查器、脚本预览
- Studio 会记住最近打开的项目、筛选条件、画布节点和 Review 标签，刷新后可继续上一处工作
- 创建画布和草稿编辑支持创作 Brief：时长、画幅、语气、目标观众和必含要素会进入 agent 上下文
- 草稿项目可在 Seed Inspector 中编辑标题、一句话和创作 Brief，并持久化到画布与生成队列
- Studio 右侧提供 Run Readiness 面板，运行前汇总一句话、Brief、节点指令和下一步 agent 范围
- Agent 节点 Inspector 可保存节点级生成指令，用于约束后续运行或从该节点创建修订草稿
- 任意项目可复制为新的 draft，用于保留原成片并快速迭代一句话和 Brief
- Review 面板支持脚本节拍/对白、角色动机/故事引擎、拍摄清单/镜头计划审阅
- Review 面板提供成片检查页，基于脚本、Brief 和拍摄包显示阻塞项、警告与可拍摄性指标
- Review 面板的成片检查页可保存人工发布备注、待办和审批意见，并随成片包导出
- Review 面板的成片检查页可把阻塞项/警告整理成带 open、done、blocked 状态的发布任务清单
- Review 面板提供交付页，可在下载前查看 JSON 成片包文件名、脚本/拍摄体量、发布备注和导出清单
- 完成项目可在 Review 面板直接编辑标题、logline、节拍、场景摘要和对白，并保存到成片导出包
- 完成项目可在 Review 面板直接编辑拍摄包：视觉风格、场景、道具、剪辑备注和镜头计划会保存到成片导出包
- 完成项目可在画布节点上创建修订草稿，保留上游 agent 输出并只重跑所选节点及下游
- 修订草稿会继承源项目的节点级生成指令，便于针对脚本对白、节拍结构或拍摄包要求做定向重跑
- 运行 Agent 会立即进入后台生成，画布、进度条和 Timeline 会自动刷新节点状态
- Timeline 顶部显示运行开始时间、已用时、当前 agent 节点耗时和最后活动，便于判断项目是否卡住
- 运行中的项目可暂停；当前 agent 节点完成后停止，之后可从未完成节点继续
- Timeline 面板展示项目创建、每个 agent 节点状态、更新时间、输出摘要和错误
- Timeline 会记录人工保存的成片脚本和拍摄包编辑，并在导出的 JSON 成片包中保留 activity 历史
- 失败项目可一键重置为 draft，保留已完成节点并清理失败节点，便于调整 Brief 后继续迭代
- 完成项目可从 Studio 下载包含脚本、拍摄包和 agent 输出的 JSON 成片包
- Agent 画布工作流：Premise Agent、Character Agent、Beat Agent、Script Agent、Production Agent
- 使用 OpenAI-compatible Chat Completions JSON schema 生成结构化短剧
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

在 Studio 中创建画布前，可设置时长、画幅、语气、目标观众和必含要素。项目列表支持按标题/一句话搜索，并可按 draft、running、paused、completed、failed 状态筛选；每个项目行会显示 seed 摘要、agent 完成进度、下一步动作、当前/失败节点和更新时间，便于把 Studio 当成真实工作队列使用。Studio 会在浏览器本地保存最近打开的项目、筛选条件、所选节点和 Review 标签，刷新或重新打开后直接回到上次上下文。创建画布后，选中 Seed 节点可编辑草稿标题、一句话和创作 Brief；右侧 Run Readiness 会在运行前汇总 seed 强度、Brief 完整度、节点级指令数量和下一步 agent，且可直接跳转到 Seed 或下一个 agent 节点。任意项目都可从顶部复制为新的 draft，继续改写而不覆盖原项目。运行 Agent 后项目立即进入后台生成，画布节点、顶部进度和 Timeline 会自动刷新；Timeline 会记录运行、暂停、完成、失败、重置等状态变化，并在顶部显示本轮运行耗时与当前节点耗时。运行中可点击暂停，当前 agent 节点完成后项目进入 paused，再点击继续会复用已完成节点并从未完成节点恢复。失败项目可从顶部重置为 draft，清理失败节点后继续编辑或重跑。Review 面板可切换查看脚本对白、角色设计和拍摄包。项目完成后可点击顶部下载按钮导出 JSON 成片包，也可选中某个 agent 节点创建修订草稿，保留此前节点输出并从该节点开始重跑。

选中任意 Agent 节点时，Inspector 会显示 Node Guidance 表单。保存后的指令会绑定到该节点，运行到对应 agent 时进入模型指令和上下文；如果项目已完成，可先在目标节点保存指令，再从该节点创建修订草稿，系统会保留上游输出并只重跑目标节点及下游。导出的 JSON 成片包会在 project metadata 中记录 agent_instructions，便于复盘本次生成的人工约束。

Review 面板的脚本页在项目完成后会显示“编辑成片脚本”，可直接微调标题、logline、节拍、场景摘要和对白；保存后会更新项目标题、画布脚本节点、成片包导出内容和历史 production 记录，并在 Timeline/导出包中留下本次编辑摘要。拍摄页会显示“编辑拍摄包”，可直接微调视觉风格、拍摄场景、道具、剪辑备注和镜头计划；保存后会更新画布 Production 节点、成片包导出内容和 Timeline/导出包 activity。检查页会把当前脚本、Brief 和拍摄包汇总成 release check，提示 logline、场景数、对白覆盖、地点/道具一致性、镜头覆盖和时长风险，帮助用户在导出前完成最后审阅。完成项目还可在检查页保存发布状态、人工审阅摘要、下一步待办、带状态的发布任务和审批意见；这些备注会进入 Timeline，并随导出的 JSON 成片包一起交付。交付页会把导出文件名、Brief、发布状态、发布任务状态、脚本场景/节拍、镜头数量、agent 输出和 activity 数量汇总成清单，并提供同页下载入口。

必须配置：

```bash
HM_BASE_URL=...
HM_LLM_APIKEY=...
HM_IMG_APIKEY=...
VIDIOM_DATABASE_PATH=./data/vidiom.sqlite3
```

语言 agent 固定使用 `gpt-5.5`，项目图像生成固定使用 `gpt-image-2`。两类调用都会使用 `HM_BASE_URL`，语言调用使用 `HM_LLM_APIKEY`，图像调用使用 `HM_IMG_APIKEY`。缺少必需配置时，运行或图像请求会进入可见失败状态，不会生成假成功结果。

## 每小时运行

本机 cron：

```bash
crontab deploy/crontab.example
```

常驻进程：

```bash
vidiom scheduler
```

图像生成 smoke test：

```bash
source .venv/bin/activate
vidiom init-db
vidiom serve
```

打开 `http://127.0.0.1:8000`，创建或选择一个项目，在 Review 的“图像”页输入项目相关 prompt 并点击“生成项目图像”。成功后该页会显示 `gpt-image-2` 生成资产的状态、prompt、URL/base64 图像或可检索引用；失败时会显示绑定到该图像请求的错误信息。

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

## 迭代记录

### 2026-07-10 00:48 CST - 接入真实模型配置与项目图像生成

- 对应需求文档条目：`docs/next-product-function-spec.md` 的 “Real Model Provider Integration”，覆盖语言 agent runtime、Image Generation Foundation、Data/API、UX 和 Documentation 验收项。
- 本轮开发内容：语言 agent 改为通过 OpenAI-compatible provider 使用 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`；新增 `gpt-image-2` 图像 provider、项目图像生成 API、生成资产持久化、Studio 图像页、导出包 image asset metadata。
- 用户价值：用户可以用真实模型运行 agent 画布，并从项目 prompt 生成第一张可验证视觉资产，为后续分镜图和素材节点打基础。
- 涉及文件/模块：`src/vidiom/config.py`、`src/vidiom/providers.py`、`src/vidiom/generator.py`、`src/vidiom/canvas.py`、`src/vidiom/storage.py`、`src/vidiom/web.py`、`src/vidiom/static/index.html`、`src/vidiom/static/app.js`、`src/vidiom/static/styles.css`、`tests/test_pipeline.py`、`tests/test_web.py`、`.env.example`。
- 验证命令与结果：`.venv/bin/python -m ruff check .` 通过；`.venv/bin/python -m pytest` 通过，43 passed，1 个 StarletteDeprecationWarning 来自依赖；真实 `.env` smoke test 通过，临时数据库中 agent 项目完成 5/5 节点，标题为“明晨6:17”，`gpt-image-2` 图像资产 completed 并返回 base64 图像。
- 仍待处理事项：本轮不实现批量分镜、图像编辑、多角度、打光、全景、导演台、视频/音频能力；后续可将图像资产挂到画布节点和故事板 shot。

### 2026-07-10 00:37 CST - 阻塞：缺少 next product function spec

- 对应需求文档条目：本轮必须读取并以 `docs/next-product-function-spec.md` 为主要需求来源，但该文件不存在；`docs/product-gap-analysis.md` 也不存在；`docs/libtv-product-function-description.md` 可读取。
- 本轮开发内容：未实现产品功能增量；按任务约束仅新增阻塞说明。
- 用户价值：避免在缺少验收标准时自行发散产品方向，保留清晰的下一步输入要求。
- 涉及文件/模块：`docs/development-blockers.md`、`README.md`。
- 验证命令与结果：`.venv/bin/python -m ruff check .` 通过；`.venv/bin/python -m pytest` 通过，29 passed，1 个 StarletteDeprecationWarning 来自依赖。
- 仍待处理事项：补充 `docs/next-product-function-spec.md`，并在其中写明可验证的验收标准后再继续开发。
