# Development Task Breakdown: Real Model Storyboard Acceptance

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Real Model Storyboard Acceptance，更新时间 2026-07-10 CST。

首要执行项：建立真实 `.env` 端到端 smoke runner 和结构化验收记录，收口长耗时、失败、中断、旧成功结果和 README 发布状态一致性。现有 Storyboard 生成、API、Studio 审阅和导出基础已存在，本轮不切换到无限画布、视频、音频、导演台或批量分镜图功能。

## Task 1: 建立真实端到端 smoke runner

目标：用一个可重复执行的命令完成真实 `gpt-5.5` agent、真实 `gpt-5.5` Storyboard、真实 `gpt-image-2` 项目图像和导出包校验，并生成可交接的验收记录。

产品需求来源：

- 真实 `.env` 配置下 agent 项目运行可完成并产生结构化脚本和拍摄包。
- Storyboard 生成使用 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`。
- `gpt-image-2` 项目图像生成可在同一轮验收中确认未退化。
- 真实 smoke 结果应能被下一轮产品任务直接读取和判断。

影响文件/模块：

- `src/vidiom/cli.py`
- `src/vidiom/storage.py`
- `src/vidiom/canvas.py`
- `src/vidiom/storyboard.py`
- `src/vidiom/providers.py`
- `docs/real-model-smoke-result.md`（新增）
- `tests/test_pipeline.py`
- `tests/test_storyboard.py`
- `tests/test_providers.py`

实现步骤：

1. 新增显式命令或脚本入口，例如 `vidiom smoke-real-model-storyboard`。命令必须读取当前 `.env`/环境变量，但不得打印 secret values。
2. 使用临时或命令参数指定的数据库路径创建项目，写入可识别的 seed 和 Brief。
3. 按真实产品链路顺序执行：
   - agent 项目运行，语言模型固定 `gpt-5.5`。
   - Storyboard 生成，语言模型固定 `gpt-5.5`。
   - 项目图像生成或复验，图像模型固定 `gpt-image-2`。
   - 导出项目包并校验 Storyboard 是否进入交付包。
4. 每个阶段记录 `stage`、`status`、`started_at`、`finished_at`、`duration_seconds`、`model`、`summary`、`error_message`。
5. 阶段状态只允许 `not_started`、`running`、`completed`、`failed`、`interrupted`、`incomplete`。
6. 捕获 `KeyboardInterrupt`、进程级中断可见异常和 provider/schema/storage/export 错误，写入 `interrupted`、`failed` 或 `incomplete`，不得写成 completed。
7. 命令结束时写入 `docs/real-model-smoke-result.md`，包含本轮真实 smoke 总状态、各阶段状态、模型名、shot 数、asset 数、image asset 状态、导出校验结果和错误摘要。
8. 如某阶段未完成，后续阶段应记录为 `not_started` 或 `incomplete`，不得自动补假数据继续写通过。

验收标准：

- 开发可用一个命令复验真实 agent -> Storyboard -> image -> export 链路。
- 缺少 `HM_BASE_URL`、`HM_LLM_APIKEY` 或 `HM_IMG_APIKEY` 时，smoke 结果明确失败阶段和变量名，不暴露密钥值。
- provider 长时间等待被中断时，结果文件显示 interrupted/incomplete，不显示成功。
- 成功时结果文件包含 agent 5/5、Storyboard shot/asset 计数、image asset completed 和导出包 Storyboard 校验结果。
- 失败时不会生成占位 Storyboard、假 shot、假 image asset 或假成功导出。

测试要求：

- 单元测试使用 fake provider clients 覆盖 success、provider error、invalid storyboard payload、missing config 和 interrupted 状态记录。
- 测试结果文件格式，确保下一轮产品任务可读取阶段和总状态。
- 运行 `.venv/bin/python -m pytest tests/test_pipeline.py tests/test_storyboard.py tests/test_providers.py`。

是否允许/要求重构：要求小范围重构。可以抽出 smoke orchestration helper，但不得引入通用任务系统或备用 provider 机制作为本轮前置。

风险和注意事项：

- 不要在普通 pytest 中自动调用真实模型。
- 不要打印或提交 `.env` secret values。
- 不要引入备用模型、假数据、占位结果或默认降级路径。
- 如开发认为需要 provider 调用超时策略，只能在 README/结果文件中标为“需用户确认”，不得直接写成既定实现。

## Task 2: 收口长耗时、失败和中断状态记录

目标：让真实 provider 等待、失败或人工中断时，产品和验收文档都能清楚说明当前处于哪个阶段，而不是空白或假成功。

产品需求来源：

- 长时间等待时，用户不会看到假成功状态。
- Provider 返回错误、非结构化结果或任务被中断时，Storyboard 进入可理解的失败或未完成状态。
- 已有成功 Storyboard 后再次生成失败，不得让用户误以为旧结果是本次成功结果。
- README 或等价迭代记录明确写入真实 smoke 是否可重复通过；若复验未通过，写明发生阶段。

影响文件/模块：

- `src/vidiom/web.py`
- `src/vidiom/storage.py`
- `src/vidiom/storyboard.py`
- `src/vidiom/static/app.js`
- `docs/real-model-smoke-result.md`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 审查现有 Storyboard API，确认 `generation_status`、`generation_error_message`、`has_completed_result`、`latest_attempt_failed`、`result_source` 已能表达旧成功结果与本次失败的关系。
2. 如 API 缺少字段或前端未展示字段，补齐最小响应和文案，不做新的 Storyboard 深度编辑器。
3. 在 smoke runner 中为 agent、Storyboard、image、export 四段都记录状态；agent provider 长时间等待被中断时，总状态必须是 `interrupted` 或 `incomplete`。
4. 检查 `_run_project_job` 与 `_generate_storyboard_job`，确保后台异常会落库失败状态或项目 activity；不能只写日志。
5. 错误脱敏统一复用或扩展现有 sanitise 逻辑，错误消息只保留阶段、变量名、模型名和 provider 错误摘要。
6. README 和 smoke 结果中解释：上一轮真实 smoke 曾通过，本轮独立复验在语言 agent provider 阶段超过三分钟被中断；本轮开发后的结果以新的 smoke 记录为准。

验收标准：

- Storyboard 生成中、失败、失败但有旧成功结果，在 API 和 Studio 中都可区分。
- smoke 结果文件可明确标出 agent provider 等待中断，不会被后续任务误读为通过。
- 错误消息不包含 `HM_LLM_APIKEY`、`HM_IMG_APIKEY` 或实际 key 值。
- 后台 job 异常不只停留在 server log，至少能在 project/storyboard 状态或 smoke 文件中被读取。

测试要求：

- `tests/test_web.py` 覆盖 Storyboard 失败但保留旧结果的 API 响应和前端标记。
- 新增或更新测试覆盖 smoke interrupted/incomplete 状态。
- 运行 `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`。

是否允许/要求重构：允许小范围重构。状态记录可抽 helper；不得启动完整异步任务队列改造。

风险和注意事项：

- 不要把旧 completed shots 当作本次 failed attempt 的成功产物。
- 不要在 UI 或导出中伪造没有生成过的 Storyboard。
- 不要为了规避等待问题自动换模型或换 provider。

## Task 3: 回归验证 Storyboard 审阅、图像关联和导出闭环

目标：确认上一轮已实现的 Storyboard Studio 工作区、shot 审阅、项目图像关联和导出包没有因真实 smoke 收口而退化。

产品需求来源：

- 用户可查看 Storyboard 状态、shot 列表、资产摘要和图像关联位置。
- 每个 shot 能展示 prompt 准备度和审阅状态。
- 成功 Storyboard 会进入导出包。
- 导出包包含 shots、资产摘要和图像关联摘要。
- 现有 `gpt-image-2` 项目图像生成继续可用。

影响文件/模块：

- `src/vidiom/web.py`
- `src/vidiom/storage.py`
- `src/vidiom/static/index.html`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_web.py`
- `tests/test_storyboard.py`

