# Development Task Breakdown: Complete Real Model End-to-End Acceptance

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Complete Real Model End-to-End Acceptance，更新时间 2026-07-10 CST。

首要执行项：围绕最新真实 smoke 的 `storyboard_generation=interrupted` 阻塞，收口 Storyboard 真实生成生命周期、用户可读状态、同轮图像/导出复验和 README/验收文档一致性。上一轮 `vidiom smoke-real-model-storyboard` 发布门禁已完成，本轮不重复做门禁，不切换到自由无限画布、批量分镜图、视频、音频或导演台。

## Task 1: 收口 Storyboard 真实生成生命周期与中断状态

目标：让真实 `gpt-5.5` Storyboard 生成在开始、生成中、完成、失败、中断和未完成时都有一致、可交接、可测试的状态；最新中断不得被 UI、smoke、README 或导出包误写成 completed。

产品需求来源：

- 最新真实 smoke：`agent_project` completed，`storyboard_generation` interrupted，`project_image_generation` 和 `export_package` incomplete。
- Storyboard 长时间运行后被中断时，验收结果显示 interrupted 或等价中断状态，不显示 completed。
- Provider 错误、非结构化结果或任务中断时，用户和验收文档能看到失败、中断或未完成状态。
- 已有成功 Storyboard 后再次生成失败或中断，不得让用户误以为旧结果是本次成功结果。

影响文件/模块：

- `src/vidiom/storyboard.py`
- `src/vidiom/smoke.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `tests/test_storyboard.py`
- `tests/test_smoke.py`
- `tests/test_web.py`

实现步骤：

1. 审查 `run_real_model_storyboard_smoke()` 的 Storyboard 阶段，确认 KeyboardInterrupt 或外部中断只会写 `storyboard_generation=interrupted`，并把后续图像与导出标为 `incomplete`。
2. 审查 `generate_project_storyboard()` 与 `_generate_storyboard_job()`，确认 provider 异常、schema 异常和后台任务异常都会落库为 `generation_status=failed` 和脱敏错误；不要只写 server log。
3. 明确 Studio API 对运行中 Storyboard 的响应：`generation_status=generating` 时展示生成中；若后台任务失败则展示 failed；若仍有旧 completed 结果，必须说明展示的是上次成功结果。
4. 若发现当前 Storage/API 无法表达“本次中断但保留旧成功结果”，做小范围状态字段或响应字段补齐；不要重写 Storyboard 表为通用任务表。
5. 增加或调整测试，覆盖 Storyboard 阶段中断、失败保留旧结果、无旧结果失败不产生 shots、UI/API 可读状态。
6. 不要引入调用超时调整、自动重试、排队等待、验收窗口延长或人工复跑作为既定实现；如认为需要，写入 README 待处理事项并标注“需用户确认”。

验收标准：

- Storyboard 中断不会写成 completed。
- 中断后 `project_image_generation` 和 `export_package` 保持 incomplete。
- Studio 可区分未开始、生成中、成功、失败、失败但有旧成功结果；如实现了中断语义，也必须可见。
- 失败或中断不会创建假 shots、假 assets、假 image links 或假导出包。
- 旧 completed Storyboard 可继续展示，但不得被描述为本次真实 smoke 成功。
- 错误信息不包含 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY` 的实际值。

测试要求：

- `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_smoke.py tests/test_web.py`
- 如修改前端：`node --check src/vidiom/static/app.js`
- `git diff --check`

是否允许/要求重构：要求小范围重构。允许提取 Storyboard 状态判断 helper、API 响应 helper 或 smoke 阶段断言 helper；不允许前端大重构，不允许新增通用工作流引擎，不允许改用其他模型或 provider。

风险和注意事项：

- 不要把最新中断弱化为普通提示。
- 不要清空旧 completed Storyboard，除非新的 completed Storyboard 正常替换。
- 不要把旧成功结果作为本轮 smoke completed 证据。
- 不要暴露任何 secret value。

## Task 2: 强化真实 smoke 的 Storyboard 阶段可观测性

目标：让 `docs/real-model-smoke-result.md` 在 Storyboard 长耗时、中断、失败或非结构化输出时提供足够信息，供产品、架构和开发下一轮直接判断。

产品需求来源：

