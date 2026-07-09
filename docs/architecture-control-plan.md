# Architecture Control Plan: Real Model Storyboard Generation

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Real Model Storyboard Generation。
- 差距判断：`docs/product-gap-analysis.md` 将 P0 缺口锁定为真实 `gpt-5.5` Storyboard 生成、可见状态、Studio 审阅和导出闭环。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 要求脚本/故事板链路能把剧本拆成结构化 shot，提取角色/场景/道具，并为后续分镜图、视频片段和合成准备 prompt。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，缺少必需配置或 provider 失败时必须进入可见失败状态，不得生成假结果。

## 当前实现状态

- 最新提交：`7c0f348 Refocus product requirement on real model storyboard generation`，当前 `main` 与 `origin/main` 对齐。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，不纳入本轮文档提交。
- README 迭代记录显示上一轮已完成 Storyboard 领域模型与存储基础：`storyboards`、`storyboard_shots`、`project_story_assets`、`storyboard_shot_assets`、`storyboard_shot_image_assets` 表，导出包可包含 completed storyboard。
- 当前 `src/vidiom/storyboard_schema.py` 已定义 Storyboard schema 和本地校验；`src/vidiom/storyboard.py` 只负责 payload normalize，尚未实现真实模型生成器、上下文组装或 provider 调用。
- 当前 `src/vidiom/web.py` 已有项目创建、agent run、Review 编辑、项目图像生成和导出 API；尚无 `GET/POST /api/projects/{project_id}/storyboard`，也无 Storyboard 生成后台任务。
- 当前前端仍是单文件 `src/vidiom/static/app.js`，Review tabs 已有脚本、角色、拍摄、图像、检查、交付；尚无 Storyboard 工作区。
- 当前测试覆盖 Storyboard 存储迁移、schema、导出和 shot-image 关联 helper；尚未覆盖真实 Storyboard generator、状态 API、失败语义、Studio 入口或真实配置 smoke。

## 架构判断

上一轮存储改造让 Storyboard 具备一等领域底座，现有架构已经能承载 shot、项目内资产、shot-asset 关系和 shot-image 关系。本轮不需要先推翻该存储结构，但必须补一个轻量状态模型改造：当前单个 `storyboards.status` 不足以清晰表达“已有成功结果，但本次重新生成失败”的产品语义。

本轮架构结论：

- 后端存储：基本支撑，但需要增加 latest generation attempt 语义，避免 failed 状态覆盖或伪装旧 completed 结果。
- 数据模型：继续以 project 内 storyboard/shot/asset/relationship 表为核心，不回退到 `canvas_nodes.output_json`。
- API 边界：必须新增 Storyboard 查询和生成 API，并把生成状态、错误、旧结果标识作为一等响应字段。
- 异步任务：沿用现有 FastAPI `BackgroundTasks`，但生成 job 必须和 Web handler 分离，状态必须落库。
- Provider 抽象：复用 `LanguageJSONClient` 和 `OpenAICompatibleLanguageClient`，新增 Storyboard generator 领域层，不复用固定 agent step schema。
- 前端架构：本轮可继续无构建静态前端，但 Storyboard 渲染、生成、状态和审阅逻辑必须形成独立函数边界；长期仍应从单文件 Review 面板演进为可承载 LibTV 式画布、节点、资产和任务的模块化前端。
- 测试结构：必须从 storage-only 测试扩展到 generator、API、失败状态、前端 smoke 和导出回归。

## 本轮架构决策

### 1. 首要改造：真实生成状态与旧结果语义

在真实 provider 接入前，先让 Storyboard 状态能表达最新尝试与已完成结果的关系。推荐方向：

- 保留 `storyboards` 作为当前项目 Storyboard 聚合根。
- 增加字段或等价结构记录最新生成尝试：
  - `generation_status`: `not_started`、`generating`、`completed`、`failed`
  - `generation_started_at`
  - `generation_finished_at`
  - `generation_error_message`
  - `last_completed_at`
  - `last_completed_model`
- `shots/assets/relations` 表保存最后一次成功结果。
- 如果已有成功结果后重新生成失败，API 必须返回 `generation_status=failed` 且 `has_completed_result=true`，前端显示“本次生成失败，可查看上次成功结果”，不得显示为本次成功。
- 导出包只导出明确 completed 的 Storyboard 结果；如果 latest generation failed 但保留旧结果，导出中必须标明该结果不是本次失败尝试的产物。

该改造是为满足产品“旧结果状态与失败状态清晰区分”的必要条件，不是备用生成策略。

### 2. Storyboard Generator 领域边界

新增或扩展 `src/vidiom/storyboard.py`：

- `StoryboardContextBuilder`：从项目 seed、Brief、Premise、Character、Beat、Script、Production 和 `generated_image_assets` 组装输入。
- `OpenAIStoryboardGenerator`：依赖 `LanguageJSONClient`，固定通过 settings 使用 `gpt-5.5`。
- `generate_project_storyboard(storage, project_id, model, client)`：完成项目校验、上下文组装、provider 调用、schema 校验、normalize、持久化和失败记录。
- 生成器不得调用任何假数据、占位 shot 或备用文本拆段逻辑。

