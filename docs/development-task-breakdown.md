# Development Task Breakdown: Real Model Storyboard Generation

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Real Model Storyboard Generation，更新时间 2026-07-10 CST。

首要执行项：先补 Storyboard 生成尝试状态与真实 `gpt-5.5` 生成 API，再接 Studio 审阅和导出回归。现有 Storyboard 存储底座可复用，但当前缺少真实模型生成器、API、前端入口和“已有成功结果后本次失败”的状态语义。

## Task 1: 完善 Storyboard 生成状态模型

目标：让系统能同时表达最新生成尝试状态和最后一次成功 Storyboard 结果，避免用户把旧结果误认为本次生成成功。

产品需求来源：

- 可见生成状态与错误状态：未生成、生成中、成功、失败和已有结果状态必须可区分。
- 如果项目已有成功 Storyboard，再次生成失败时，不得让用户误以为旧结果是本次成功结果。
- 失败时不得生成占位 shot、假成功 Storyboard 或静默成功。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/storyboard_schema.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`
- `README.md`

实现步骤：

1. 在 `storyboards` 表增加 generation attempt 语义，可用字段包括 `generation_status`、`generation_started_at`、`generation_finished_at`、`generation_error_message`、`last_completed_at`、`last_completed_model`；如采用等价字段命名，必须在代码和测试中保持清晰。
2. 迁移必须幂等，旧库已有 `storyboards.status`、shots、assets、relations 和 image links 时不得丢失数据。
3. 调整 `get_or_create_project_storyboard()`、`update_project_storyboard_status()`、`replace_project_storyboard()` 和 `get_project_storyboard()`，让查询响应明确包含：
   - 当前 generation status。
   - 错误信息。
   - 是否存在 completed result。
   - shots/assets/relations/image links 是否来自最后一次成功结果。
4. 已有 completed result 后记录 failed attempt 时，不删除 shots/assets/relations。
5. 导出包只导出明确存在的 completed Storyboard 结果，并包含 generation metadata；如果 latest attempt failed 但保留旧结果，导出 metadata 必须标明 latest attempt 状态。
6. 写入 `project_events`，事件能区分 generation started、completed、failed。

验收标准：

- 空库迁移后具备新增状态字段或等价结构。
- 上一轮已保存的 completed storyboard 迁移后仍可读取和导出。
- 已有 completed result 后写入 failed attempt，GET API/storage 读取能同时看到 failed attempt 与 retained completed result。
- 失败 attempt 不产生新 shots，不清空旧 shots。

测试要求：

- Storage migration 测试覆盖旧 schema 到新 schema。
- Storage 测试覆盖 completed 后 failed attempt 的读取和导出语义。
- 运行 `.venv/bin/python -m pytest tests/test_storyboard.py`。

是否允许/要求重构：要求。该任务是本轮真实生成 API 的前置状态模型改造。

风险和注意事项：

- 不要把 failed attempt 写成 completed。
- 不要新增备用生成器、文本拆段占位结果或默认降级路径。
- 不要改变项目级 `generated_image_assets` 的归属语义。

## Task 2: 接入真实 `gpt-5.5` Storyboard 生成器与 API

目标：用户可从 completed 项目触发真实模型 Storyboard 生成，生成输入覆盖项目上下文，成功结果持久化，失败结果可见。

产品需求来源：

- Storyboard 生成使用 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`。
- 生成输入覆盖 seed、Brief、Premise、Character、Beat、Script、Production 和已有图像资产摘要。
- 成功结果包含多个结构化 shot。
- 缺少配置、provider 错误或非结构化结果进入可见失败状态。

影响文件/模块：