- 验收记录明确写入总状态、阶段状态、模型名、耗时、关键计数和错误摘要。
- 如果真实 smoke 仍失败或中断，写清失败/中断阶段和错误摘要。
- 不得用历史通过记录覆盖最新中断记录。

影响文件/模块：

- `src/vidiom/smoke.py`
- `docs/real-model-smoke-result.md`
- `README.md`
- `tests/test_smoke.py`

实现步骤：

1. 审查 `write_smoke_result_markdown()`，确认 `storyboard_generation` interrupted/failed 时会保留模型名、开始/结束时间、耗时、摘要和错误。
2. 若 Storyboard 阶段已有部分可安全记录的上下文，例如 project id、agent node count、source script/production 可用状态、已有旧 completed result 状态，可加入 `details`；不得写入 provider 原始敏感 payload。
3. 确认 `smoke_gate_completed()` 继续要求 `overall_status=completed` 且四段均 completed。
4. 增加测试断言：中断结果文件包含 interrupted、模型名、阶段名、后续 incomplete；不包含密钥值。
5. 开发完成后重新执行真实 `.env` smoke，并让 `docs/real-model-smoke-result.md` 保留最新状态。

验收标准：

- 最新 smoke 文件能直接看出 agent completed、Storyboard interrupted/failed/completed、图像与导出是否 completed。
- interrupted 和 failed 均不会让 CLI 返回通过。
- 历史 completed 记录不会覆盖最新 smoke 文件。
- 结果文件不包含 `.env` secret values。

测试要求：

- `.venv/bin/python -m pytest tests/test_smoke.py`
- `git diff --check`
- 显式真实验收：`.venv/bin/vidiom smoke-real-model-storyboard --result-path docs/real-model-smoke-result.md`

是否允许/要求重构：允许小范围重构。可以整理 smoke markdown 生成和阶段 details 组装；不得引入多轮 smoke 数据库表，除非本轮发现文件记录无法满足验收且先在 README 标为需要后续设计。

风险和注意事项：

- 真实 smoke 可能仍 interrupted；这不是通过结果，必须原样记录。
- 不要为了让文档好看而删除失败/中断摘要。
- 不要把调用窗口或人工复跑策略写成既定实现。

## Task 3: 同轮复验项目图像与导出包

目标：当 Storyboard 真实 completed 后，继续在同一轮 smoke 中完成 `gpt-image-2` 项目图像和导出包校验；如果 Storyboard 未 completed，下游必须保持 incomplete。

产品需求来源：

- 项目图像生成或复验 completed，并使用 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`。
- 导出包 completed，并包含 Storyboard metadata、shots、资产摘要和图像关联摘要。
- 后续未运行阶段显示 incomplete，不被伪造成成功。
- 常规测试不得自动消耗真实模型额度。

影响文件/模块：

- `src/vidiom/smoke.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `tests/test_smoke.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 复查 smoke 顺序：只有 Storyboard completed 且 `_ensure_storyboard_completed()` 通过后，才进入 `project_image_generation`。
2. 复查项目图像阶段，确认使用 `OpenAICompatibleImageClient.from_env()`、`HM_IMG_APIKEY` 和 `gpt-image-2`；失败时持久化 failed image asset 记录并让 smoke 阶段 failed。
3. 复查 `_validate_export_package()`，确保导出包必须包含 completed Storyboard、shots、assets、relationships、image links 摘要和至少一个项目图像资产。
4. 如果 Storyboard interrupted/failed，确认图像和导出不运行，阶段为 incomplete。
5. 增加或保留 fake provider 测试，证明成功路径四段 completed，失败路径下游 incomplete。

验收标准：

- Storyboard 未 completed 时，不生成本轮图像、不生成本轮导出 completed。
- Storyboard completed 后，项目图像阶段使用 `gpt-image-2`，并记录 image asset 状态。
- 导出包只在 completed Storyboard 存在时包含 Storyboard deliverable。
- 导出包包含 metadata、shots、assets、relations、image links 和 image asset 摘要。

测试要求：

- `.venv/bin/python -m pytest tests/test_smoke.py tests/test_storyboard.py tests/test_web.py`
- `git diff --check`

是否允许/要求重构：允许小范围重构。可以整理导出校验 helper；不得把项目图像复制成 shot 私有资产，不得新增批量分镜图。

风险和注意事项：

- 不要在 Storyboard interrupted 后继续运行图像或导出。
- 不要把历史 image asset 当作本轮 project_image_generation completed，除非 smoke 明确执行了生成或复验并记录 completed。
- 不要提交 provider 大型敏感原始 payload。

## Task 4: README 与验收文档同步

目标：让 README、`docs/real-model-smoke-result.md`、产品文档、架构文档和开发拆解对真实模型接入状态保持一致。

产品需求来源：

- README 明确区分历史真实 smoke 通过记录、上一轮 provider 503 失败和最新 Storyboard 中断记录。
- `docs/real-model-smoke-result.md` 保留最新真实验收结果。
- 产品、架构和开发文档对“真实模型接入是否完成”的判断一致。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`