实现步骤：

1. 复查 `GET /api/projects/{project_id}/storyboard` 返回是否包含 shots、assets、relationships、image_links 和 project image_assets 摘要。
2. 复查 `PATCH /api/projects/{project_id}/storyboard/shots/review` 能保存 `review_status` 和 `prompt_ready`。
3. 复查 image link/unlink API 只建立关联，不复制或删除项目级 image asset。
4. 复查导出包在 `has_completed_result=true` 时包含 Storyboard metadata、shots、assets、relations、image links 和 image asset 摘要。
5. 复查未生成、失败且无旧成功结果的项目不会导出 fake Storyboard。
6. 复查 Delivery 页和 README 的描述与实际导出字段一致。

验收标准：

- Studio 可查看 Storyboard shot 核心字段、prompt readiness、review status、assets 和 image links。
- 已有项目图像可关联到 shot，解绑后项目图像资产仍存在。
- 成功 Storyboard 导出包包含完整摘要。
- 未生成或只有失败尝试的 Storyboard 不被导出为成功产物。
- 项目图像生成 API 和 UI 仍使用 `gpt-image-2`，入口不被隐藏。

测试要求：

- 运行 `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`。
- `node --check src/vidiom/static/app.js`。
- 如前端文案或标记变化，更新静态 smoke 测试。

是否允许/要求重构：不要求大重构。只允许为修复回归或整理 Storyboard 函数边界做小范围调整。

风险和注意事项：

