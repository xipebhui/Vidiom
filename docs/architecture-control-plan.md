# Architecture Control Plan: Real Model End-to-End Acceptance Gate

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Real Model End-to-End Acceptance Gate。
- 最新差距判断：`docs/product-gap-analysis.md` 将 P0 缺口锁定为真实 `.env` smoke 未通过；最新结果停在 `agent_project`，`gpt-5.5` provider 返回 503 `system_cpu_overloaded`，Storyboard、项目图像和导出均为 `incomplete`。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 要求脚本/故事板链路提供可信 shot、角色、场景、道具和提示词上游，后续分镜图、视频、音频、导演台和合成都依赖这一层。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`；生产 runtime 不得生成假结果，provider 或配置失败必须可见。
- 最新真实验收记录：`docs/real-model-smoke-result.md` 总状态为 `failed`，`agent_project` 使用 `gpt-5.5` 等待 73.444 秒后失败，错误摘要为 provider 503 `system_cpu_overloaded`。

## 当前实现状态

- 最新提交：`6521f35 Update product requirement for real model acceptance gate`，当前分支 `main` 与 `origin/main` 对齐。
- 上一轮开发提交：`8b24c8f Add real model storyboard smoke runner` 已新增 `src/vidiom/smoke.py`、`vidiom smoke-real-model-storyboard` 和 `docs/real-model-smoke-result.md`，能够按 `agent_project`、`storyboard_generation`、`project_image_generation`、`export_package` 四段记录真实 smoke 状态。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，本轮不纳入架构文档提交。
- README 已记录上一轮真实 smoke 曾通过，也记录最新真实 smoke 失败：`agent_project` 阶段 provider 503，后续三段 `incomplete`。该历史成功只能证明能力曾经走通，不能覆盖最新失败。
- `src/vidiom/smoke.py` 已有 `RealModelSmokeRun`、阶段状态集合、错误脱敏、结果 markdown 写入、fake-client 测试入口和真实 provider 调用编排。
- `src/vidiom/cli.py` 已暴露 `smoke-real-model-storyboard`，但当前命令只打印 `overall_status`，失败时是否作为发布门禁的非通过结果仍需开发收口。
- `write_smoke_result_markdown()` 当前仍写着 “Real Model Storyboard Acceptance” 和 “Task 1 real `.env` end-to-end smoke runner”，需要更新为本轮产品需求与本轮开发任务口径，避免下一轮自动化误读。
- Storyboard 存储、API、Studio 审阅、shot review、项目图像关联和导出包已具备；当前 P0 不再是缺少数据底座，而是最新真实模型链路未通过。
- 常规测试结构已覆盖 fake provider 的 smoke success、配置缺失、图像配置缺失、无效 Storyboard payload 和 KeyboardInterrupt；真实 `.env` smoke 仍必须显式手动执行，不应进入普通 pytest。

## 架构判断

现有架构已经支撑本轮产品所需的 Storyboard 领域模型、项目图像资产、导出包和显式真实 smoke runner。本轮不应把首要任务设为新增 LibTV 下游能力，也不应重写前端为无限画布。

当前阻塞发布的是验收门槛和发布状态控制：最新真实 smoke 在第一段真实语言模型调用失败，后续 Storyboard、图像和导出没有同一轮完成证据。只要 `docs/real-model-smoke-result.md` 最新总状态不是 `completed`，产品侧就不能判断真实模型接入完成。

本轮架构结论：

- 前端架构：现有静态 Studio 可支撑本轮 Storyboard 状态查看和失败提示；长期仍撑不住 LibTV 式无限画布、节点系统、资产栏、历史记录、视频/音频和导演台，后续推进这些能力前必须重构前端模块边界。本轮不启动该重构。
- 后端存储：当前 project、canvas nodes、generated image assets、storyboards、shots、story assets、shot-image links 可支撑本轮需求；不需要新增数据库迁移来解决 provider 503。若后续要长期记录 smoke 历史，可另行设计一等验收记录表，但本轮产品只要求最新验收记录可读。
- 数据模型：继续保持 Storyboard 为一等领域对象，不把 Storyboard、图像或导出结果伪装成 agent 节点长文本；失败和旧成功结果必须通过状态字段区分。
- API 边界：现有 Storyboard API 可用；本轮只允许补状态观测、错误脱敏和导出校验边界，不新增视频、音频、导演台、跨项目资产库或自由画布 API。
- 异步任务：Studio 仍可用 `BackgroundTasks`；真实 smoke runner 应保持 CLI 顺序执行和阶段记录。provider 长时间等待、失败或中断时必须留下可交接状态，不能只依赖 server log。
- Provider 抽象：继续复用 `OpenAICompatibleLanguageClient` 和 `OpenAICompatibleImageClient`。不得自动改用其他模型、备用 provider、假数据或占位结果。调用超时、自动重试、排队等待等调用策略均为“需用户确认”，不能作为本轮既定实现。
- 测试结构：常规测试继续使用 fake clients，不消耗真实模型额度；真实 `.env` smoke 作为显式验收命令，结果写入 `docs/real-model-smoke-result.md`。
- README 迭代记录：必须明确区分历史通过与最新失败，且以最新真实 smoke 结果判断当前发布状态。

## 本轮架构决策

### 1. 首要任务改为验收门禁强化，而非新增 runner

上一轮已经建立 `vidiom smoke-real-model-storyboard`。本轮开发首要任务是把它升级为真实发布门禁：

1. 最新 `docs/real-model-smoke-result.md` 是唯一真实模型接入状态判断来源。
2. `overall_status=completed` 只允许在 agent、Storyboard、项目图像和导出四段均 `completed` 且关键计数有效时出现。
3. 任一阶段为 `failed`、`interrupted` 或 `incomplete` 时，命令输出、结果文件、README 和开发交接都必须保持未通过判断。
4. CLI 应让自动化能识别失败状态；失败、interrupted 或 incomplete 不应被当作成功发布结果。
5. 结果 markdown 的产品需求名、架构任务名和阶段摘要必须更新到本轮 End-to-End Acceptance Gate，不继续写旧 Storyboard Acceptance 口径。

### 2. Provider 503 是发布阻塞，不是功能通过

最新失败来自 `gpt-5.5` provider 503 `system_cpu_overloaded`。架构上按以下规则处理：

- 503 必须记录为对应阶段 `failed`，不得写成 `completed`。
- 后续未执行阶段必须保持 `incomplete` 或等价未完成状态。
- 不得使用上一轮成功结果覆盖最新失败。
- 不得生成假 agent 输出、假 Storyboard、假图像资产或假导出包。
- 如果开发认为需要超时、重试、排队等待或验收窗口策略，只能在文档中标为“需用户确认”，不得直接实现为默认行为。

### 3. 旧成功结果与本次失败必须隔离

当前 Storyboard 层已有 `has_completed_result`、`latest_attempt_failed`、`result_source` 等语义。本轮要求把同样原则应用到真实 smoke 与 README：

- README 可保留历史真实 smoke 通过记录，但必须注明它不是最新验收。
- 最新真实 smoke 失败时，产品、架构和开发文档都不能写“真实模型接入完成”。
- 已有 completed Storyboard 可在 Studio 中显示为旧成功结果，但本次失败尝试必须可见。
- 导出包只允许包含明确存在的 completed Storyboard；未生成、失败且无旧成功结果、或本次 smoke 未完成时，不得被描述为本轮导出通过。

### 4. 前端长期架构约束

用户已明确判断当前架构撑不住 LibTV 级产品，该判断继续作为长期约束：

- 单文件 `src/vidiom/static/app.js` 只适合作为短期 Studio 壳；后续进入无限画布、自由节点、资产栏、历史记录、视频/音频和导演台前，必须拆出画布状态、节点渲染、资产面板、生成任务和审阅工作区边界。
- 本轮产品需求明确不做自由无限画布、批量分镜图、视频、音频或导演台，因此不把前端重构列为首要开发任务。
- 本轮如需改 UI，只能围绕真实 smoke/Storyboard 状态可读性、旧成功结果提示和错误脱敏做最小改动。

### 5. 后端长期数据模型方向

后端继续坚持一等领域表和清晰边界：

- 当前 project、canvas nodes、generated image assets、storyboards、storyboard_shots、project_story_assets、storyboard_shot_assets、storyboard_shot_image_assets 保持独立。
- 后续 LibTV 对齐的画布节点、视频资产、音频资产、导演台构图、生成任务历史和跨项目资产库应新增领域边界与迁移，不复用 Storyboard 表承载无关能力。
- 本轮只要求最新 smoke 结果文件可信；如未来需要多轮验收追踪，再设计 `smoke_runs`/`smoke_run_stages` 或等价结构，不在本轮预先扩张。

### 6. 测试策略

本轮开发必须保持两层验证：

- 自动化测试：fake provider 覆盖 smoke success、provider 503/错误、缺配置、无效 payload、KeyboardInterrupt、CLI 失败门禁和结果 markdown 文案。
- 真实验收：显式执行 `vidiom smoke-real-model-storyboard --result-path docs/real-model-smoke-result.md`，用真实 `.env` 调用 `gpt-5.5` 与 `gpt-image-2`，并把结果写入 README 与验收文件。

最低验证命令：

- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m pytest`
- `node --check src/vidiom/static/app.js`
- `git diff --check`
- `vidiom smoke-real-model-storyboard --result-path docs/real-model-smoke-result.md`（显式真实验收，允许失败但必须记录真实状态）

