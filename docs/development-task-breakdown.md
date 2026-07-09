# Development Task Breakdown: Real Model End-to-End Acceptance Gate

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Real Model End-to-End Acceptance Gate，更新时间 2026-07-10 CST。

首要执行项：在已存在 `vidiom smoke-real-model-storyboard` 和 `docs/real-model-smoke-result.md` 基础上，收口真实端到端验收门禁、provider 503 发布阻塞、旧成功记录隔离和 README/验收文档一致性。现有 Storyboard 数据底座、Studio 审阅、项目图像和导出包能力已存在，本轮不切换到自由无限画布、批量分镜图、视频、音频或导演台。

## Task 1: 强化真实 smoke 发布门禁

目标：让 `vidiom smoke-real-model-storyboard` 成为可被自动化和人工共同识别的真实模型发布门禁；最新真实 smoke 只要不是四段 completed，就不能被当作真实模型接入完成。

产品需求来源：

- `docs/real-model-smoke-result.md` 总状态为 completed 且四个核心阶段均 completed，才满足真实模型链路验收。
- Provider 返回 503 时，验收结果显示对应阶段 failed，不显示 completed。
- 后续未运行阶段显示 incomplete 或等价未完成状态，不被伪造成成功。
- README 明确区分历史真实 smoke 通过记录和最新真实 smoke 结果。

影响文件/模块：

- `src/vidiom/cli.py`
- `src/vidiom/smoke.py`
- `docs/real-model-smoke-result.md`
- `README.md`
- `tests/test_smoke.py`

实现步骤：

1. 审查 `run_real_model_storyboard_smoke()` 的总状态计算，确保只有 `agent_project`、`storyboard_generation`、`project_image_generation`、`export_package` 四段全部 `completed` 时才写入 `overall_status=completed`。
2. 更新 `write_smoke_result_markdown()` 的元数据文案：
   - Product requirement 改为 `Real Model End-to-End Acceptance Gate`。
   - Architecture task 改为本文件 Task 1 “强化真实 smoke 发布门禁”。
   - 如果仍保留命令名 `smoke-real-model-storyboard`，文案需说明它覆盖 agent、Storyboard、项目图像和导出四段端到端验收。
3. 调整 `vidiom smoke-real-model-storyboard` CLI 行为，使 `overall_status` 为 `failed`、`interrupted` 或包含 `incomplete` 阶段时能被自动化识别为未通过。不要改变结果文件写入要求。
4. 保留失败时结果文件写入：即使命令返回未通过状态，`docs/real-model-smoke-result.md` 仍必须包含 run timestamp、总状态、阶段状态、模型名、耗时、关键计数和错误摘要。
5. 增加测试覆盖 CLI/runner 未通过状态，确保 provider 503 或 fake provider error 不会被命令层当作通过。
6. 确认 `docs/real-model-smoke-result.md` 最新内容仍记录当前真实 503 失败，而不是上一轮历史通过。

验收标准：

