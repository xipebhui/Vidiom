# Development Task Breakdown: Storyboard Readiness and Asset Review Workspace

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Storyboard Readiness and Asset Review Workspace，更新时间 2026-07-10 CST。

首要执行项：先建立 Storyboard readiness summary、per-shot blockers 和导出事实源，再实现资产 CRUD、shot-asset 关系编辑、项目图像关联增强和前端 Storyboard 可编辑生产台。上一轮已完成 shot 编辑事务和 API 边界，本轮不得重复建设该基础，也不得跳到批量分镜图、批量视频、音频、导演台或自由无限画布。

## Task 1: 建立 Storyboard 准备度摘要与阻塞项事实源

目标：让 Studio、API 和导出包都能明确告诉用户当前 Storyboard 哪些 shots 可进入下一阶段准备，哪些 shots 仍需处理。

产品需求来源：

- 准备度验收：Storyboard 工作区显示 shot 总数、已确认数量、需修改数量、未确认数量、prompt 未准备数量和有阻塞项数量。
- 准备度验收：用户可以定位未确认、需修改、prompt 未准备或有阻塞项的 shots。
- 准备度验收：每个阻塞项都能让用户理解需要处理什么。
- 导出验收：导出包包含 Storyboard 准备度摘要和 per-shot 阻塞项摘要。

影响文件/模块：

- `src/vidiom/storyboard_schema.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 新增 readiness 派生 helper，输入当前 storyboard response 中的 `shots`、`assets`、`relationships`、`image_links`，输出 `readiness_summary` 和每个 shot 的 `blockers`。
2. `readiness_summary` 至少包含：
   - `shot_count`
   - `approved_count`
   - `needs_changes_count`
   - `pending_count`
   - `prompt_not_ready_count`
   - `shots_with_blockers_count`
   - `ready_for_media_generation`
3. per-shot blockers 至少覆盖：
   - `review_status` 为 `pending` 或其他非 `approved` 状态。
   - `review_status` 为 `needs_changes`。
   - `prompt_ready=false`。
   - `visual_description` 为空或只有空白。
   - `image_prompt` 为空或只有空白。
   - `duration_seconds` 不在 1 到 120 秒范围。
   - 缺少场景资产关系，或 scene 字段为空。
   - characters/props 字段与现有关联关系明显不一致时提示需要复核。
4. 将 readiness helper 接入 `storage.get_project_storyboard()` 或 Web `_storyboard_response()`，确保 `GET /api/projects/{project_id}/storyboard` 总是返回 `readiness_summary` 和 shot-level blockers。
5. 将相同 readiness 结果写入 `storage.export_project_package()` 的 Storyboard deliverable。
6. `ready_for_media_generation=true` 只表示提示和确认，不触发批量图像、视频或任何真实模型调用。
7. 保持现有真实 Storyboard 生成、失败/中断保留旧成功结果、项目图像和导出包行为不退化。

验收标准：

- API 返回 shot 总数、已确认数量、需修改数量、未确认数量、prompt 未准备数量和有阻塞项数量。
- 每个 shot 返回可解释 blockers。
- 导出包包含与 API 一致的 readiness summary 和 per-shot blockers。
- 准备度只基于当前 Storyboard、资产、关系和图像关联判断，不调用真实模型，不生成媒体资产。

测试要求：

- 新增 readiness helper 单元测试，覆盖 approved、pending、needs_changes、prompt 未准备、缺字段、缺场景资产关系、字段/关系需复核。
- 新增 API 测试，断言 `GET /storyboard` 返回 summary 与 blockers。
- 新增导出测试，断言 Storyboard deliverable 包含 readiness summary 和 per-shot blockers。
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求小范围重构。允许新增 `storyboard_readiness` helper 或 Storage 内部 helper；不允许新增异步任务、真实模型调用、批量媒体生成或备用 provider 策略。

风险和注意事项：

- 不要把 blockers 做成不可解释的布尔值。
- 不要把 readiness 只放在前端内存。
- 不要自动把 blockers 清空为 ready。
- 不要引入批量分镜图生成入口。

## Task 2: 实现角色、场景、道具资产 CRUD API 与存储事务

目标：让 Storyboard 中提取的角色、场景、道具资产从生成摘要变成可审阅、可编辑、可新增、可删除的项目内生产对象。

产品需求来源：

- 资产审阅验收：用户可以查看角色、场景、道具资产列表。
- 资产审阅验收：用户可以编辑资产名称、描述、参考提示词和一致性说明。
- 资产审阅验收：用户可以新增资产。
- 资产审阅验收：用户可以删除未使用或错误资产。
- 资产审阅验收：最新资产进入导出包。

影响文件/模块：

- `src/vidiom/storyboard_schema.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 Storage 中新增事务型 asset 方法：
   - 创建 asset：`asset_type`、`name`、`description`、`reference_prompt`、`consistency_notes`。
   - 更新 asset 字段。
   - 删除 asset，并在同一事务中删除相关 `storyboard_shot_assets`。
