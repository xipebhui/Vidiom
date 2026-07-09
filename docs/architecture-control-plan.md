# Architecture Control Plan: Storyboard Readiness and Asset Review Workspace

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Storyboard Readiness and Asset Review Workspace，包含准备度、shot 工作区、资产审阅、shot-asset 关系、项目图像关联和真实模型回归验收标准。
- 产品差距：`docs/product-gap-analysis.md` 判断真实模型主链路已通过，同轮 `gpt-5.5` agent、`gpt-5.5` Storyboard、`gpt-image-2` 项目图像和导出包均 completed；当前 P0 缺口是 Storyboard 准备度、资产审阅和前端可编辑工作区。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 强调脚本/故事板节点必须先检查并编辑 shot、角色、场景、道具、提示词和资产关系，再进入批量分镜图、批量视频与视频合成。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`；生产 runtime 不得生成假结果、备用 provider 结果或占位成功结果。
- 最新真实验收记录：`docs/real-model-smoke-result.md` 当前 overall status 为 `completed`，四段分别为 `agent_project`、`storyboard_generation`、`project_image_generation`、`export_package` completed。

## 当前实现状态

- 当前分支：`main`，与 `origin/main` 对齐。
- 最新提交：`3e06ffc Update product requirement for storyboard readiness`。
- 工作区存在未跟踪 `tmp-image/`，作为 LibTV 参考截图目录，本轮不纳入提交。
- README 最新迭代记录显示上一轮开发完成 Storyboard shot 编辑事务和 API 边界：更新单 shot、新增 shot、删除 shot、重排 shots、删除清理关系、排序安全重编号、`prompt_ready=false` 失效和 `storyboard_edit` activity。
- `src/vidiom/storage.py` 已有 `storyboards`、`storyboard_shots`、`project_story_assets`、`storyboard_shot_assets`、`storyboard_shot_image_assets`、`generated_image_assets` 和 `project_events`，并已新增 shot update/create/delete/reorder 事务方法。
- `src/vidiom/web.py` 已提供 `GET /api/projects/{project_id}/storyboard`、Storyboard 生成、shot review、shot CRUD、shot reorder、shot-image link/unlink 和项目导出 API。
- `src/vidiom/static/app.js` 的 Storyboard 页仍主要是展示型 Review 面板：可以生成故事板、显示 shots/assets/image links、批准或标记需修改、把已有项目图像以 `reference` 关联到选中 shot；尚不支持深度 shot 表单、新增/删除/排序、状态筛选、资产 CRUD、shot-asset 关系编辑、图像 link type 选择和解除关联的完整用户流程。
- `storage.get_project_storyboard()` 和 `_storyboard_response()` 尚未返回 readiness summary 或 per-shot blockers；`export_project_package()` 会导出当前 Storyboard，但尚未包含准备度摘要和 blockers。
- 测试已覆盖 Storyboard 生成、失败/中断语义、shot 编辑事务、导出、image link 和 API 基础路径；尚未覆盖 readiness 派生、asset CRUD、shot-asset 关系编辑、前端 Storyboard 生产台控件和导出准备度一致性。

## 架构判断

本轮产品需求有效且包含产品验收标准，因此不阻塞。当前架构已经具备 Storyboard 一等数据底座和 shot 局部编辑事务，不应再把首要任务设为 shot 后端基础改造。下一步必须把 Storyboard 准备度和阻塞项做成后端事实源，并补齐资产/关系编辑 API 和前端生产台，否则用户仍无法完成 LibTV 式“生成后检查、资产修正、提示词确认、导出前确认”的核心流程。

当前架构对本轮需求的支撑情况：

- 前端架构：现有静态单体 `app.js` 能承接本轮有限范围，但 Storyboard 相关逻辑必须局部模块化。长期看，该前端形态撑不住 LibTV 级自由无限画布、节点系统、图像/视频/音频资产、工作流、历史记录和导演台；这是长期架构约束。本轮产品明确不做自由无限画布和下游媒体生成，因此不启动全量框架迁移，但必须把 Storyboard 工作区拆出清晰函数边界。
- 后端存储：SQLite 表结构方向正确，Storyboard、shots、assets、relationships 和 image links 已是一等数据，不需要推倒重建。当前缺口是 readiness 派生、asset CRUD、shot-asset relation set/update、关系变化后的 `prompt_ready` 失效和导出包摘要。
- 数据模型：`review_status` 与 `prompt_ready` 继续作为用户确认字段；`readiness_summary` 和 `blockers` 必须由当前 shots、assets、relationships、image links 派生，不作为用户手写状态保存。
- API 边界：Storyboard 查询响应应成为 Studio 和导出前确认的事实来源，新增或扩展 API 应覆盖 readiness、asset CRUD、shot-asset relation set、图像关联 link type 和解除关联。编辑类 API 必须同步事务完成，不新增后台任务。
- 异步任务：本轮不新增批量分镜图、批量视频或后台媒体生成。真实 Storyboard 生成继续沿用现有后台任务；准备度计算和人工编辑保持同步事务。
- Provider 抽象：本轮不做新模型接入、模型替换、备用 provider、自动重试、假数据或占位结果。常规测试继续使用 fake clients，不自动消耗真实模型额度。
- 测试结构：优先补 Storage/API/导出一致性测试，再补前端静态断言与 `node --check`。真实 smoke completed 记录不得删除或改写为未验收。

## 本轮架构决策

### 1. 首要开发任务改为 Storyboard readiness 事实源

现有架构阻碍下一版需求落地的点已从 shot CRUD 转移到准备度判断。首要任务必须建立 readiness helper，并让 `GET /api/projects/{project_id}/storyboard` 与导出包返回同一份 `readiness_summary` 和 per-shot `blockers`。

准备度至少覆盖：

- shot 总数、已确认数、需修改数、未确认数、prompt 未准备数、有阻塞项 shot 数。
- `ready_for_media_generation` 仅作为提示字段，不触发媒体生成。
- per-shot blockers 覆盖未确认、需修改、prompt 未准备、画面描述缺失、图像提示词缺失、时长异常、缺少场景资产关系、角色/道具字段与关系需要复核。

### 2. 资产和关系编辑是第二层基础设施，不应只做前端备注

角色、场景、道具资产必须继续作为 `project_story_assets` 中的项目内生产对象。新增、编辑、删除资产以及调整 shot-asset 关系时，必须校验 project/storyboard/shot/asset 归属，删除资产不得留下悬空关系，受影响 shots 的 `prompt_ready` 必须回到 false，由用户重新确认。

### 3. 前端 Storyboard 工作区做局部模块化，不启动无限画布重构

本轮需要把现有 Storyboard 页从展示面板提升为生产台，但范围限定在 Review 的 Storyboard 页内。建议在 `app.js` 内拆出：

- Storyboard 数据加载、保存和错误显示。
- readiness summary 与状态筛选。
- shot 列表、选中态和详情编辑表单。
- shot 新增、删除、上移/下移或排序控件。
- asset 面板与 asset 表单。
- shot-asset relation editor。
- image link editor，支持 `reference` 与 `storyboard_frame`。

不引入大型前端框架迁移、自由无限画布、通用节点系统或下游生成器组。

### 4. 导出包必须与界面事实一致

`storage.export_project_package()` 中的 Storyboard deliverable 必须包含编辑后的 shots、assets、relationships、image_links、readiness_summary 和 per-shot blockers。不能出现界面显示已处理但导出包仍是模型初稿或缺少准备度摘要的分裂。

### 5. 不推进下游媒体生成

本轮需求只建立批量分镜图和视频生成前的可信上游。不新增批量 shot 图生成、批量视频、视频合成、音频、导演台、自由无限画布或跨项目资产库。任何长耗时保护、撤销版本、备用 provider、默认降级或自动切换策略如被认为必要，必须标为“需用户确认”，不得作为默认实现写入开发任务。

## 当前风险与控制

- 风险：readiness 只在前端临时计算，导出包和 API 不一致。控制：首要任务把 readiness 放到后端 helper，并由 API 和导出共同复用。
- 风险：资产编辑只改显示文案，不影响关系和准备度。控制：资产 CRUD 和关系编辑必须是事务型 Storage/API 能力，并让相关 shots `prompt_ready=false`。
- 风险：shot 字段和 relationships 脱节，用户不知道哪些镜头需要复核。控制：blockers 必须显式提示字段/关系需要复核，筛选能定位这些 shots。
- 风险：项目图像解除关联误删图片资产。控制：只删除 `storyboard_shot_image_assets` 关系，不删除 `generated_image_assets`。
- 风险：单体前端继续膨胀。控制：本轮 Storyboard 工作区必须按数据、列表、编辑、资产、关系、图像关联、readiness 拆函数边界。
- 风险：误把图像关联做成批量分镜图生成。控制：只关联已有项目图像，不自动调用 `gpt-image-2`。
- 风险：为稳定性引入备用 provider、假图、占位成功或默认降级。控制：遵守模型文档和用户约束；相关策略只能标为“需用户确认”。

## 为什么能支撑 LibTV 对齐

LibTV 的批量分镜图、批量视频和合成能力建立在可编辑、可确认、可资产化的 Storyboard 上游之上。Vidiom 已能通过真实模型生成结构化 Storyboard，并已具备 shot 后端编辑基础；下一步必须让用户在 Studio 中完成准备度判断、shot 修正、资产维护、关系整理和图像参考确认。

本轮架构决策把 Storyboard readiness 设为事实源，并补齐资产/关系/API/前端工作区边界。这样后续推进批量分镜图、视频片段、音频和导演台时，下游能力会建立在可保存、可导出、可解释的人工确认 Storyboard 上，而不是模型初稿或前端临时状态上。