- 成功路径：四段均 completed 时，结果文件总状态为 `completed`，包含 agent 节点计数、Storyboard shot/asset 计数、项目图像状态和导出校验计数。
- 失败路径：provider 503 时，`agent_project` 为 `failed`，后三段为 `incomplete`，总状态为 `failed`。
- 命令层：真实 smoke 未 completed 时，自动化可以判断本次验收未通过。
- 结果文件：Product requirement 与 Architecture task 指向本轮 End-to-End Acceptance Gate，不再使用旧 Storyboard Acceptance 口径。
- 文档不包含 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY` 的值。

测试要求：

- `.venv/bin/python -m pytest tests/test_smoke.py`
- 新增或更新 CLI 测试时，覆盖 completed 与 failed 两类命令结果。
- `git diff --check`

是否允许/要求重构：要求小范围重构。可以抽出 CLI 状态判断 helper 或 smoke result 判定 helper；不得引入备用模型、备用 provider、假数据或默认降级路径。

风险和注意事项：

- 不要把 provider 503 写成通过。
- 不要用上一轮历史通过记录覆盖最新失败记录。
- 不要因为命令返回未通过而跳过结果文件写入。
- 调用超时、自动重试、排队等待等策略如需讨论，必须标为“需用户确认”，不要直接实现。

## Task 2: 收口 provider 503、配置缺失和错误脱敏语义

目标：让用户、README 和下一轮自动化都能清楚看到失败阶段、模型名、配置变量名或 provider 错误摘要，同时不泄露密钥值，也不弱化 provider 503 的发布阻塞含义。

产品需求来源：

- Provider 503 应显示为真实失败或发布阻塞，不得被弱化为普通提示。
- 缺少 `HM_BASE_URL`、`HM_LLM_APIKEY` 或 `HM_IMG_APIKEY` 时，对应阶段进入可见失败状态。
- Provider 错误、非结构化结果或任务中断时，用户和验收文档能看到失败或未完成状态。
- 错误信息不得包含密钥值。

影响文件/模块：

- `src/vidiom/smoke.py`
- `src/vidiom/storyboard.py`
- `src/vidiom/providers.py`
- `src/vidiom/web.py`
- `tests/test_smoke.py`
- `tests/test_providers.py`
- `tests/test_web.py`

实现步骤：

1. 审查 `sanitize_smoke_error()` 与 `sanitize_storyboard_error()`，确认 provider 异常、配置异常和 schema 异常都会替换环境变量实际值，仅保留变量名。
2. 增加 fake provider 503 测试，断言错误摘要保留 `503` 和 `system_cpu_overloaded`，但不包含任何密钥值。
3. 确认缺少 `HM_BASE_URL`、`HM_LLM_APIKEY` 时失败落在 `agent_project`；缺少 `HM_IMG_APIKEY` 时失败落在 `project_image_generation`，并且后续阶段为 `incomplete`。
4. 确认非结构化 Storyboard payload 失败落在 `storyboard_generation`，不继续生成项目图像或导出包。
5. 确认 KeyboardInterrupt 或等价中断会写 `interrupted`，后续阶段写 `incomplete`。
6. 审查 Studio Storyboard API 失败语义：后台 Storyboard 失败应落库 `generation_status=failed` 和脱敏错误；不要只写 server log。

验收标准：

- provider 503 在 smoke 文件中显示为对应阶段 `failed` 和发布阻塞摘要。
- 配置缺失能显示变量名，但不显示变量值。
- 非结构化模型输出不会产生假 Storyboard。
- 中断不会写成成功或 completed。
- Storyboard UI/API 仍能区分生成中、失败、失败但有旧成功结果。

测试要求：

- `.venv/bin/python -m pytest tests/test_smoke.py tests/test_providers.py tests/test_web.py`
- 如修改前端状态展示，运行 `node --check src/vidiom/static/app.js`。

是否允许/要求重构：允许小范围重构。可统一错误脱敏 helper；不得改变 provider 模型选择，不得自动改用其他模型或 provider。

风险和注意事项：

- 不要截断掉 provider 错误中用于判断 503 的关键信息。
- 不要把配置缺失解释为普通未开始状态。
- 不要暴露 `.env` 中任何实际值。

## Task 3: 隔离旧成功结果与本次真实验收结果

目标：确保上一轮真实 smoke 通过记录、已有 completed Storyboard、最新失败 smoke 三者在 README、Studio 和导出语义中不会互相覆盖。

产品需求来源：

- 已有成功 Storyboard 后再次生成失败，不得让用户误以为旧结果是本次成功结果。
- 不得用上一轮历史通过记录覆盖最新失败记录。
- 成功 Storyboard 仍能进入导出包；未生成、失败或未完成的 Storyboard 不得作为成功产物导出。
- README 明确区分历史真实 smoke 通过记录和最新真实 smoke 结果。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `README.md`
- `docs/real-model-smoke-result.md`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 复查 `get_project_storyboard()` 返回字段：`has_completed_result`、`latest_attempt_failed`、`result_source` 必须能表达“本次失败但保留旧结果”。
2. 复查导出逻辑：只有 `has_completed_result=true` 时才把 Storyboard 放入 deliverables；失败且无旧成功结果时不得导出 Storyboard。
3. 复查 Studio 故事板页：`generation_status=failed` 且 `has_completed_result=true` 时，必须说明下面展示的是上次成功结果。
4. 复查 Delivery 页：Storyboard 汇总只能基于 `has_completed_result`，不能把失败尝试当作本次通过。
5. README 最新迭代记录必须说明：历史通过记录存在，但最新真实 `.env` smoke 总状态为 failed，失败阶段为 `agent_project`。
6. 如发现 UI 或导出文案容易混淆“历史成功”和“最新验收成功”，做最小修正。

验收标准：

- 已有 completed Storyboard 后再次失败，Studio 可见失败状态并保留旧 shots。
- 旧项目没有 Storyboard 时，界面和导出包不会伪造 Storyboard。
- 导出包只包含明确存在的 completed Storyboard，并带有 metadata、shots、assets、relations、image links 和 image asset 摘要。
- README 不把历史通过记录写成当前发布通过。

测试要求：

- `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- `node --check src/vidiom/static/app.js`

是否允许/要求重构：允许极小范围重构。不得做完整 shot 深度编辑器、新增/删除/排序功能或资产库迁移。

风险和注意事项：

- 不要清空旧 completed shots，除非新的 completed Storyboard 正常替换。
- 不要让 Delivery 页在最新真实 smoke failed 时暗示端到端已通过。
- 不要把项目图像资产迁移为 shot 私有资产。