2. `asset_type` 只能是 `character`、`scene`、`prop`；继续保持同一 project 下 `asset_type + name` 唯一。
3. 所有 asset 操作必须校验 project 归属和 completed Storyboard 存在状态；无 completed Storyboard 时不得创建孤立 Storyboard asset。
4. 删除 asset 后不得留下悬空关系；受影响 shots 的 `prompt_ready=false`。
5. asset 名称变化后，已有关系继续通过 `asset_id` 保持稳定，不依赖旧名称。
6. 写入 `project_events`，事件类型建议使用 `storyboard_asset_edit`，details 包含 asset id、asset type、受影响 shot ids 和是否重置 prompt ready。
7. Web 层新增 API，建议形态：
   - `POST /api/projects/{project_id}/storyboard/assets`
   - `PATCH /api/projects/{project_id}/storyboard/assets/{asset_id}`
   - `DELETE /api/projects/{project_id}/storyboard/assets/{asset_id}`
8. API 响应返回完整 Storyboard 状态，包含 readiness 和 blockers。

验收标准：

- 用户可通过 API 创建、编辑、删除角色/场景/道具资产。
- 删除资产不会留下悬空关系。
- 资产变化后相关 shots 不再静默保持 prompt ready。
- 最新资产进入 `GET /storyboard` 和导出包。

测试要求：

- 新增 Storage 测试：asset create/update/delete、重复名称拒绝、无 completed Storyboard 拒绝、删除清理关系、prompt ready invalidation、activity。
- 新增 Web 测试：asset API 的 200、400、404 路径。
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求小范围重构。允许抽取 asset 校验 helper；不允许引入跨项目资产库、LibTV 全局资产栏或通用工作流引擎。

风险和注意事项：

- 不要用 asset 名称作为关系主键。
- 不要删除项目图像资产来实现 story asset 删除。
- 不要把资产 CRUD 做成孤立备注；必须影响相关 shots、readiness 和导出包。

## Task 3: 实现 shot-asset 关系编辑与关系影响提示

目标：让用户能整理每个 shot 使用哪些角色、场景和道具，并能从资产侧看到被哪些 shots 使用。

产品需求来源：

- Shot 与资产关系审阅：用户可以查看每个 shot 使用了哪些角色、场景和道具。
- Shot 与资产关系审阅：用户可以查看每个资产关联了哪些 shots。
- Shot 与资产关系审阅：用户可以调整 shot 与资产的关联关系。
- Shot 与资产关系审阅：识别缺少关键资产的 shots。
- 资产或关系变化后，相关 shot 的准备状态可被用户重新判断。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 Storage 中新增 `set_storyboard_shot_assets(project_id, shot_id, relationships)`，以单个 shot 为单位替换该 shot 的角色、场景、道具关系。
2. 每个 relationship 输入包含 `asset_id` 和 `role`；asset type 从 asset 记录读取，不由前端信任。
3. 校验 shot 属于当前 project 的 completed Storyboard，asset 属于同一 project。
4. 支持同一 shot 关联多个 character/prop；scene 关系建议允许一个或多个，但 readiness 必须能识别缺少 scene 关系。
5. 更新关系后，将该 shot 的 `prompt_ready=false`，并写入 `storyboard_relation_edit` activity。
6. `GET /storyboard` 响应中的 assets 应能让前端计算或直接读取每个 asset 关联的 shot 列表；如选择直接返回 `asset_usage`，导出包也应包含同源信息。
7. Web 层新增 API，建议形态：`PUT /api/projects/{project_id}/storyboard/shots/{shot_id}/assets`。
8. API 响应返回完整 Storyboard 状态，包含最新 relationships、readiness 和 blockers。