### 3. API 边界

本轮必须新增：

- `GET /api/projects/{project_id}/storyboard`
  - 返回 storyboard generation 状态、错误、shots、assets、relationships、image links、项目 image asset 摘要。
- `POST /api/projects/{project_id}/storyboard/generate`
  - 仅允许 completed 项目触发。
  - 请求受理后写入 `generating`，后台调用真实 `gpt-5.5`。
  - 成功写入 shots/assets/relations 并标记 `completed`。
  - 失败写入 `failed` 和错误信息，不写入占位结果，不清空最后成功结果。
- `PATCH /api/projects/{project_id}/storyboard/shots/review`
  - 最小审阅接口，允许更新 shot `review_status` 和必要的 `prompt_ready` 修正；不做完整深度编辑器。
- Shot 与图像资产 link/unlink API 可复用上一轮 storage helper，本轮若前端需要入口则补 Web API。

所有请求模型使用 Pydantic 校验，错误信息只暴露变量名、模型调用阶段或 provider 错误摘要，不暴露密钥值。

### 4. 前端架构方向

本轮不实现自由无限画布，也不做完整 shot 深度编辑器。Studio 必须新增 Storyboard 视图或等价工作区：

- Review tab 增加“故事板”。
- 显示未生成、生成中、成功、失败、失败但有旧结果五类状态。
- 显示 shot 列表：顺序、剧情/节拍、角色、场景、道具、画面、动作、对白/声音、时长、视觉要求、image prompt、prompt 准备度、审阅状态、图像关联。
- 显示项目内角色、场景、道具资产摘要和它们出现的 shot。
- 显示已有项目图像资产与 shot 的关联位置。
- Delivery/导出页显示 Storyboard 是否进入交付包，以及 shots、assets、image links 计数。

为控制前端长期风险，新增函数应集中命名为 `storyboard*`，避免把 Storyboard 状态散落到现有脚本和拍摄编辑函数中。若开发判断单文件继续膨胀影响实现，可拆出 `src/vidiom/static/storyboard.js`，但不得引入构建链路作为本轮前置条件。

### 5. 后端存储与导出方向

上一轮表结构可沿用；本轮只做必要补充：

- Storyboard 状态必须区分 latest generation attempt 与 completed result。
- 查询 API 返回 `has_completed_result`、`latest_attempt_failed` 或等价布尔字段，供 UI 避免旧结果误读。
- 导出包包含 completed Storyboard 的 shots、assets、relations、image links、generation metadata。
- 未生成或只有失败尝试的项目不得导出假 Storyboard。
- 项目级 `generated_image_assets` 继续保持独立，不迁移为 shot 私有资产。

### 6. 测试策略

本轮新增测试必须覆盖：

- Storage migration：旧库迁移后新增 generation attempt 字段或表，不破坏上一轮 Storyboard 数据。
- Storyboard generator：fake `LanguageJSONClient` 验证模型名是 `gpt-5.5`，上下文包含 seed、Brief、agent 输出和 image assets。
- 失败状态：缺少 `HM_BASE_URL`、缺少 `HM_LLM_APIKEY`、provider 抛错、非结构化 payload 都进入 failed 状态，不产生 placeholder shots。
- Web API：GET 未生成、POST 受理、后台成功、后台失败、已有成功后再失败的响应语义。
- Frontend smoke：Storyboard tab、生成入口、状态文案、shot 列表、资产摘要和导出计数标记存在。
- Regression：现有 agent 运行仍使用 `gpt-5.5`，项目图像生成仍使用 `gpt-image-2`，项目创建、运行、暂停、修订、Review、图像和导出测试保持通过。

## 风险与控制

- 风险：只在前端展示 schema 样例，会形成假 Storyboard。控制：生成结果只能来自真实 provider 或测试 fake client，生产 runtime 不写占位结果。
- 风险：单一 `status` 覆盖旧结果，导致“本次失败但旧结果看起来成功”。控制：先补 generation attempt 语义，再接入生成 API。
- 风险：直接复用 agent canvas 输出字段承载 Storyboard。控制：继续使用上一轮独立 Storyboard 表，不写入 `canvas_nodes.output_json` 作为唯一来源。
- 风险：前端单文件继续无边界膨胀。控制：Storyboard 函数和状态独立命名，必要时拆静态模块。
- 风险：真实 provider 错误泄露密钥。控制：错误只记录变量名和阶段，不输出 secret value。
- 风险：为追 LibTV 一次性做无限画布、视频、音频或导演台。控制：本轮只完成真实模型 Storyboard 生成与验收闭环。

## 为什么能支撑 LibTV 对齐

LibTV 的脚本/故事板链路以 shot 为下游生产单位，以角色/场景/道具资产保证一致性，以 prompt 和图像/视频关联继续推进素材生成。本轮架构把 Vidiom 已有 Storyboard 存储底座接入真实 `gpt-5.5`、可见状态、Studio 审阅和导出包，先保证“脚本到结构化分镜”的上游可信。后续批量分镜图、视频片段、音频和导演台都能围绕已有 shot 与 asset 结构扩展，而不是继续在项目级脚本或单张图像上堆叠不可维护功能。
