# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮产品判断维持在真实模型主链路已完成验收后的 LibTV 故事板生产差距，但需要基于最新开发结果调整需求重点。

当前仓库状态：

- 当前分支为 `main`，最新提交为 `c72ea2a Add storyboard shot editing transactions and APIs`，与 `origin/main` 对齐。
- 工作区存在未跟踪 `tmp-image/` 参考截图目录，本轮只抽样核对，不纳入提交。
- README 最新迭代记录显示上一轮开发完成的是 Storyboard shot 编辑事务和 API 边界：更新单 shot、新增 shot、删除 shot、重排 shots、prompt ready 失效、删除清理关系和 activity 记录。
- 上一轮严格完成架构拆解 Task 1，尚未完成 readiness summary/blockers、资产 CRUD、shot-asset 关系编辑、项目图像关联审阅增强和前端 Storyboard 可编辑生产台。
- `docs/real-model-smoke-result.md` 最新记录仍为 `completed`：`agent_project` 使用 `gpt-5.5` 完成 5/5 节点，`storyboard_generation` 使用 `gpt-5.5` 完成 18 shots/18 assets/119 relationships，`project_image_generation` 使用 `gpt-image-2` 完成 1 个项目图像资产，`export_package` completed。
- `docs/model-provider-integration.md` 的模型约束仍成立：语言模型固定 `gpt-5.5`，图像模型固定 `gpt-image-2`，配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`；文档与验收记录未暴露密钥值。

因此，用户此前要求的“真实模型接入完成并通过验收前不得切换需求”已经满足：同轮真实 smoke 已 completed，且后续开发没有删除或改写该验收记录。本轮产品需求不回退到模型接入，也不切换到视频、音频、导演台或无限画布，而应继续沿 LibTV 脚本/故事板主链路推进。

下一步产品需求应从上一版宽泛的“Storyboard 可编辑生产台与资产审阅闭环”收束为：**Storyboard 准备度、资产审阅与可编辑工作区收口**。

原因是后端 shot 编辑 API 已建立，但用户仍不能在 Studio 中完整完成 LibTV 所强调的“检查并编辑 shot、角色、场景、道具、提示词，再进入批量生成”的关键流程。当前最重要的产品差距已经不是单个 shot 能否被后端保存，而是用户能否看到准备度、处理阻塞项、维护资产与关系，并在前端工作区完成可验收的编辑闭环。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力仍集中在脚本/故事板节点：

- 将剧本或故事想法拆解为结构化 shot。
- 让用户逐格编辑 shot 信息，包括剧情、角色、场景、道具、画面描述、动作、声音、时长和提示词。
- 支持新增、删除、排序 shot，保证分镜节奏符合创作者判断。
- 提取并管理角色、场景、道具资产，支持编辑名称、描述、参考提示词和一致性说明。
- 将资产信息同步到相关 shot 的最终提示词与 prompt 准备状态。
- 在进入批量分镜图、批量视频和视频合成前，提供明确的检查和确认流程。
- 参考截图抽样显示 LibTV 还具备运镜预设、自定义运镜、视频与音频分离、画布节点连线等更下游能力；这些仍是后续差距，但不应早于 Storyboard 上游确认闭环。

Vidiom 已具备 Storyboard 数据底座、真实生成入口、项目图像生成、shot-image 关联位置、导出包能力和 shot 编辑 API 基础，但缺少面向用户的完整 Storyboard 准备度与资产审阅体验。

## Vidiom 当前已完成能力

Vidiom 当前已具备以下能力：

- Studio Web 可创建项目、保存创作 Brief、运行 agent 画布、查看节点、Timeline 和 Review。
- Agent 流程覆盖 Premise、Character、Beat、Script、Production。
- 节点级生成指令、修订草稿、暂停/继续、失败重置、Review 编辑和 JSON 导出已存在。
- 完成项目可人工编辑脚本和拍摄包，并保存审阅备注、发布任务和交付清单。
- 语言 agent 已接入 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`；缺少配置或 provider 错误会进入可见失败状态。
- 项目图像生成已接入 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`；项目图像资产可在 Studio 查看并进入导出语境。
- Storyboard 数据底座已具备：可保存 storyboard、shots、项目内资产、shot-asset 关系、shot-image 关系，并在导出包中体现 completed storyboard。
- Storyboard Studio 能触发真实 `gpt-5.5` 生成，显示生成状态、失败错误、中断状态、结构化 shots、资产摘要和图像关联。
- Storyboard 生成会区分最新尝试与最后一次成功结果；失败或中断不会清空旧 shots，也不会把旧结果伪装成本次成功。
- `vidiom smoke-real-model-storyboard` 已能按 agent、Storyboard、项目图像和导出阶段记录真实 smoke 状态，并要求四段全部 completed 才算通过。
- 最新真实 smoke 已通过同轮四段验收，证明当前仓库具备真实模型主链路。
- 最新开发已补齐 Storyboard shot 的后端局部编辑基础：更新、新增、删除、排序、sequence 保持、prompt ready 失效、删除关联清理、activity 记录和 API 测试。

## 主要产品差距

### P0：Storyboard 准备度与阻塞项仍缺少产品闭环

LibTV 的故事板流程强调“先检查和编辑，再进入批量生成”。Vidiom 当前虽然有 `prompt_ready` 与 `review_status`，但还没有可被用户理解和操作的 Storyboard 级准备度。

当前产品缺口：

- 缺少 Storyboard 总体完成度摘要。
- 缺少按未确认、需修改、已确认、prompt 未准备、有阻塞项筛选 shots 的体验。
- 缺少 per-shot 阻塞项说明，例如缺少画面描述、缺少提示词、缺少关键资产、时长异常或未确认镜头。
- 导出包尚不能把 Storyboard 准备度与阻塞项作为事实来源交付给下一阶段。
- 用户难以判断当前 Storyboard 是否可以进入批量分镜图或视频生成阶段。

用户价值影响：真实模型和后端编辑能力已经存在，但创作者仍缺少“哪些镜头还能生成、哪些必须先修”的判断面板，后续媒体生成容易建立在未确认的镜头表上。

### P0：角色、场景、道具资产仍停留在生成摘要

Vidiom 已能保存 Storyboard assets 和 shot-asset relationships，但用户缺少资产工作区。

当前产品缺口：

- 不能编辑角色、场景、道具资产的名称、描述、参考提示词和一致性说明。
- 不能新增模型漏提的资产。
- 不能删除无效资产。
- 不能把资产修改同步反映到相关 shot 的审阅状态或 prompt 准备状态。
- 不能清晰看到每个资产被哪些 shots 使用。
- 不能调整 shot 与资产的关系。

用户价值影响：长故事中的角色、场景和道具一致性无法被用户主动维护，Vidiom 与 LibTV 在“资产化管理”上的差距仍然明显。

### P0：前端 Storyboard 工作区尚未承接后端编辑能力

最新开发已经完成 shot 编辑的后端基础，但 Studio 的 Storyboard 页仍主要是展示和轻审阅。

当前产品缺口：

- 用户不能在前端工作区完成 shot 深度编辑。
- 用户不能在前端新增、删除、排序 shots。
- 用户不能在一个工作区内联动查看 shot、资产、关系、项目图像和准备度。
- 现有项目图像关联仍偏基础，缺少更明确的 link type、解除关联、关联覆盖状态和导出前摘要。

用户价值影响：产品能力对普通用户仍不可见或不可完成；后端 API 已具备基础，但还没有转化为 LibTV 式的创作工作流体验。

### P1：批量分镜图能力尚未开始

Vidiom 已有项目级 `gpt-image-2` 图像生成和 shot-image 关联，但尚不支持按 Storyboard shots 批量创建分镜图任务。

用户价值影响：用户仍需要手动围绕项目生成单张图，不能把确认后的 shot 列表转化为一组镜头图像产物。

### P1：无限画布与自由节点系统差距

Vidiom 的画布仍是固定 agent 流程。LibTV 支持自由新建文本、图片、视频、音频、脚本节点，拖入素材、连线、复用、打组和保存工作流。

用户价值影响：Vidiom 目前更像结构化 agent 审阅台，还不是自由组织素材和生成任务的影视工作台。

### P1：资产/历史/项目管理差距

Vidiom 已有项目列表、activity、导出包、项目图像资产和项目内 Storyboard 资产底座，但缺少 LibTV 左侧资产栏、历史记录、素材复用、跨项目资产库和画布级操作回溯。

用户价值影响：长项目和多版本生产时，用户难以沉淀角色、场景、风格和分镜资产。

### P2：视频、音频和导演台差距

Vidiom 尚未覆盖 LibTV 的视频生成、视频剪辑、视频合成、音频生成/提取/变速、导演台 3D 构图、主体库、风格库、自定义风格、运镜控制和真人素材合规。

用户价值影响：Vidiom 距离完整 AI 影视创作工作台还有明显距离，但这些能力应在 Storyboard 准备度、资产审阅和可编辑工作区收口之后推进。

## 风险

- 如果把后端 shot API 完成误读为“Storyboard 编辑台已完成”，会忽略用户仍无法在 Studio 内完成资产审阅、关系维护、准备度筛选和阻塞项处理。
- 如果直接推进批量分镜图或视频生成，会把下游媒体产物建立在未完成准备度确认和资产一致性维护的 Storyboard 上。
- 如果资产编辑不能清楚影响哪些 shots，用户会失去对角色、场景和道具一致性的控制。
- 如果准备度只停留在隐藏字段或不可解释布尔值，用户无法知道下一步该修哪个 shot。
- 如果继续围绕已通过的真实模型接入重复建设，会浪费架构与开发窗口，无法缩小 LibTV 的核心生产体验差距。
- 如果引入备用 provider、假图、占位成功或自动降级，会违背用户明确约束；如确需相关策略，必须标为“需用户确认”。

## 优先级结论

下一步产品需求：**Storyboard 准备度、资产审阅与可编辑工作区收口**。

本需求应先交给架构师判断当前 Storyboard 编辑 API、数据模型、Studio Review、项目图像资产、导出包和未来批量生成边界是否支撑，再由架构师更新架构方案和开发任务拆解。产品任务不直接给开发下实现指令。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/real-model-smoke-result.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`
