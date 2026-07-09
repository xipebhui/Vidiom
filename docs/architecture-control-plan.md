# Architecture Control Plan: Storyboard Editing and Asset Review Workspace

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Storyboard Editing and Asset Review Workspace。
- 最新产品差距：`docs/product-gap-analysis.md` 已将下一步 P0 缺口从真实模型接入切换为 Storyboard 可编辑生产台与资产审阅闭环。
- 最新真实验收记录：`docs/real-model-smoke-result.md` 当前 overall status 为 `completed`，同轮完成 `agent_project`、`storyboard_generation`、`project_image_generation` 和 `export_package`。本轮架构判断以该 completed 记录作为真实模型主链路已验收的依据。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 的脚本/故事板链路要求用户先检查并编辑 shot、角色、场景、道具、提示词和资产关系，再进入批量分镜图、批量视频与视频合成。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`；生产 runtime 不得生成假结果、备用 provider 结果或占位成功结果。

## 当前实现状态

- 当前分支：`main`，与 `origin/main` 对齐。
- 最新提交：`caf3cae Update product requirement for storyboard editing`。
- 工作区存在未跟踪 `tmp-image/`，作为 LibTV 参考截图目录，不纳入本轮架构文档提交。
- README 最新迭代记录写明真实 `.env` smoke 已 completed：`gpt-5.5` agent 完成 5/5 节点，`gpt-5.5` Storyboard 完成 18 shots/18 assets/119 relationships，`gpt-image-2` 项目图像完成 1 个资产，导出包 completed。
- `src/vidiom/storyboard_schema.py` 已定义 Storyboard 生成 payload 的 shots、assets、relationships 基础字段，以及 review status、asset type、image link type 枚举。
- `src/vidiom/storage.py` 已有 `storyboards`、`storyboard_shots`、`project_story_assets`、`storyboard_shot_assets`、`storyboard_shot_image_assets`、`generated_image_assets` 和 `project_events`。这些表能保存生成结果、项目图像和导出包，但当前主要入口是整包替换 Storyboard、更新 shot review/prompt ready、绑定/解绑项目图像。
- `src/vidiom/web.py` 已提供 Storyboard 查询、生成、shot review 更新、shot-image link/unlink 和项目导出 API；尚未提供 shot 深度编辑、新增、删除、排序、资产 CRUD、shot-asset 关系编辑和准备度摘要 API。
- `src/vidiom/static/app.js` 的 Storyboard 页仍是单体 Review 面板中的展示型 UI，只能批准/标记需修改和关联项目图像；尚不具备生产级编辑台、状态筛选、资产编辑、关系矩阵或阻塞项定位。
- `tests/test_storyboard.py`、`tests/test_web.py` 和 `tests/test_smoke.py` 已覆盖生成、失败/中断语义、导出、review 和 image link 回归；尚未覆盖本轮需要的编辑事务、排序重编号、资产关系变更、准备度计算和导出一致性。

## 架构判断

本轮产品需求有效且包含可执行验收标准，因此不阻塞。当前真实模型主链路已具备可用上游，下一步应把生成后的 Storyboard 变成可编辑、可保存、可导出、可审阅的生产数据，而不是继续围绕模型接入或 smoke 门禁重复建设。

现有架构能支撑本轮的基础数据边界，但不能直接支撑产品验收：

- 前端架构：当前 `src/vidiom/static/app.js` 单体 Review 面板已接近本阶段上限。深度 shot 表单、排序、新增/删除、资产面板、关系编辑、项目图像关联和准备度筛选会显著增加状态复杂度。本轮不引入完整前端框架迁移，也不建设 LibTV 式自由无限画布，但必须把 Storyboard 工作区在现有静态前端内做模块化整理，至少分出 Storyboard 状态派生、shot 列表/编辑器、资产面板、图像关联和准备度摘要的函数边界。
- 后端存储：SQLite 表结构方向正确，Storyboard、shots、assets、relationships 和 image links 已是一等数据，不需要推倒重建。但当前 Storage 缺少细粒度编辑事务，且 `replace_project_storyboard()` 会整包替换 shots/assets，不适合人工编辑后的局部保存。首要开发任务必须补齐事务型编辑方法和 API，而不是先堆 UI。
- 数据模型：继续保留 Storyboard 作为项目内一等领域对象；本轮不引入跨项目资产库、视频资产、音频资产、导演台场景或通用工作流表。shot、asset、relationship、image link 的编辑必须保持引用完整性，排序后 `sequence_index` 必须连续可读。
- API 边界：需要新增或扩展 Storyboard 编辑 API，覆盖 shot CRUD、shot reorder、asset CRUD、shot-asset relation set/update、readiness summary 和 blockers。现有 image link API 可保留，但 UI 需要支持移除关联并区分 `reference` 与 `storyboard_frame`。
- 异步任务：本轮不新增批量分镜图、批量视频或后台媒体生成任务。真实 Storyboard 生成仍沿用现有后台任务；编辑 API 必须是同步事务，失败时不产生部分写入。
- Provider 抽象：本轮不做新模型接入、模型替换、备用 provider、自动重试或假数据路径。`gpt-5.5` Storyboard 生成和 `gpt-image-2` 项目图像能力必须保持回归。
- 测试结构：常规测试继续使用 fake clients，不自动消耗真实模型额度；本轮重点补 Storage/API/UI 静态检查和导出一致性测试。真实 smoke 可作为显式回归命令，不作为普通单元测试的一部分。
- README 迭代记录：开发完成后必须记录 Storyboard 编辑台、资产审阅、图像关联、准备度摘要和测试结果，并说明真实模型 completed 记录未被删除或改写。

## 本轮架构决策

### 1. 首要任务设为 Storyboard 编辑域模型与存储/API 改造

现有架构已经阻碍下一版需求直接落地：数据表存在，但缺少可安全执行的局部编辑命令、关系维护和准备度派生。开发首要执行项必须是后端 Storyboard 编辑域服务与 API 边界，而不是先做表层 UI。

本轮应在 Storage 层新增事务型方法，并在 Web 层暴露清晰 API：

1. 编辑 shot 核心生产字段：`beat_ref`、`scene_ref`、`characters`、`scene`、`props`、`visual_description`、`action_focus`、`dialogue_or_sound`、`duration_seconds`、`aspect_ratio`、`visual_style`、`image_prompt`、`review_status`、`prompt_ready`。
2. 新增 shot，自动分配或接受明确插入位置，并在事务内重排 `sequence_index`。
3. 删除 shot，同时删除该 shot 的 asset relations 和 image links，并重排剩余 shots。
4. 调整 shot 顺序，保证顺序变化同步进入展示、导出和 readiness 计算。
5. 编辑、新增、删除角色/场景/道具资产，并维护引用完整性。
6. 调整 shot 与 asset 的关系；关系变化后受影响 shots 必须重新进入可判断状态。
7. 计算并返回 Storyboard readiness summary 和 per-shot blockers。

### 2. 准备度采用派生摘要加用户确认字段

`prompt_ready` 继续表示用户对该 shot prompt 是否准备好的确认；系统新增派生的 readiness summary 和 blockers，用于提示缺少字段、缺少关键资产、时长异常、未确认或 prompt 未准备等问题。

规则方向：

- `review_status` 和 `prompt_ready` 是用户可编辑状态。
- `readiness_summary` 和 `blockers` 由当前 shots、assets、relationships、image links 派生，不作为用户手写字段。
- 当 shot 生产字段、asset 内容、shot-asset relations 或 shot-image links 改变时，受影响 shots 的 `prompt_ready` 应在同一事务中重置为 false，直到用户重新确认。
- 如果开发认为需要完整撤销、版本历史或编辑快照，应在 README 待处理事项标为“需用户确认”，不得作为本轮默认降级或备用策略写入实现。

### 3. 前端只做 Storyboard 工作区内的必要模块化

长期来看，当前静态单体前端撑不住 LibTV 级无限画布、自由节点、资产栏、历史记录、图像/视频/音频资产、工作流和导演台。这个判断继续作为长期架构约束。

本轮产品明确不做自由无限画布、批量分镜图、视频、音频或导演台，因此不启动全量前端重构。但为了让本轮 Storyboard 编辑台可维护，开发必须在现有 `app.js` 中整理 Storyboard 相关函数边界：

- Storyboard 数据加载与 readiness 派生展示。
- Shot 列表、筛选和详情编辑。
- Asset 列表与编辑。
- Shot-asset 关系编辑。
- 项目图像关联与移除。
- 导出准备度摘要。

### 4. 导出包必须成为编辑后 Storyboard 的事实来源

用户编辑后的 Storyboard 必须进入 `storage.export_project_package()` 的 deliverables，不允许出现“界面已修改但导出仍是模型初稿”的分裂。

导出包应包含：

- Storyboard metadata 和 generation status。
- 最新 shots，包括排序、review status 和 prompt ready。
- 最新角色/场景/道具 assets。
- 最新 shot-asset relationships。
- 最新 shot-image links，并保留项目图像资产本身。
- readiness summary 和 blockers 摘要。

### 5. 不推进下游媒体生成

本轮需求是批量媒体生成前的可信上游，不做批量分镜图、批量视频、视频合成、音频、导演台或自由无限画布。任何新建任务不得自动调用 `gpt-image-2` 批量生成 shot 图，也不得引入备用模型、占位图或假成功状态。

## 当前风险与控制

- 风险：只在前端表单里临时编辑，刷新或导出后丢失。控制：首要任务必须落在 Storage 事务和 API，UI 只能调用持久化接口。
- 风险：shot 排序与数据库唯一约束冲突，导致部分更新或重复 sequence。控制：排序必须在事务内使用稳定重编号策略，并用测试覆盖。
- 风险：资产改名、删除或关系变化后出现悬空关系。控制：asset CRUD 和 relation API 必须在同一事务内校验 project、storyboard、shot 和 asset 归属。
- 风险：prompt ready 在字段变化后仍保留 true，误导用户进入批量生成。控制：影响 prompt 的编辑必须让相关 shots 重新进入 prompt 未准备状态，并在 blockers 中说明。
- 风险：单体 `app.js` 继续无边界膨胀。控制：本轮必须把 Storyboard 工作区逻辑按功能拆分函数边界；不要求框架迁移，但要求可测试、可扫描。
- 风险：误把本轮图像关联理解为批量分镜图生成。控制：只关联已有项目图像，不自动生成批量 shot 图。
- 风险：为稳定性添加备用 provider、假数据或默认降级。控制：严格遵守模型接入文档和用户备用策略约束；如确需备用策略，标为“需用户确认”。

## 为什么能支撑 LibTV 对齐

LibTV 的批量分镜图、批量视频和合成能力建立在可编辑、可确认、可资产化的 Storyboard 上游之上。Vidiom 当前已经能通过真实模型生成结构化 Storyboard，但用户还不能像 LibTV 脚本节点一样校正 shot、管理资产、整理关系和判断准备度。

本轮架构决策先补 Storyboard 编辑域模型、持久化事务、API 边界和生产台 UI，使人工确认后的 Storyboard 成为后续导出和媒体生成的事实来源。这样后续推进批量分镜图、视频片段、音频和导演台时，才不会把下游能力建立在不可编辑、不可确认的模型初稿上。