验收标准：

- 用户可通过 API 调整某个 shot 的角色、场景、道具关系。
- 跨项目 shot/asset 关系被拒绝。
- 关系变化后相关 shot 的 `prompt_ready=false`。
- readiness 能识别缺少关键关系的 shots。
- 最新关系进入导出包。

测试要求：

- 新增 Storage 测试：relation set、清空关系、跨项目拒绝、缺失 asset 拒绝、prompt ready invalidation、导出一致性。
- 新增 Web 测试：relation API 的 200、400、404 路径。
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求小范围重构。允许复用 asset 校验 helper；不允许新增跨项目资产库或自动提示词重写模型调用。

风险和注意事项：

- 不要从前端提交的 asset type 推导关系事实。
- 不要留下 orphan relation。
- 不要因为关系变化自动生成新图片或新 Storyboard。

## Task 4: 完成项目图像关联审阅、link type 和解除关联闭环

目标：让已有项目图像在 Storyboard 审阅中成为可管理的 shot 参考或分镜占位，而不是只在图像页孤立展示。

产品需求来源：

- 图像关联验收：用户可以查看当前项目图像资产。
- 图像关联验收：用户可以把已有项目图像关联到 shot。
- 图像关联验收：用户可以移除 shot 与项目图像的关联。
- 图像关联验收：项目图像资产本身不会因为解除 shot 关联而消失。
- 图像关联验收：用户可以区分参考图与分镜图占位。
- 图像关联验收：导出包包含最新 shot-image 关联摘要。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 保留现有 shot-image link/unlink API，并确认 link 与 unlink 都会返回包含 readiness 的完整 Storyboard 状态。
2. 确认 `link_type` 支持 `reference` 与 `storyboard_frame`，前端可选择关联类型。
3. 解绑 shot-image link 时只删除 `storyboard_shot_image_assets` 关系，不删除 `generated_image_assets`。
4. 图像关系变化后，对应 shot 的 `prompt_ready=false`，由用户重新确认。
5. 在每个 shot 上展示已关联图像数量和 link type；在图像资产上展示被哪些 shots 使用。
6. 导出包包含最新 `image_links`，并能看出 image asset id、model、status、prompt、revised prompt 和 link type。
7. 不触发新的 `gpt-image-2` 调用，不创建占位图片。

验收标准：

- 用户可以查看项目图像资产并关联到当前 selected shot。
- 用户可以选择 `reference` 或 `storyboard_frame` link type。
- 用户可以移除 shot-image 关联，项目图像资产仍在项目图像列表中。
- 每个 shot 能显示是否已有项目图像关联。
- 导出包包含最新 shot-image 关联摘要。

测试要求：

- 扩展 image link/unlink Storage 测试，断言 link type、prompt ready invalidation 和图片资产保留。
- 新增 Web 测试覆盖 `reference`、`storyboard_frame`、unlink 和错误路径。
- 如修改前端：`node --check src/vidiom/static/app.js`
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：允许小范围重构。不得新增批量分镜图生成，不得自动调用 `gpt-image-2` 为每个 shot 生成图像。

风险和注意事项：

- 不要把解除关联实现成删除图片资产。
- 不要把项目图像误标为已批量分镜生成结果。
- 不要创建假图像 URL 或占位图片。

## Task 5: 建设 Storyboard 可编辑生产台前端体验

目标：在现有 Studio Review 的 Storyboard 页内提供面向镜头生产的可扫描、可编辑、可过滤工作区，让用户能完成本轮关键流程。

产品需求来源：

- Storyboard 编辑体验应面向镜头生产，而不是普通长文本表单。
- 用户应能快速扫描哪些 shots 需要处理，哪些已经确认。
- 新增、删除、排序和编辑后的结果必须可追溯、可保存、可导出。
- 资产编辑应清楚影响到哪些 shots。
- 图像关联应清楚区分参考图、分镜图占位或已有项目图像。

影响文件/模块：