## 当前风险与控制

- 风险：CLI 失败时仍以普通成功退出，自动化无法把真实 smoke 当作发布门禁。控制：开发任务要求补 CLI/测试，使非 completed 状态可被自动化识别。
- 风险：结果文件仍写旧产品需求名，下一轮产品任务误读本轮验收对象。控制：开发任务要求更新 smoke markdown 元数据。
- 风险：README 历史通过记录掩盖最新 503。控制：README 必须按时间明确历史通过与最新失败，当前状态以最新结果为准。
- 风险：provider 503 被视为外部偶发而切换到其他 LibTV 功能。控制：最新真实 smoke 未 completed 前，下一轮仍围绕真实模型验收。
- 风险：为绕过 503 引入备用模型、假数据或占位成功。控制：本轮禁止；调用策略调整必须标为“需用户确认”。
- 风险：错误摘要泄露密钥。控制：继续复用/扩展脱敏逻辑，只记录变量名、模型名、阶段和 provider 错误摘要。

## 为什么能支撑 LibTV 对齐

LibTV 的脚本/故事板能力要求上游 shot、资产和 prompt 可信。Vidiom 当前已经有 Storyboard 领域模型和真实 smoke runner，但最新真实验收停在 `gpt-5.5` agent 阶段。若不先把最新验收门槛、失败状态和文档判断收口，后续批量分镜图、视频、音频、导演台和无限画布都会建立在未通过的模型主链路上。

因此，本轮架构控制选择先强化真实端到端验收门禁与 provider 503 发布阻塞处理。只有最新 `docs/real-model-smoke-result.md` 显示四段均 `completed`，产品侧才有依据切换到下一类 LibTV 差距。
