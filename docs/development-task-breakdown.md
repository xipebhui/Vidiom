# Development Task Breakdown: Storyboard Editing and Asset Review Workspace

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Storyboard Editing and Asset Review Workspace，更新时间 2026-07-10 CST。

首要执行项：先改造 Storyboard 编辑域模型、Storage 事务和 API 边界，再实现前端 Storyboard 可编辑生产台。现有真实模型主链路已 completed，本轮不得继续围绕 smoke 门禁重复开发，也不得跳到批量分镜图、批量视频、音频、导演台或自由无限画布。

## Task 1: 建立 Storyboard 编辑域模型、事务存储和 API 边界

目标：把生成后的 Storyboard 从只读/轻审阅数据改造成可局部编辑、可增删排序、可维护关系、可导出的项目内生产数据。此任务是本轮要求的架构改造首要任务。

产品需求来源：

- Shot 编辑验收：用户可以编辑现有 shot 核心生产字段，编辑后保存、刷新仍可见，并进入导出包。
- Shot 新增、删除和排序验收：新增、删除、调整顺序后 Storyboard 顺序保持可读，并反映在展示和导出包中。
- 资产审阅验收：资产或关系变化后，相关 shot 的准备状态可被用户重新判断。
- 准备度验收：缺少关键字段或关键资产关系的 shots 会被标为需要处理。

影响文件/模块：

