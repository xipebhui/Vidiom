# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮产品判断可以从“真实模型接入阻塞”切换为“真实模型主链路已验收通过后的 LibTV 故事板生产差距”。切换依据是仓库最新提交与最新真实验收记录已经满足用户此前设定的模型接入优先级：

- 当前分支为 `main`，最新提交为 `a8e2b54 Handle storyboard interrupt lifecycle and record completed smoke`，与 `origin/main` 对齐。
- 工作区仅存在未跟踪 `tmp-image/` 参考截图目录，本轮不纳入提交。
- README 最新迭代记录显示开发已完成 Storyboard 中断生命周期收口，并执行真实 `.env` smoke。
- `docs/real-model-smoke-result.md` 最新记录为 `completed`：`agent_project` 使用 `gpt-5.5` 完成 5/5 节点，`storyboard_generation` 使用 `gpt-5.5` 完成 18 shots/18 assets/119 relationships，`project_image_generation` 使用 `gpt-image-2` 完成 1 个项目图像资产，`export_package` completed。
- 最新真实 smoke 同轮覆盖 agent、Storyboard、项目图像和导出四段，并且四段均为 `completed`。因此，真实模型接入可以视为已完成当前产品验收。
- `docs/model-provider-integration.md` 的模型约束已在当前能力中落地：语言模型固定 `gpt-5.5`，图像模型固定 `gpt-image-2`，调用配置来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`，文档与验收文件未暴露密钥值。

因此，下一步产品需求不再继续停留在“完成真实模型接入”，而应交给架构师处理 LibTV 脚本/故事板链路的下一层核心差距：**Storyboard 可编辑生产台与资产审阅闭环**。

当前 Vidiom 已能把真实模型输出拆成结构化 Storyboard，但用户还不能像 LibTV 一样在批量生成前充分检查、编辑、排序、增删 shot，管理角色/场景/道具资产，并让资产变化影响 shot prompt 准备度。这是推进批量分镜图、视频片段和合成之前必须补上的产品能力。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力已经从“真实模型是否可用”转移到“生成后能否人工校正并资产化”：

- 将剧本或故事想法拆解为结构化 shot。
- 让用户逐格编辑 shot 信息，包括剧情、角色、场景、道具、画面描述、动作、声音、时长和提示词。
- 支持新增、删除、排序 shot，保证分镜节奏符合创作者判断。
- 提取并管理角色、场景、道具资产，支持编辑名称、描述、参考提示词和一致性说明。
- 将资产信息同步到相关 shot 的最终提示词与 prompt 准备状态。
- 在进入批量分镜图、批量视频和视频合成前，提供明确的检查和确认流程。

Vidiom 已具备 Storyboard 数据底座、真实生成入口、项目图像生成、shot-image 关联位置和导出包能力，但缺少足够可用的 Storyboard 编辑与资产审阅体验。

## Vidiom 当前已完成能力

Vidiom 已具备短剧 agent 工作流、真实模型调用、Storyboard 数据底座、真实 smoke 门禁和一次同轮 completed 验收：

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

## 主要产品差距

### P0：Storyboard 仍缺少深度编辑能力

当前 Storyboard 已经能生成和展示 shots，但用户仍不能完整编辑镜头生产数据。

当前产品缺口：

- 不能直接编辑每个 shot 的核心字段。
- 不能新增缺失 shot。
- 不能删除重复或无效 shot。
- 不能调整 shot 顺序。
- 不能在编辑后重新计算或标记 prompt 准备度。
- 不能把人工修改后的 Storyboard 作为后续分镜图、视频和导出的可信版本。

用户价值影响：真实模型已经能给出第一版分镜，但创作者还无法像使用 LibTV 脚本节点一样完成“生成后检查、修正、确认”的关键工作，后续批量生成会建立在未经充分校正的镜头表上。

### P0：角色、场景、道具资产仍停留在生成摘要

Vidiom 已能保存 Storyboard assets 和 shot-asset relationships，但用户缺少资产工作区。

当前产品缺口：

- 不能编辑角色、场景、道具资产的名称、描述、参考提示词和一致性说明。
- 不能新增模型漏提的资产。
- 不能删除无效资产。
- 不能把资产修改同步反映到相关 shot 的审阅状态或 prompt 准备状态。
- 不能清晰看到每个资产被哪些 shot 使用。
- 不能把已有项目图像作为资产参考图进行更明确的审阅管理。

用户价值影响：长故事中的角色、场景和道具一致性无法被用户主动维护，Vidiom 与 LibTV 在“资产化管理”上的差距仍然明显。

### P0：批量生成前的确认流程不足

LibTV 的故事板流程强调“先检查和编辑 shot，再进入批量生成”。Vidiom 目前已有 prompt_ready 与 review_status，但它们还不是完整的批量生成前确认体验。

当前产品缺口：

- 缺少按待处理、需修改、已确认、prompt 未准备等状态筛选 shots。
- 缺少 Storyboard 级完成度摘要。
- 缺少可见的阻塞项，例如缺少角色、缺少场景、提示词为空、时长异常或未确认镜头。
- 缺少导出前对 Storyboard 编辑状态的清晰说明。

用户价值影响：用户难以判断当前 Storyboard 是否已经可以进入批量分镜图或视频生成阶段。

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

Vidiom 尚未覆盖 LibTV 的视频生成、视频剪辑、视频合成、音频生成/提取/变速、导演台 3D 构图、主体库、风格库、运镜控制和真人素材合规。

用户价值影响：Vidiom 距离完整 AI 影视创作工作台还有明显距离，但这些能力应在 Storyboard 可编辑生产台和资产审阅闭环之后推进。

## 风险

- 如果把真实模型 smoke completed 误读为“已接近 LibTV 完整工作台”，会忽略 Storyboard 人工校正、资产一致性和批量生成前确认仍然缺失。
- 如果直接推进批量分镜图或视频生成，会把下游媒体产物建立在不可充分编辑的 shot 与资产数据上。
- 如果 Storyboard 编辑后不能进入导出包或后续生成语境，用户会看到界面修改与交付结果不一致。
- 如果资产编辑不能清楚影响哪些 shots，用户会失去对角色、场景和道具一致性的控制。
- 如果下一轮需求继续围绕已通过的真实模型接入，会浪费架构与开发窗口，无法缩小 LibTV 的核心生产体验差距。

## 优先级结论

下一步产品需求：**Storyboard 可编辑生产台与资产审阅闭环**。

本需求应先交给架构师判断当前 Storyboard 数据模型、Studio Review、项目图像资产、导出包和未来批量生成边界是否支撑，再由架构师拆解开发任务。产品任务不直接给开发下实现指令。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/real-model-smoke-result.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`