## Task 4: 真实端到端回归验收

目标：在开发完成后，用自动化测试和真实 `.env` smoke 共同证明当前版本状态；如果真实 smoke 仍因 provider 503 失败，文档必须清楚保留失败事实。

产品需求来源：

- 自动化检查继续通过。
- 使用真实 `.env` 配置时，agent、Storyboard、项目图像和导出包必须同一轮 completed 才算真实模型链路完成。
- 如果真实 smoke 仍失败，写清失败阶段和错误摘要。
- 常规测试不得自动消耗真实模型额度。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- 全部 `src/vidiom/**`
- 全部 `tests/**`

实现步骤：

1. 运行 `.venv/bin/python -m ruff check .`。
2. 运行 `.venv/bin/python -m pytest`。
3. 运行 `node --check src/vidiom/static/app.js`。
4. 运行 `git diff --check`。
5. 显式执行真实验收命令：`vidiom smoke-real-model-storyboard --result-path docs/real-model-smoke-result.md`。
6. 如果真实 smoke completed，核对：
   - agent 5/5 completed。
   - Storyboard completed，shot 数和 asset 数大于 0。
   - project image generation completed，使用 `gpt-image-2`。
   - export_package completed，包含 completed Storyboard metadata、shots、assets、relations、image links 和 image asset 摘要。
7. 如果真实 smoke failed/interrupted/incomplete，保留最新失败结果，不写真实端到端通过。
8. 更新 README 迭代记录，写明自动化测试结果和最新真实 smoke 状态。

验收标准：

- 自动化检查通过，或 README 明确记录失败命令和失败原因。
- `docs/real-model-smoke-result.md` 包含最新 run timestamp、总状态、阶段状态、模型名、关键计数和错误摘要。
- README 与 `docs/real-model-smoke-result.md` 对真实模型接入是否完成的判断一致。
- 文档不包含 secret values。

测试要求：

- 完整执行本任务实现步骤中的所有自动化命令。
- 真实 `.env` smoke 只通过显式命令执行，不加入普通 pytest。

是否允许/要求重构：不要求。只允许为修复验收命令、结果记录或文档一致性做必要小改。

风险和注意事项：

- 不要提交 `.env`、临时数据库或 provider 返回的大型敏感 payload。
- 不要把视频、音频、导演台、自由无限画布或跨项目资产库写成本轮已完成能力。
- 如果 provider 继续返回 503，本轮开发结果可以是“门禁正确阻塞并记录失败”，不能写成真实模型接入完成。

## Task 5: 保持 Storyboard、项目图像和导出回归

目标：本轮虽然聚焦验收门禁，但不能让上一轮已经完成的 Storyboard 审阅、项目图像和导出闭环退化。

产品需求来源：

- Studio 仍可触发 Storyboard 生成并查看状态。
- 成功 Storyboard 仍能展示 shot 列表、角色/场景/道具资产摘要、prompt 准备度和审阅状态。
- 项目图像能力仍使用 `gpt-image-2`。
- 已有项目图像仍可与 Storyboard shot 建立关联。
- 成功 Storyboard 仍能进入导出包。

影响文件/模块：

- `src/vidiom/web.py`
- `src/vidiom/storage.py`
- `src/vidiom/static/index.html`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 复查 `GET /api/projects/{project_id}/storyboard` 返回 shots、assets、relationships、image_links 和 project image_assets 摘要。
2. 复查 `PATCH /api/projects/{project_id}/storyboard/shots/review` 能保存 `review_status` 和 `prompt_ready`。
3. 复查 image link/unlink API 只建立关联，不复制或删除项目级 image asset。
4. 复查项目图像生成 API 和 UI 仍使用 `gpt-image-2`。
5. 复查导出包在 completed Storyboard 存在时包含完整 Storyboard deliverable。
6. 如 Task 1-4 修改影响 UI 或导出，补充回归测试。

验收标准：

- Studio 可查看 Storyboard 状态、shot 列表、资产摘要和图像关联位置。
- 每个 shot 能展示 prompt ready 和 review status。
- 已有项目图像可关联到 shot，解绑后项目图像资产仍存在。
- 成功 Storyboard 导出包包含 metadata、shots、assets、relations、image links 和 image asset 摘要。
- 未生成或只有失败尝试且无旧成功结果的 Storyboard 不被导出为成功产物。

测试要求：

- `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- `node --check src/vidiom/static/app.js`

是否允许/要求重构：不要求大重构。只允许为修复回归或整理 Storyboard 函数边界做小范围调整。

风险和注意事项：

- 本轮不做完整 shot 深度编辑、新增/删除/排序。
- 不做批量分镜图、视频、音频或导演台。
- 不做跨项目资产库。