- `src/vidiom/storyboard_schema.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 Storyboard schema 或新的局部编辑 request 校验中定义 shot 可编辑字段：`beat_ref`、`scene_ref`、`characters`、`scene`、`props`、`visual_description`、`action_focus`、`dialogue_or_sound`、`duration_seconds`、`aspect_ratio`、`visual_style`、`image_prompt`、`review_status`、`prompt_ready`。
2. 在 Storage 中新增事务型方法：
   - 更新单个 shot 生产字段。
   - 新增 shot，可指定插入位置；未指定时追加到末尾。
   - 删除 shot，并清理该 shot 的 `storyboard_shot_assets` 和 `storyboard_shot_image_assets`。
   - 重排 shots，保证 `sequence_index` 连续且从 1 开始。
3. 排序实现必须规避 `UNIQUE(storyboard_id, sequence_index)` 的中间态冲突；使用单事务内的安全重编号策略，并在失败时回滚。
4. 每次 shot 内容、新增、删除或排序成功后，更新项目 `updated_at`，写入 `project_events`，并返回完整 `_storyboard_response()`。
5. 影响 prompt 或资产语境的 shot 编辑、新增、删除和排序必须让相关 shots 的 `prompt_ready=false`，由用户重新确认；不要静默保留旧 prompt ready。
6. 在 Web 层新增清晰 API，建议形态：
   - `PATCH /api/projects/{project_id}/storyboard/shots/{shot_id}`
   - `POST /api/projects/{project_id}/storyboard/shots`
   - `DELETE /api/projects/{project_id}/storyboard/shots/{shot_id}`
   - `POST /api/projects/{project_id}/storyboard/shots/reorder`
7. API 必须校验 project、storyboard 和 shot 归属；draft 或无 completed Storyboard 的项目不能编辑 shots。
8. 不要用整包 `replace_project_storyboard()` 作为人工编辑保存方式；该方法继续只服务于模型生成结果替换。

验收标准：

- 用户通过 API 可以编辑现有 shot 的全部核心生产字段。
- 新增 shot 后刷新仍存在，且 sequence 可读。
- 删除 shot 后剩余 sequence 连续，相关 asset/image link 关系被清理。
- 调整排序后展示和导出包顺序一致。
- 编辑、新增、删除和排序均写入 activity。
- 编辑后的 Storyboard 进入 `storage.export_project_package()`。
- API 不创建假 shots、假 assets、假 image links 或占位成功结果。

测试要求：

- 新增 Storage 测试：shot update/create/delete/reorder、prompt ready invalidation、activity、导出一致性。
- 新增 Web 测试：新增 API 的 200、404、400 路径和刷新后持久化。
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求重构。允许新增 Storyboard editing helper、request model 和 readiness helper；不允许引入通用工作流引擎，不允许重写为跨项目资产库，不允许改动备用 provider 策略或模型选择。

风险和注意事项：

- 不要把人工编辑实现成只改前端内存。
- 不要在排序中留下重复或跳号 sequence。
- 不要把旧 completed Storyboard 覆盖为空结果。
- 不要暴露 `HM_LLM_APIKEY`、`HM_IMG_APIKEY` 或实际密钥值。

## Task 2: 实现 Storyboard 准备度摘要与阻塞项派生

目标：让 Storyboard 工作区和导出包能明确告诉用户当前是否可以进入下一阶段媒体生成准备，而不是只展示 shots 列表。

产品需求来源：

- Storyboard 工作区显示 shot 总数、已确认数量、需修改数量和 prompt 未准备数量。
- 用户可以定位未确认、需修改或 prompt 未准备的 shots。
- 缺少画面描述、缺少提示词、缺少关键资产、时长异常或未确认 shot 的阻塞提示。
- 导出前能看出 Storyboard 是否还有未处理项。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 新增 readiness 派生 helper，基于当前 shots、assets、relationships 和 image links 计算：
   - `shot_count`
   - `approved_count`
   - `needs_changes_count`
   - `pending_count`
   - `prompt_not_ready_count`
   - `shots_with_blockers_count`
   - `ready_for_media_generation`
2. 为每个 shot 返回 blockers，至少覆盖：
   - `review_status` 不是 `approved`
   - `prompt_ready=false`
   - `visual_description` 为空
   - `image_prompt` 为空
   - `duration_seconds` 不在 schema 允许范围
   - 缺少 scene 关系或 scene 字段
   - characters/props 字段与关系明显不一致时提示需要检查
3. 将 readiness summary 和 blockers 加入 `GET /api/projects/{project_id}/storyboard` 响应。
4. 将 readiness summary 和 blockers 加入导出包中的 Storyboard deliverable。
5. 前端 Storyboard 页展示完成度摘要，并提供按 `pending`、`needs_changes`、`approved`、`prompt_not_ready`、`has_blockers` 过滤 shots 的能力。
6. 不要把 `ready_for_media_generation=true` 当作触发下游生成；本轮只做判断与提示。

验收标准：

- Storyboard 页面显示总 shot 数、已确认数量、需修改数量和 prompt 未准备数量。
- 用户能定位未确认、需修改、prompt 未准备或有 blockers 的 shots。
- 导出包包含 readiness summary 和每个 shot blockers。
- readiness 只基于现有数据派生，不调用真实模型，不生成媒体资产。

测试要求：

- 新增 readiness helper 单元测试。
- 新增 API/导出测试，断言 summary 和 blockers。
- 如修改前端：`node --check src/vidiom/static/app.js`
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：允许小范围重构。可以把 readiness 计算抽到独立 helper；不得新增异步任务或真实模型调用。

风险和注意事项：

- 不要把 blockers 做成不可解释的布尔值；必须能让用户知道要处理什么。
- 不要自动把所有 blockers 清空为 ready。
- 不要引入批量分镜图生成入口。

## Task 3: 实现角色、场景、道具资产 CRUD 与 shot-asset 关系编辑

目标：让项目内角色、场景、道具资产从生成摘要变成可审阅、可编辑、可关联的生产对象。

产品需求来源：

- 用户可以查看角色、场景、道具资产列表。
- 用户可以编辑资产名称、描述、参考提示词和一致性说明。
- 用户可以新增资产。
- 用户可以删除未使用或错误资产。
- 用户可以查看资产关联的 shots。
- 用户可以调整 shot 与资产关系。
- 资产或关系变化后，相关 shot 的准备状态可被用户重新判断。

影响文件/模块：

- `src/vidiom/storyboard_schema.py`
- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 Storage 中新增资产事务方法：
   - 新增 asset，字段为 `asset_type`、`name`、`description`、`reference_prompt`、`consistency_notes`。
   - 更新 asset 字段。
   - 删除 asset，并在同一事务中删除相关 `storyboard_shot_assets`。
2. 资产 `asset_type` 只能是 `character`、`scene`、`prop`；同一 project 下 `asset_type + name` 仍保持唯一。
3. 新增 shot-asset relation 编辑方法，允许为某个 shot 设置角色、场景、道具关系及 role；每次更新必须校验 asset 与 shot 属于同一 project。
4. asset 名称变化后，关系应继续通过 `asset_id` 保持稳定；不要依赖旧名称更新关系。
5. asset 内容或关系变化后，受影响 shots 的 `prompt_ready=false`，并写入 activity。
6. Web 层新增 API，建议形态：
   - `POST /api/projects/{project_id}/storyboard/assets`
   - `PATCH /api/projects/{project_id}/storyboard/assets/{asset_id}`
   - `DELETE /api/projects/{project_id}/storyboard/assets/{asset_id}`
   - `PUT /api/projects/{project_id}/storyboard/shots/{shot_id}/assets`
7. API 响应返回完整 Storyboard 状态，包含 assets、relationships、readiness 和 blockers。
8. 前端 Storyboard 工作区新增资产面板：按 character/scene/prop 分组，支持查看关联 shots、编辑、新增、删除和从 shot 侧调整关联。

验收标准：

- 用户可创建、编辑、删除角色/场景/道具资产。
- 用户可看到每个资产被哪些 shots 使用。
- 用户可调整每个 shot 的角色、场景、道具关系。
- 删除资产不会留下悬空关系。
- 资产或关系变化后，相关 shots 不再静默保持 prompt ready。
- 最新资产和关系进入导出包。

测试要求：

- 新增 Storage 测试：asset create/update/delete、关系 set、跨项目拒绝、prompt ready invalidation。
- 新增 Web 测试：asset API 和 relation API。
- 如修改前端：`node --check src/vidiom/static/app.js`
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：要求小范围重构。允许把 asset/relation 校验抽成 helper；不允许引入跨项目资产库或 LibTV 资产栏全局系统。

风险和注意事项：

- 不要用 asset 名称作为关系主键。
- 不要删除项目图像资产来实现 story asset 删除。
- 不要把资产 CRUD 做成孤立备注；必须反映到相关 shots、readiness 和导出包。

## Task 4: 完成项目图像关联审阅与导出摘要

目标：让已有项目图像在 Storyboard 审阅中成为可管理的 shot 参考或分镜占位，而不是只在图像页孤立展示。

产品需求来源：

- 用户可以查看当前项目图像资产。
- 用户可以把已有项目图像关联到 shot。
- 用户可以移除 shot 与项目图像的关联。
- 项目图像资产本身不会因为解除 shot 关联而消失。
- 导出包包含最新 shot-image 关联摘要。
- 图像关联应清楚区分参考图、分镜图占位或已有项目图像。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js`
- `src/vidiom/static/styles.css`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 保留现有 shot-image link/unlink API，并补齐前端移除能力；当前 UI 只需要关联已有项目图像，不触发新图像生成。
2. 在 UI 中区分 `reference` 与 `storyboard_frame` 两类 link type；用户能选择关联类型。
3. 在每个 shot 上展示已关联图像数量和 link type；在图像资产上展示被哪些 shots 使用。
4. 解绑 shot-image link 时只删除 `storyboard_shot_image_assets` 关系，不删除 `generated_image_assets`。
5. 关系变化后对应 shot 的 `prompt_ready=false`，由用户重新确认。
6. 确认导出包包含最新 `image_links`，并能看出 image asset id、model、status、prompt 和 link type。

