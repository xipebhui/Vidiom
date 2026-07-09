# Architecture Control Plan: Storyboard Shot Assetization

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Storyboard Shot Assetization。
- 差距判断：`docs/product-gap-analysis.md` 将真实模型接入列为已完成基础能力，本轮 P0 缺口是故事板与 shot 资产化。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 要求脚本/故事板节点能拆解 shot、维护角色/场景/道具、合成提示词，并承接后续批量生图、生视频和合成。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，缺少必需配置时必须进入可见失败状态，不得产生假成功。

## 当前实现状态

- 最新提交：`38ca0d9 Update product requirement for storyboard assetization`。
- README 迭代记录显示上一轮已完成真实模型配置、项目图像生成、真实 `.env` smoke test，以及 43 个自动化测试通过。
- 当前后端以 `projects`、`canvas_nodes`、`canvas_edges`、`project_events`、`generated_image_assets` 为核心；agent 流程固定为 Seed、Premise、Character、Beat、Script、Production。
- 当前导出包包含脚本、拍摄包、Review notes、项目级 image assets 和 agent outputs，但不包含 storyboard、shot、项目内资产或 shot-image 关联。
- 当前前端是单文件 `src/vidiom/static/app.js` 状态机，Review tabs 固定为脚本、角色、拍摄、图像、检查、交付；尚未形成可承载大量 shot 编辑和资产关系的独立 storyboard 视图边界。
- 当前测试覆盖项目创建、运行、暂停、Review 编辑、项目级图像生成和 provider 行为；尚无 storyboard schema、storage migration、生成状态、shot 编辑、资产关系和导出包测试。
- 工作区存在未跟踪 `tmp-image/`，本轮视为本地参考素材目录，不纳入提交。

## 架构判断

现有架构可以支撑短剧 agent 运行和项目级首张图像，但不能直接支撑 LibTV 式故事板生产线。阻碍点不是单个 UI 缺口，而是缺少以下一等边界：

- 缺少 storyboard/shot/asset 数据模型，无法持久化可编辑 shot 顺序、审阅状态、提示词准备度和项目内资产关系。
- `generated_image_assets` 只有项目级归属，无法表达一张图像属于哪个 shot，后续批量分镜图无法追踪。
- `canvas_nodes.output_json` 适合 agent 节点结果，不适合承载用户持续编辑、排序、关联和局部更新的 shot 表。
- 前端 Review 面板可以展示较小 JSON 编辑表单，但不适合继续堆叠可排序 shot 列表、资产表和关联检查。
- 后端缺少 storyboard 生成 API 和可见状态记录，不能满足“生成中、成功、失败、人工编辑状态清晰可见”的产品验收。

因此，本轮首要开发项必须是 storyboard 基础设施改造，而不是直接堆 UI 展示。

## 本轮架构决策

### 1. Storyboard 成为项目内一等领域

新增独立领域模块，建议边界如下：

- `src/vidiom/storyboard_schema.py`：定义 storyboard 生成 JSON schema 和编辑校验规则。
- `src/vidiom/storyboard.py`：封装 `gpt-5.5` 生成器、上下文组装、结果标准化、资产提取和状态更新流程。
- `src/vidiom/storage.py`：增加 storyboard、shot、项目内资产、shot-asset 关联、shot-image 关联的迁移和持久化方法。
- `src/vidiom/web.py`：增加 storyboard 查询、生成、shot 编辑、资产编辑和图片关联 API。
- `src/vidiom/static/`：为 storyboard 增加独立视图状态和渲染边界，避免继续把所有 Review 行为塞进现有脚本/拍摄编辑逻辑。

### 2. 推荐数据模型方向

以 SQLite 表承载可编辑关系，不把 storyboard 塞进 `canvas_nodes.output_json`：

- `storyboards`
  - `id`
  - `project_id`
  - `status`: `not_started`、`generating`、`completed`、`failed`
  - `model`
  - `source_script_updated_at`
  - `source_production_updated_at`
  - `error_message`
  - `created_at`
  - `updated_at`
- `storyboard_shots`
  - `id`
  - `storyboard_id`
  - `sequence_index`
  - `review_status`: `pending`、`needs_changes`、`approved`
  - `beat_ref`
  - `scene_ref`
  - `visual_description`
  - `action_focus`
  - `dialogue_or_sound`
  - `duration_seconds`
  - `aspect_ratio`
  - `visual_style`
  - `image_prompt`
  - `prompt_ready`
  - `created_at`
  - `updated_at`
- `project_story_assets`
  - `id`
  - `project_id`
  - `asset_type`: `character`、`scene`、`prop`
  - `name`
  - `description`
  - `reference_prompt`
  - `consistency_notes`
  - `created_at`
  - `updated_at`
- `storyboard_shot_assets`
  - `shot_id`
  - `asset_id`
  - `role`