实现步骤：

1. 开发完成后更新 README 迭代记录，写明本轮修改、自动化测试结果和最新真实 smoke 状态。
2. README 必须同时保留并区分：
   - 历史真实 smoke completed 记录。
   - 上一轮 provider 503 failed 记录。
   - 最新 Storyboard interrupted 或本轮重新验收后的最新状态。
3. 如果本轮真实 smoke completed，写明 agent、Storyboard、项目图像、导出四段均 completed 和关键计数。
4. 如果本轮真实 smoke 仍 failed/interrupted/incomplete，写清阶段、模型、耗时和错误摘要，不写真实模型接入完成。
5. 确认文档不包含 secret values。

验收标准：

- README 与 `docs/real-model-smoke-result.md` 的最新状态一致。
- README 不把历史通过记录写成当前发布通过。
- 文档能让下一轮产品任务直接判断是否继续围绕真实模型验收。
- 文档不包含 `HM_LLM_APIKEY`、`HM_IMG_APIKEY` 或实际密钥值。

测试要求：

- `git diff --check`
- 如修改代码同时运行对应单元测试；仅改文档时至少执行 diff whitespace 检查。

是否允许/要求重构：不要求。只做文档同步。

风险和注意事项：

- 不要删除历史记录；要明确历史记录不是最新验收。
- 不要把“门禁正确阻塞”写成“真实模型链路已完成”。
- 不要写入 `.env` 值。

## Task 5: 保持 Storyboard、项目图像和导出回归

目标：本轮聚焦真实验收阻塞，但不得让已完成的 Studio Storyboard 审阅、项目图像和导出闭环退化。

产品需求来源：

- Studio 仍可触发 Storyboard 生成并查看状态。
- 成功 Storyboard 仍能展示 shot 列表、角色/场景/道具资产摘要、prompt 准备度和审阅状态。
- 项目图像能力仍使用 `gpt-image-2`。
- 已有项目图像仍可与 Storyboard shot 建立关联。
- 成功 Storyboard 仍能进入导出包；未生成、失败或未完成的 Storyboard 不得作为成功产物导出。

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
3. 复查 image link/unlink API 只建立或删除关联，不删除项目级 image asset。
4. 复查项目图像生成 API 和 UI 仍使用 `gpt-image-2`。
5. 复查导出包在 completed Storyboard 存在时包含完整 Storyboard deliverable；无 completed Storyboard 时不得伪造。
6. 如 Task 1-4 修改影响 UI 或导出，补充回归测试。

验收标准：

- Studio 可查看 Storyboard 状态、shot 列表、资产摘要和图像关联位置。
- 每个 shot 能展示 prompt ready 和 review status。
- 已有项目图像可关联到 shot，解绑后项目图像资产仍存在。
- 成功 Storyboard 导出包包含 metadata、shots、assets、relations、image links 和 image asset 摘要。
- 未生成或只有失败/中断尝试且无旧成功结果的 Storyboard 不被导出为成功产物。

测试要求：

- `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- `node --check src/vidiom/static/app.js`
- `git diff --check`

是否允许/要求重构：不要求大重构。只允许为修复回归或整理 Storyboard 函数边界做小范围调整。

风险和注意事项：

- 本轮不做完整 shot 深度编辑、新增/删除/排序。
- 本轮不做批量分镜图、视频、音频或导演台。
- 本轮不做跨项目资产库。