验收标准：

- 用户可以查看项目图像资产并关联到当前选中 shot。
- 用户可以移除 shot-image 关联，项目图像资产仍在项目图像列表中。
- 用户可以区分参考图与分镜图占位。
- 每个 shot 能显示是否已有项目图像关联。
- 导出包包含最新 shot-image 关联摘要。

测试要求：

- 保留并扩展 image link/unlink Storage 和 API 测试。
- 新增导出测试，断言 link type 和 image asset 摘要。
- 如修改前端：`node --check src/vidiom/static/app.js`
- 运行：`.venv/bin/python -m pytest tests/test_storyboard.py tests/test_web.py`
- 运行：`git diff --check`

是否允许/要求重构：允许小范围重构。不得新增批量分镜图生成，不得自动调用 `gpt-image-2` 为每个 shot 生成图像。

风险和注意事项：

- 不要把解除关联实现成删除图片资产。
- 不要把项目图像误标为已批量分镜生成结果。
- 不要创建占位图片或假图像 URL。

## Task 5: 建设 Storyboard 可编辑生产台前端体验

目标：在现有 Studio Review 的 Storyboard 页内提供面向镜头生产的可扫描、可编辑、可过滤工作区，让用户能完成本轮关键流程。

产品需求来源：

- Storyboard 编辑体验应面向镜头生产，而不是普通长文本表单。
- 用户应能快速扫描哪些 shots 需要处理，哪些已经确认。
- 新增、删除、排序和编辑后的结果必须可追溯、可保存、可导出。
- 资产编辑应清楚影响到哪些 shots。
- 如果某个 shot 缺少关键字段，应以阻塞项形式提示用户。

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
   - asset 面板。
   - relation editor。
   - image link editor。