- `src/vidiom/static/index.html`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_web.py`

实现步骤：

1. 在 `app.js` 内整理 Storyboard 工作区函数边界，至少分为：
   - 数据加载/保存 action。
   - readiness summary 渲染。
   - shot 列表和状态过滤。
   - shot 详情编辑表单。
   - shot 新增、删除、排序控件。
   - asset 面板。
   - relation editor。
   - image link editor。
2. Shot 列表支持按全部、未确认、需修改、已确认、prompt 未准备、有阻塞项、已有图像、无图像筛选。
3. Shot 详情表单支持编辑核心生产字段：`beat_ref`、`scene_ref`、`characters`、`scene`、`props`、`visual_description`、`action_focus`、`dialogue_or_sound`、`duration_seconds`、`aspect_ratio`、`visual_style`、`image_prompt`、`review_status`、`prompt_ready`。
4. 提供新增 shot、删除 shot、上移/下移或明确排序控件；排序后 UI 与后端 sequence 一致。
5. 资产面板支持新增、编辑、删除，并显示关联 shots。
6. 关系编辑在 shot 详情中可调整角色、场景、道具；保存后 readiness 与 prompt ready 状态立即更新。
7. 图像关联编辑支持 `reference`/`storyboard_frame` 选择和解除关联。
8. API 失败必须可见显示，不要在前端生成假成功结果。

验收标准：

- 用户能在 Storyboard 页完成 shot 编辑、新增、删除、排序。
- 用户能编辑资产并调整 shot-asset 关系。
- 用户能关联和解除项目图像。
- 用户能按状态定位待处理 shots。
- 刷新后所有编辑仍可见。
- 页面不会暴露 secret values，也不会显示假生成成功。

测试要求：

- `node --check src/vidiom/static/app.js`
- 通过 `tests/test_web.py` 静态断言关键 API 路径、控件 data attribute 和状态文案存在。
- 运行：`.venv/bin/python -m pytest tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求前端局部重构。允许整理 Storyboard 相关函数和 CSS；不允许引入大型框架迁移、自由无限画布或通用节点系统。

风险和注意事项：

- 不要把生产台做成纯展示卡片堆叠；需要可编辑控件和状态筛选。
- 不要让长文本挤出按钮或覆盖相邻区域。
- 不要把 UI 操作只存在浏览器内存。

## Task 6: 回归、文档和发布记录

目标：确保本轮 Storyboard readiness 与资产工作区能力不会破坏真实模型主链路、项目图像和导出包，并让下一轮产品/架构任务能读取完成状态。

产品需求来源：

- 真实模型与回归验收：现有真实模型配置继续保持。
- 真实模型与回归验收：Storyboard 生成、项目图像生成和导出包能力不得退化。
- 真实模型与回归验收：最新真实 smoke completed 记录不得被删除或改写为未验收。
- 真实模型与回归验收：常规自动化测试不得自动消耗真实模型额度。
- 真实模型与回归验收：文档不得包含 secret values。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- `tests/test_storyboard.py`
- `tests/test_web.py`
- `tests/test_smoke.py`
- `src/vidiom/static/app.js`

实现步骤：

1. 保留 `docs/real-model-smoke-result.md` 最新 completed 记录，不将其改写为未验收。
2. README 迭代记录写明本轮完成的 readiness、asset/relation、image link、前端工作区和导出包变化。
3. 常规测试继续使用 fake provider，不自动调用真实 `gpt-5.5` 或 `gpt-image-2`。
4. 确认 docs、README、测试输出和错误信息只包含变量名，不包含 `HM_LLM_APIKEY`、`HM_IMG_APIKEY` 或实际密钥值。
5. 开发完成后运行完整回归：
   - `.venv/bin/python -m ruff check .`
   - `.venv/bin/python -m pytest`
   - `node --check src/vidiom/static/app.js`
   - `git diff --check`

验收标准：

- README 记录本轮完成内容、用户价值、涉及文件和测试结果。
- 常规测试不消耗真实模型额度。
- 真实 smoke completed 记录仍可被下一轮产品/架构任务读取。
- 文档和代码不包含 secret values。

测试要求：

- 完整回归命令全部通过，或在 README 迭代记录中明确记录未通过原因。

是否允许/要求重构：不要求功能重构。允许整理测试 helper 和 README 文字；不得改变模型选择、provider 配置变量或真实 smoke completed 语义。

风险和注意事项：

- 不要删除或覆盖最新 completed smoke 记录。
- 不要把真实 provider 调用放进默认单元测试。
- 不要记录密钥值。