- `src/vidiom/storyboard.py`
- `src/vidiom/storyboard_schema.py`
- `src/vidiom/providers.py`
- `src/vidiom/config.py`
- `src/vidiom/web.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 `web.py` 增加 `get_language_client()` 依赖，返回 `OpenAICompatibleLanguageClient.from_env()`。
2. 在 `storyboard.py` 新增 `StoryboardContextBuilder`，从 `storage.get_project(project_id)` 提取：
   - project seed/title/brief。
   - Premise、Character、Beat、Script、Production 节点输出。
   - Review 编辑后的脚本和拍摄包结果。
   - `project["image_assets"]` 中 prompt、model、status、artifact metadata 摘要。
3. 在 `storyboard.py` 新增 `OpenAIStoryboardGenerator` 或等价函数，调用 `LanguageJSONClient.generate_json(model="gpt-5.5", schema_name="storyboard", schema=STORYBOARD_SCHEMA, ...)`。
4. 生成前校验项目必须为 `completed`，Script 和 Production 必须有可用输出；不满足时返回 400，不写入假 storyboard。
5. 新增 `POST /api/projects/{project_id}/storyboard/generate`：
   - 受理后写入 `generating`。
   - 使用 `BackgroundTasks` 执行 provider 调用。
   - 返回当前 project/storyboard 响应。
6. 新增后台 job helper，例如 `_generate_storyboard_job(database_path, project_id, model)`，job 内重新创建 storage 和真实 client。
7. 成功时调用 `replace_project_storyboard()` 写入 shots/assets/relations，状态为 completed。
8. 失败时写入 failed attempt 和 sanitised error message；不得清空最后成功结果，不得写入 placeholder shot。
9. 新增 `GET /api/projects/{project_id}/storyboard` 返回状态、shots、assets、relationships、image_links、image_assets 摘要。

验收标准：

- completed 项目可触发 Storyboard 生成。
- fake language client 测试证明模型名为 `gpt-5.5`。
- 生成上下文测试证明包含 seed、Brief、agent outputs 和 image assets。
- provider 成功后刷新仍可读取多个结构化 shot。
- 缺少 `HM_BASE_URL` 或 `HM_LLM_APIKEY` 时进入 failed 状态，错误不包含密钥值。
- provider 返回非结构化结果时进入 failed 状态，不产生占位 shots。

测试要求：

- `tests/test_storyboard.py` 覆盖 context builder、generator success、generator invalid payload、provider exception。
- `tests/test_web.py` 覆盖 GET/POST storyboard API、非 completed 项目拒绝、后台成功和后台失败。
- 运行 `.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`。

是否允许/要求重构：允许。可以抽出 storyboard job helper，但不引入通用任务系统作为本轮前置条件。

风险和注意事项：

- 不要复用 `OpenAICanvasAgent` 的固定节点 schema 作为 Storyboard 输出 schema。
- 不要要求项目必须已有图像资产；有则纳入上下文，没有则正常生成。
- 不要打印或提交 `.env` secret values。

## Task 3: 提供最小 Storyboard 审阅与图像关联 API

目标：让 Studio 能保存用户对 shot 审阅状态和 prompt 准备度的判断，并能把已有项目图像资产关联到 shot。

产品需求来源：

- 用户可查看每个 shot 的审阅状态和 prompt 准备度。
- 用户可查看 shot 与已有图像资产的关联位置。
- 导出包包含 Storyboard 摘要、shots、项目内资产摘要和图像关联摘要。

影响文件/模块：

- `src/vidiom/web.py`
- `src/vidiom/storage.py`
- `src/vidiom/storyboard_schema.py`
- `tests/test_web.py`
- `tests/test_storyboard.py`

实现步骤：

1. 新增 Pydantic 请求模型：`StoryboardShotReviewRequest`，包含 `shot_id`、`review_status`、`prompt_ready`。
2. 新增 `PATCH /api/projects/{project_id}/storyboard/shots/review`，支持批量更新 review status 和 prompt_ready。
3. 后端校验 shot 属于当前 project，`review_status` 只允许 `pending`、`needs_changes`、`approved`。
4. 如果 `prompt_ready=true`，对应 shot 的 `image_prompt` 必须非空。
5. 新增或暴露 link/unlink API：
   - `POST /api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}`
   - `DELETE /api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}`
6. 校验 shot 和 image asset 属于同一 project，link type 只允许 `reference`、`storyboard_frame`。
7. 更新 project event：`storyboard_review`、`storyboard_image_link`。

验收标准：

- 用户可把 shot 标记为 pending、needs_changes、approved。
- 用户可修正 prompt_ready 并刷新保持。
- 已有项目图像资产可绑定到指定 shot。
- 解除绑定后 image asset 仍保留在项目图像列表。
- 跨项目 shot/image 绑定被拒绝。

测试要求：

- Web API 测试覆盖审阅状态更新、prompt_ready 校验、link/unlink、跨项目拒绝。
- Storage 测试覆盖删除 link 不删除 `generated_image_assets`。

是否允许/要求重构：允许。更新逻辑应落在 storage/storyboard helper，不要在 Web handler 中拼复杂 SQL。

风险和注意事项：

- 本轮不做完整 shot 深度编辑器、新增/删除/排序 UI，除非开发完成 P0 后仍有余量。
- 不要把 image asset 复制进 shot 记录；只通过关联表引用。

## Task 4: Studio 接入 Storyboard 生成和审阅视图

目标：在 Studio 中提供真实可用的 Storyboard 工作区，让用户触发生成、观察状态、检查 shots/assets/image links，并完成最小审阅。

产品需求来源：

- 用户可从 Studio 进入 Storyboard 视图或等价工作区。
- 用户可查看 Storyboard 状态、shot 列表、资产摘要和图像关联位置。
- 生成中、成功、失败和旧结果状态应清晰区分。
- 现有 `gpt-image-2` 项目图像能力不能被隐藏或破坏。

影响文件/模块：

- `src/vidiom/static/index.html`
- `src/vidiom/static/app.js`，或新增 `src/vidiom/static/storyboard.js`
- `src/vidiom/static/styles.css`
- `tests/test_web.py`
- `README.md`

实现步骤：

1. Review tab 增加 `storyboard`，显示为“故事板”。
2. 前端状态新增 `storyboard`、`storyboardLoading`、`storyboardGenerating`、`storyboardReviewDraft`、`selectedStoryboardShotId`。
3. 进入 Storyboard tab 时调用 `GET /api/projects/{id}/storyboard`。
4. completed 项目显示“生成故事板”入口；非 completed 项目说明需先完成 agent。
5. 生成请求调用 `POST /api/projects/{id}/storyboard/generate`，生成中显示明确状态并轮询项目或 storyboard 状态。
6. 失败状态显示错误摘要；如果存在旧成功结果，明确标注“本次生成失败，下面是上次成功结果”。
7. 成功状态显示 shot 列表：顺序、beat、角色、场景、道具、画面、动作、对白/声音、时长、视觉要求、image prompt、prompt_ready、review_status、image link 数。
8. 资产区显示 character、scene、prop 摘要和出现 shot。
9. 图像关联区展示项目 image assets，并允许把已有 image asset 绑定/解绑到选中 shot。
10. Delivery/导出页补充 Storyboard 计数：shots、approved、prompt_ready、assets、image_links。
11. 若继续使用单文件 `app.js`，Storyboard 相关函数必须集中命名和分区；如拆 `storyboard.js`，保持无需构建即可运行。

验收标准：

- 完成项目可从 Studio 进入 Storyboard 视图并触发生成。
- 生成中状态可见。
- 成功后可查看多个结构化 shot 和资产摘要。
- 失败时显示绑定到 Storyboard 的错误，不显示空白成功态。
- 旧项目没有 Storyboard 时不伪造内容。
- 项目图像页和现有图像生成入口仍可用。

测试要求：

- 静态前端 smoke 测试检查 Storyboard tab、生成入口、状态文案、shot list、asset summary、image link UI 标记存在。
- Web API 回归测试确认 `/api/projects/{project_id}/images` 和导出仍通过。

是否允许/要求重构：要求形成 Storyboard 前端逻辑边界。允许拆静态模块；不得引入构建链路作为本轮前置条件。

风险和注意事项：

- 不要把 Storyboard 呈现成脚本文本简单拆段。
- 不要在失败或生成中显示旧结果为当前成功。
- 不要用大规模无限画布重构阻塞本轮 P0 验收。

## Task 5: 导出、回归和 README 迭代记录

目标：确保真实 Storyboard 生成闭环进入交付语境，并且不破坏现有真实 agent、项目图像生成和 Review 流程。

产品需求来源：

- 成功 Storyboard 会进入导出包。
- 未生成或失败的 Storyboard 不应被导出为成功产物。
- 现有 agent 运行仍使用 `gpt-5.5`。
- 现有项目图像生成仍使用 `gpt-image-2`。
- 现有项目创建、运行、暂停、修订、Review 编辑、项目图像生成、交付导出和自动化测试保持通过。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `README.md`
- `tests/test_storyboard.py`
- `tests/test_web.py`
- `tests/test_pipeline.py`
- `tests/test_providers.py`

实现步骤：

1. 调整 `export_project_package()`，确认导出 Storyboard 时包含:
   - generation metadata。
   - shots。
   - assets。
   - shot-asset relations。
   - shot-image links。
   - project image asset 摘要。
2. 未生成或仅 failed attempt 的项目不得在 `deliverables` 中伪造 completed storyboard。
3. README 迭代记录补充本轮需求来源、开发内容、用户价值、涉及文件、验证命令和仍待事项。
4. 运行 `.venv/bin/python -m ruff check .`。
5. 运行 `.venv/bin/python -m pytest`。
6. 如本机 `.env` 可用，执行真实配置 smoke：agent 运行、Storyboard 生成、项目图像生成和导出链路；只记录结果和错误类型，不输出 secret values。

验收标准：

- 自动化测试通过。
- 导出包包含真实成功 Storyboard 的 shots、assets 和 image links。
- failed Storyboard 不被导出为成功产物。
- README 明确记录本轮 Storyboard 真实模型生成能力和验证结果。

测试要求：

- 完整执行 ruff 和 pytest。
- 至少新增 storyboard generator/API/frontend smoke 相关测试。
- 真实 smoke 若因 provider 或配置失败，只记录具体阶段，不写成通过。

是否允许/要求重构：不要求新增大重构；只允许为导出和测试稳定性做小范围整理。

风险和注意事项：

- 不要提交 `.env`。
- 不要把批量分镜图生成、视频生成、音频、导演台或自由无限画布写成本轮已完成能力。
- 不要新增备用策略；如开发认为需要备用策略，必须先请求用户确认。