2. Shot 列表支持按全部、未确认、需修改、已确认、prompt 未准备、有阻塞项筛选。
3. Shot 详情表单支持编辑 Task 1 的所有核心字段；保存后重新加载 Storyboard 响应。
4. 提供新增 shot、删除 shot、上移/下移或明确排序控件；排序后 UI 与后端 sequence 一致。
5. 资产面板支持新增、编辑、删除，并显示关联 shots。
6. 关系编辑在 shot 详情中可调整角色、场景、道具；保存后 readiness 与 prompt ready 状态立即更新。
7. 图像关联编辑支持 reference/storyboard_frame 选择和解除关联。
8. 不要在前端生成假成功结果；API 失败必须可见显示。

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

## Task 6: 回归、README 和真实模型链路保护

目标：确保本轮 Storyboard 编辑和资产审阅不会破坏已经 completed 的真实模型主链路、项目图像和导出包能力。

产品需求来源：

- 现有真实模型配置继续保持：语言模型 `gpt-5.5`，图像模型 `gpt-image-2`，配置变量为 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`。
- Storyboard 生成、项目图像生成和导出包能力不得退化。
- 最新真实 smoke completed 记录不得被删除或改写为未验收。
- 常规自动化测试不得自动消耗真实模型额度。
- 文档不得包含 secret values。

影响文件/模块：

- `README.md`
- `docs/real-model-smoke-result.md`
- `src/vidiom/smoke.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`
- `tests/test_smoke.py`

实现步骤：

1. 保持 `docs/real-model-smoke-result.md` 的 completed 记录，不要把它改写成未验收状态。
2. 确认 Storyboard 生成 API 仍调用 `gpt-5.5`，项目图像生成仍调用 `gpt-image-2`。
3. 确认编辑后的 Storyboard 不影响后续重新生成的失败/中断语义：失败或中断仍不能创建假结果，也不能清空旧 completed result。
4. 更新 README 迭代记录，写明本轮 Storyboard 编辑台、资产审阅、图像关联、准备度摘要、测试结果和未做事项。
5. 常规测试继续使用 fake clients；不要把真实 `.env` smoke 放进默认测试。
6. 如开发手动运行真实 smoke，只能作为显式验收记录，并确保不写入 secret values。

验收标准：

- 全量单元测试通过。
- `node --check src/vidiom/static/app.js` 通过。
- `git diff --check` 通过。
- README 记录本轮能力与测试结果。
- 文档未包含实际 secret values。
- `docs/real-model-smoke-result.md` 最新 completed 记录未被删除或改写成失败。

测试要求：

- `.venv/bin/python -m pytest`
- `.venv/bin/python -m ruff check .`
- `node --check src/vidiom/static/app.js`
- `git diff --check`

是否允许/要求重构：不要求。只做回归保护和文档同步。

风险和注意事项：

- 不要把本轮编辑功能误写为批量分镜图或视频生成完成。
- 不要自动消耗真实模型额度。
- 不要提交 `.env` 或任何密钥值。