- 本轮不做完整 shot 深度编辑、新增/删除/排序。
- 不做批量分镜图、视频、音频或导演台。
- 不把项目图像资产迁移为 shot 私有资产。

## Task 4: README 与验收文档同步

目标：把“自动化测试状态、真实 `.env` smoke 状态、独立复验超时事实、当前发布判断”写清楚，避免产品、架构和开发任务读取到互相冲突的状态。

产品需求来源：

- 文档应明确哪些能力已在自动化测试中通过。
- 文档应明确哪些能力已在真实 `.env` smoke 中通过。
- 若真实 smoke 未通过，失败或超时发生在哪个产品阶段。
- README 通过记录与本轮复验超时之间的产品解释。
- 架构师下一轮交给开发的任务是否基于最新提交继续收口。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- `docs/product-gap-analysis.md`（如开发结果改变产品事实，可供下一轮产品任务更新）
- `docs/architecture-control-plan.md`（本文件由架构师维护，开发不应随意改写架构判断）
- `docs/development-task-breakdown.md`（本文件由架构师维护，开发只按任务执行）

实现步骤：

1. README 迭代记录新增本轮开发条目，写明本轮目标是 Real Model Storyboard Acceptance，而不是新 LibTV 功能。
2. README 记录自动化验证命令和结果：
   - `.venv/bin/python -m ruff check .`
   - `.venv/bin/python -m pytest`
   - `node --check src/vidiom/static/app.js`
3. README 记录真实 smoke 命令和结果；如未通过，必须写具体阶段、状态和错误摘要。
4. `docs/real-model-smoke-result.md` 保持结构化、短而可读，下一轮产品任务能直接判断总状态。
5. 如果真实 smoke 仍因 provider 长时间等待未完成，README 不得写“真实端到端通过”；只能写明未完成阶段和下一步需要用户或 provider 侧确认的事项。

验收标准：

- README 明确区分自动化测试通过和真实模型 smoke 通过/未通过。
- README 解释上一轮通过记录与本轮复验超时不是同一次验收。
- `docs/real-model-smoke-result.md` 存在且包含本轮 run timestamp、总状态、阶段状态和关键计数。
- 文档不包含 secret values。

测试要求：

- 文档变更后运行 `git diff --check`。
- 若 README 中记录命令结果，必须先真实执行对应命令或明确写未执行原因。

是否允许/要求重构：不涉及代码重构。

风险和注意事项：

- 不要把未完成 smoke 写成成功。
- 不要删除上一轮真实 smoke 通过记录；应增加本轮复验解释。
- 不要让开发自行改写产品需求或架构结论来规避验收。

## Task 5: 完整回归与真实验收执行

目标：在开发完成后，用自动化测试和真实 `.env` smoke 同时证明本轮需求是否可发布，并把结果留给下一轮产品/架构任务读取。

产品需求来源：

- 自动化检查继续通过。
- 现有 agent、项目图像生成、项目创建、运行、暂停、修订、Review 编辑、交付导出保持可用。
- README 或等价迭代记录明确写入真实 smoke 是否可重复通过；若复验未通过，写明发生阶段。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- 全部 `src/vidiom/**`
- 全部 `tests/**`

实现步骤：

1. 运行 `.venv/bin/python -m ruff check .`。
2. 运行 `.venv/bin/python -m pytest`。
3. 运行 `node --check src/vidiom/static/app.js`。
4. 使用真实 `.env` 执行 Task 1 新增 smoke 命令。
5. 核对 smoke 结果：
   - agent 是否 5/5 completed。
   - Storyboard 是否 completed，shot 数和 asset 数是否大于 0。
   - image asset 是否 completed 或失败状态可解释。
   - 导出包是否包含成功 Storyboard 的 metadata、shots、assets、relations、image links。
6. 将验证结果写入 README 和 `docs/real-model-smoke-result.md`。
7. 提交时确保 `.env`、临时数据库、生成图片 payload 和 secret values 没有进入 git。

验收标准：

- 自动化测试全部通过，或 README 明确记录失败命令和失败原因。
- 真实 smoke 完整通过时，文档可直接支持下一轮产品切换到下一个 LibTV 缺口。
- 真实 smoke 未通过时，文档可直接说明阻塞阶段，下一轮仍继续收口模型验收。
- `git status` 中只包含应提交的代码和文档变更。

测试要求：

- 完整执行 ruff、pytest、node check。
- 真实 smoke 执行结果必须进入文档。

是否允许/要求重构：不要求。只允许为修复回归或使验收命令可执行做必要小改。

风险和注意事项：

- 不要提交 `.env`、临时数据库或 provider 返回的大型敏感 payload。
- 不要把视频、音频、导演台、自由无限画布或跨项目资产库写成本轮已完成能力。
- 不要新增备用策略；如需讨论调用超时策略，必须标为“需用户确认”。
