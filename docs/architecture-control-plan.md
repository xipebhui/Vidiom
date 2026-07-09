# Architecture Control Plan: Complete Real Model End-to-End Acceptance

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Complete Real Model End-to-End Acceptance。
- 最新产品差距：`docs/product-gap-analysis.md` 将 P0 缺口锁定为真实 `.env` smoke 总状态 `interrupted`；`agent_project` 已使用 `gpt-5.5` 完成 5/5 节点，`storyboard_generation` 使用 `gpt-5.5` 等待 291.208 秒后被中断，`project_image_generation` 和 `export_package` 均为 `incomplete`。
- 最新真实验收记录：`docs/real-model-smoke-result.md` 记录 run started at `2026-07-09T20:48:42.312673+00:00`，overall status 为 `interrupted`。该记录是当前真实模型接入状态判断依据，历史 completed 或 provider 503 记录不能覆盖它。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 要求脚本/故事板先产出可信 shot、角色、场景、道具和 prompt 上游；无限画布、批量分镜图、视频、音频、导演台和合成都依赖这一层。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`；生产 runtime 不得生成假结果，provider、配置、结构化输出或中断问题必须可见且脱敏。

## 当前实现状态

- 当前分支：`main`，与 `origin/main` 对齐。
- 最新提交：`045dd2a Update product requirement for interrupted real smoke`。
- 上一轮开发提交：`1534beb Strengthen real smoke release gate` 已完成 `vidiom smoke-real-model-storyboard` 发布门禁强化：只有 agent、Storyboard、项目图像和导出包四段全部 `completed` 时，CLI 才返回通过；未通过时仍写入 `docs/real-model-smoke-result.md`。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，不纳入本轮架构文档提交。
- README 迭代记录已写明最新真实 smoke 为 `interrupted`：agent 完成，Storyboard 中断，图像和导出未完成。该状态说明真实模型接入仍未完成。
- `src/vidiom/smoke.py` 已有 `RealModelSmokeRun`、四段阶段记录、`smoke_gate_completed()`、错误脱敏、Markdown 结果写入和 KeyboardInterrupt 中断记录。
- `src/vidiom/cli.py` 已让非 completed smoke 返回非零状态，可作为发布门禁。
- `tests/test_smoke.py` 已覆盖 completed、配置缺失、provider 503、无效 Storyboard payload、KeyboardInterrupt、CLI completed/failed 退出码和四段 completed 判定。
- `src/vidiom/storyboard.py` 已用 `OpenAIStoryboardGenerator` 调用 `gpt-5.5`，并将成功 payload 持久化为 Storyboard 领域对象；异常会写入 Storyboard failed 状态并脱敏。
- `src/vidiom/web.py` 已提供 Storyboard 生成 API、后台任务、状态查询、shot review 和 image link/unlink API；Studio 可展示生成中、失败、失败但保留旧成功结果、shot 列表、资产摘要和图像关联。
- `src/vidiom/storage.py` 已具备 `storyboards`、`storyboard_shots`、`project_story_assets`、`storyboard_shot_assets`、`storyboard_shot_image_assets`、`generated_image_assets` 和导出包 Storyboard deliverable。

## 架构判断

本轮产品需求有效且包含验收标准，因此不阻塞在需求输入。现有 Storyboard 领域模型、项目图像资产、导出包和真实 smoke 发布门禁已经支撑“可信记录未通过状态”。当前阻塞不再是缺少 smoke runner 或 CLI 门禁，而是 Storyboard 真实生成阶段在最新验收窗口内没有完成，导致下游 `gpt-image-2` 图像和导出包没有同一轮 completed 证据。

本轮首要开发任务应转向 Storyboard 真实调用生命周期、可观测性、结果收口和同轮复验，而不是继续堆 UI 功能或重复门禁强化。

- 前端架构：现有静态 Studio 可支撑本轮 Storyboard 状态、旧成功结果、shot/asset/image link 展示和错误提示；长期仍撑不住 LibTV 式无限画布、自由节点、资产栏、历史记录、图像/视频/音频资产、工作流和导演台。该长期约束继续有效，但本轮产品明确不切换到这些下游能力，因此不启动前端大重构。
- 后端存储：当前 project、canvas nodes、generated image assets、storyboards、shots、story assets、shot-image links 和 activity 结构可支撑本轮验收；本轮不需要新增视频、音频、导演台或跨项目资产库表。需要加强的是 Storyboard 生成尝试、最新 smoke 阶段结果和用户可读状态之间的一致性。
- 数据模型：Storyboard 必须继续作为一等领域对象，不回退为 agent 节点长文本。旧 completed Storyboard、本次 failed/interrupted 尝试和最新 smoke 结果必须明确隔离。
- API 边界：`/storyboard/generate`、`/storyboard` 查询、image link、导出包边界基本可用；本轮只允许围绕 Storyboard 生成状态、错误摘要、同轮 smoke 校验和导出校验收口，不新增 LibTV 下游 API。
- 异步任务：Studio 后台任务和 CLI 顺序 smoke 均已存在。最新阻塞说明真实 Storyboard 调用可能超过当前自动化运行窗口或被外部中断；中断必须保持 `interrupted`，后续阶段必须保持 `incomplete`。调用超时、自动重试、排队等待、验收窗口延长或人工复跑策略均为“需用户确认”，不能作为既定实现写入开发任务。
- Provider 抽象：继续复用 `OpenAICompatibleLanguageClient` 和 `OpenAICompatibleImageClient`，模型名保持 `gpt-5.5` 与 `gpt-image-2`。不得自动改用其他模型、其他 provider、假数据或占位结果。
- 测试结构：常规测试继续使用 fake clients，不消耗真实模型额度；真实 `.env` smoke 仍是显式验收命令，必须写入 `docs/real-model-smoke-result.md`。
- README 迭代记录：开发完成后必须明确最新真实 smoke 是 completed、failed、interrupted 还是 incomplete，并区分历史 completed、上一轮 503 和最新中断记录。

## 本轮架构决策

### 1. 首要任务改为 Storyboard 真实生成生命周期收口

上一轮已完成发布门禁。本轮首要任务是让开发围绕最新中断点收口：

1. 确认 Storyboard 生成开始、运行中、失败、中断和完成状态在 Storage、API、Studio、smoke 结果文件和 README 中语义一致。
2. 确认 `storyboard_generation` 被中断时不会生成假 Storyboard、假图像资产或假导出包。
3. 确认已有旧 completed Storyboard 不会被最新中断记录包装成本次 completed。
4. 确认开发完成后必须再次运行真实 smoke；只有四段同轮 completed，才能写真实模型接入完成。
5. 如果真实 smoke 仍 interrupted/failed/incomplete，开发结果应是“发布门禁正确阻塞并记录最新事实”，不能转向其他 LibTV 功能。

### 2. 同轮端到端 completed 是唯一通过标准

本轮真实模型接入完成标准保持严格：

- `agent_project` 必须使用 `gpt-5.5` completed，并完成 5/5 agent 节点。
- `storyboard_generation` 必须使用 `gpt-5.5` completed，并持久化多个结构化 shots、assets、relationships 和 image prompts。
- `project_image_generation` 必须使用 `gpt-image-2` completed，且生成或复验真实项目图像资产。
- `export_package` 必须 completed，并包含 completed Storyboard metadata、shots、assets、relations、image links 和 image asset 摘要。
- `docs/real-model-smoke-result.md` 总状态必须为 `completed`，四段核心阶段必须均为 `completed`。

任一阶段为 `failed`、`interrupted` 或 `incomplete` 时，当前版本仍视为真实模型接入未完成。

### 3. 前端长期架构约束继续保留

用户判断“当前架构撑不住 LibTV 级产品”是长期架构约束：

- 当前 `src/vidiom/static/app.js` 单体结构只适合作为短期 Studio 壳。
- 后续进入无限画布、自由节点、资产栏、历史记录、工作流、视频/音频或导演台前，必须拆出画布状态、节点渲染、资产面板、生成任务、审阅工作区和媒体资产模块边界。
- 本轮产品明确不做自由无限画布、批量分镜图、视频、音频或导演台，因此本轮不把前端大重构列为首要任务。
- 本轮如需改 UI，只能围绕 Storyboard 最新状态、旧成功结果提示、图像关联、导出可读性和错误脱敏做最小改动。

### 4. 后端长期数据模型方向继续保持一等领域边界

- Storyboard、shots、story assets、shot-asset relations、shot-image links、generated image assets 继续独立建模。
- 后续 LibTV 对齐需要的 canvas nodes、workflow runs、generation jobs、asset library、video assets、audio assets、director-stage scenes 和 smoke history 应独立设计迁移，不复用 Storyboard 表承载无关能力。
- 本轮不提前引入跨项目资产库、视频/音频表或导演台数据结构。
- 如未来需要长期保存多轮验收历史，可设计 `smoke_runs`/`smoke_run_stages` 或等价结构；本轮只要求最新结果文件、README 和开发交接一致。

### 5. 调用策略必须由用户确认

最新 Storyboard 中断可能涉及 provider 响应时长、自动化运行窗口、任务生命周期或人工中断。以下策略可能影响成本、等待时间和失败语义，本轮不得直接实现为默认行为：

- 调用超时调整。
- 自动重试。
- 排队等待。
- 延长验收窗口。
- 人工复跑策略。

如开发认为必须采用其中任一策略，只能在实现说明或 README 待处理事项中标为“需用户确认”，不得写成既定行为。

## 当前风险与控制

- 风险：把上一轮门禁强化完成误读为真实模型接入完成。控制：本轮文档以最新 `interrupted` 记录作为当前状态。
- 风险：围绕旧 provider 503 继续拆任务，忽略最新阻塞已经移动到 Storyboard 中断。控制：首要任务改为 Storyboard 真实生成生命周期收口。
- 风险：为通过验收引入备用模型、备用 provider、假 Storyboard、假图像或占位导出。控制：开发任务明确禁止；同轮真实 completed 是唯一通过标准。
- 风险：旧 completed Storyboard 被 UI 或导出文案误读为本次真实验收 completed。控制：继续保留 `has_completed_result`、`latest_attempt_failed`、`result_source` 语义，并要求回归测试。
- 风险：真实 smoke 长耗时被中断后没有足够上下文供下一轮判断。控制：结果文件必须保留阶段状态、模型名、耗时、关键计数和错误摘要。
- 风险：过早推进 LibTV 视频、音频、导演台或无限画布，把下游能力建立在未通过的 Storyboard 上游上。控制：最新真实 smoke completed 前，产品和架构继续锁定真实模型端到端验收。

## 为什么能支撑 LibTV 对齐

LibTV 的批量分镜图、视频片段、音频、导演台和合成都依赖可审阅、可复用、可追溯的结构化 Storyboard 上游。Vidiom 已经建立 Storyboard 数据底座和真实 smoke 门禁，但最新真实验收停在 `storyboard_generation=interrupted`，下游图像与导出没有同轮完成证据。

因此，本轮架构控制选择先完成 Storyboard 真实生成生命周期与同轮端到端验收收口。只有最新 `docs/real-model-smoke-result.md` 显示 agent、Storyboard、项目图像和导出四段均 `completed`，Vidiom 才具备继续推进 LibTV 无限画布、批量分镜图、视频、音频或导演台能力的可信上游。