- `storyboard_shot_image_assets`
  - `shot_id`
  - `image_asset_id`
  - `link_type`: `reference`、`storyboard_frame`
  - `created_at`

该结构保留现有项目级图像能力，同时允许同一张已生成图像被明确绑定到 shot，后续批量分镜图也能直接写入同一关联表。

### 3. API 边界

建议新增以下 API：

- `GET /api/projects/{project_id}/storyboard`：返回 storyboard、shots、assets、shot-asset 关系、shot-image 关系、生成状态。
- `POST /api/projects/{project_id}/storyboard/generate`：仅允许 completed 项目触发；使用 `gpt-5.5` 读取脚本、角色、节拍、拍摄包、Brief 和已有 image assets 生成结构化 storyboard。
- `PATCH /api/projects/{project_id}/storyboard/shots`：批量保存 shot 新增、删除、排序、字段编辑和审阅状态。
- `PATCH /api/projects/{project_id}/storyboard/assets`：保存项目内角色、场景、道具描述、提示词和一致性备注。
- `POST /api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}`：建立现有图像资产与 shot 的语义关联。
- `DELETE /api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}`：移除关联。

所有写接口必须通过 Pydantic 请求模型校验输入，不接受静默截断为成功。模型配置缺失或 provider 错误要写入 storyboard failed 状态和 project event。

### 4. 异步任务边界

故事板生成应沿用现有 FastAPI `BackgroundTasks` 风格，但生成状态必须落在 `storyboards.status` 和 `project_events` 中：

- 请求开始后创建或更新 storyboard 为 `generating`。
- 生成成功后写入 shots、assets、relations，并将状态改为 `completed`。
- 生成失败后保留错误信息和事件，状态改为 `failed`。
- 不新增备用生成器、不写入占位成功结果、不在缺少模型配置时伪造 storyboard。

本轮不要求引入通用任务队列；但 `storyboard.py` 应把后台任务逻辑与 Web handler 分离，后续批量图像和视频任务可复用同样的状态写入模式。

### 5. 前端架构方向

短期必须新增 Storyboard 视图；中长期要从固定 agent 画布过渡到可承载资产节点的工作台。为控制本轮范围：

- 本轮不实现自由无限画布节点创建，但 storyboard UI 不能只作为脚本文本拆段展示。
- 在 Review 区新增“故事板”入口，显示 shot 列表、状态、prompt 准备度、角色/场景/道具摘要和生成状态。
- Shot 编辑、新增、删除、排序应形成独立渲染/读取函数，避免混入脚本和 production editor。
- 资产关系以项目内角色、场景、道具表展示，至少能编辑名称、描述、参考提示词和一致性备注。
- 图像页或故事板页必须显示 shot 与已有 image assets 的关联位置，为下一轮批量分镜图生成准备产品入口。

### 6. 测试策略

新增测试优先级：

- Storage migration：空库和旧库迁移后具备 storyboard 表；旧项目和现有 image assets 不丢失。
- Storyboard schema：生成 payload 必须包含多个 shot、资产和关系；缺字段报错。
- Storyboard generator：使用 fake language client 验证调用 `gpt-5.5`、上下文包含 script/characters/beats/production/brief/image_assets。
- Web API：生成成功、生成失败、查询、shot 编辑、资产编辑、shot-image 关联、导出包包含 storyboard。
- Frontend smoke：静态文件包含 Storyboard tab、生成入口、shot editor、asset editor、关联展示函数。
- Regression：现有项目创建、运行、暂停、修订、Review 编辑、项目图像生成和导出测试必须保持通过。

## 风险与控制

- 风险：继续把 storyboard 写进 `production` 节点输出会导致 shot 编辑和资产关系不可维护。控制：必须新增一等表和 API。
- 风险：一次性做完整 LibTV 无限画布会偏离本轮需求。控制：本轮只做脚本到 storyboard 的承接层，但数据结构预留 shot 与 image/video/audio 后续关联能力。
- 风险：前端单文件继续膨胀会拖慢后续图像/视频/导演台。控制：StoryBoard 渲染与编辑函数必须独立命名和集中，必要时拆出模块文件。
- 风险：模型错误被 UI 当成空 storyboard。控制：failed 状态必须可见，导出包不得包含假成功 storyboard。
- 风险：旧项目导出回归。控制：只有 completed 且已有 storyboard 的项目导出 storyboard；没有 storyboard 的旧完成项目仍可保持现有导出行为，但不得在包内伪造 storyboard。

## 为什么能支撑 LibTV 对齐

LibTV 的脚本/故事板能力依赖“shot 是生产单位，资产是可复用上下文，生成图片/视频是 shot 的下游任务”。本方案把 Vidiom 从项目级脚本和单张图像，升级为项目内 storyboard、shot、资产和图像关联的可编辑结构。后续批量分镜图、角色一致性、视频片段、音频和导演台都可以围绕 shot 和 asset 扩展，而不需要推翻本轮数据模型。
