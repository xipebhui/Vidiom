# Next Product Requirement: Real Model End-to-End Acceptance Gate

更新时间：2026-07-10 CST

交接对象：架构师

## 产品目标

Vidiom 下一版必须先解除真实模型端到端验收未通过的发布阻塞。最新提交已经建立真实 smoke runner，并能把 agent、Storyboard、项目图像和导出阶段写入结构化验收记录；但最新 `docs/real-model-smoke-result.md` 显示真实 `.env` smoke 总状态为 `failed`，失败发生在 `agent_project` 阶段：`gpt-5.5` provider 返回 503 `system_cpu_overloaded`，后续 Storyboard、项目图像和导出阶段均为 `incomplete`。

本需求的目标是让架构师围绕“真实模型端到端验收通过门槛”继续拆解，而不是转向其他 LibTV 能力。只有当当前配置下的 `gpt-5.5` agent、`gpt-5.5` Storyboard、`gpt-image-2` 项目图像和导出包在同一轮真实 smoke 中完成并记录通过，产品侧才可考虑下一轮切换到 Storyboard 深度编辑、批量分镜图、无限画布、视频、音频或导演台。

## 用户价值

用户需要的是一个能在真实模型环境中完成创作主链路的产品，而不是只在 fake client 或历史单次成功记录中成立的演示。完成本需求后，用户应能：

- 用真实 `gpt-5.5` 完成短剧 agent 输出。
- 用真实 `gpt-5.5` 将完成项目拆成结构化 Storyboard shots。
- 用真实 `gpt-image-2` 生成或复验项目图像资产。
- 导出包含真实成功 Storyboard 的项目包。
- 在 provider 503、配置缺失、模型输出异常、任务中断或未完成时看到明确状态。
- 通过 README 和验收文档判断当前版本是否真的达到真实模型接入完成标准。

## 功能范围

### 1. 真实模型验收通过门槛

架构师需要把下一轮方案聚焦在真实模型验收门槛上。产品侧要求同一轮真实 smoke 至少覆盖：

- Agent 项目运行完成，语言模型为 `gpt-5.5`。
- Storyboard 生成完成，语言模型为 `gpt-5.5`。
- 项目图像生成或复验完成，图像模型为 `gpt-image-2`。
- 导出包生成完成，并包含 completed Storyboard 的摘要、shots、资产和图像关联信息。
- 验收记录明确写入总状态、阶段状态、模型名、耗时、关键计数和错误摘要。

任一阶段为 `failed`、`interrupted` 或 `incomplete` 时，产品侧视为真实模型接入尚未完成，不应切换到其他 LibTV 功能。

### 2. provider 503 发布阻塞处理

最新真实 smoke 失败点是 `agent_project` 阶段 provider 503 `system_cpu_overloaded`。架构师需要判断这个失败对产品发布的含义，并给出后续处理方案。

产品侧要求：

- 不得把 provider 503 写成通过。
- 不得用上一轮历史通过记录覆盖最新失败记录。
- 不得生成假 agent 输出、假 Storyboard、假图像资产或假导出包。
- 不得自动改用其他模型、备用 provider 或默认降级路径。
- 如架构师认为需要调用超时、自动重试、排队等待或其他调用策略，必须标为“需用户确认”，不能作为既定方案直接进入开发任务。

### 3. 用户可理解的失败与未完成状态

真实模型调用可能失败、长时间等待或被中断。产品需要继续保证用户和下一轮自动化任务能区分：

- 未开始。
- 生成中。
- 真实成功。
- 真实失败。
- 中断。
- 未完成。
- 已有旧成功结果但本次没有成功。

失败和未完成状态不得显示为成功。错误信息应说明失败阶段、模型名、配置变量名或 provider 错误摘要，但不得暴露 `HM_LLM_APIKEY`、`HM_IMG_APIKEY` 或实际密钥值。

### 4. 现有 Storyboard 与图像能力回归

虽然本轮主需求不是新增功能，但必须确认已完成能力没有退化：

- Studio 仍可触发 Storyboard 生成并查看状态。
- 成功 Storyboard 仍能展示 shot 列表、角色/场景/道具资产摘要、prompt 准备度和审阅状态。
- 项目图像能力仍使用 `gpt-image-2`。
- 已有项目图像仍可与 Storyboard shot 建立关联。
- 成功 Storyboard 仍能进入导出包；未生成、失败或未完成的 Storyboard 不得作为成功产物导出。

### 5. 文档与交接状态同步

下一轮架构和开发完成后，文档必须让产品任务能直接判断当前版本状态：

- README 明确区分历史真实 smoke 通过记录和最新真实 smoke 结果。
- `docs/real-model-smoke-result.md` 保留最新真实验收结果。
- 如果真实 smoke 仍失败，写清失败阶段和错误摘要。
- 如果真实 smoke 通过，写清 agent、Storyboard、项目图像和导出四段均 completed，以及关键计数。
- 文档不得包含 secret values。

## 关键用户流程

1. 用户创建项目，填写一句话和 Brief。
2. 用户运行 agent，等待真实 `gpt-5.5` 生成脚本和拍摄包。
3. 如果 agent 阶段失败，用户看到失败阶段和可理解错误，不会看到 Storyboard 或导出假成功。
4. 如果 agent 阶段成功，用户进入 Storyboard 视图，触发真实 `gpt-5.5` Storyboard 生成。
5. 用户查看结构化 shot 列表、资产摘要、prompt 准备度和审阅状态。
6. 用户生成或复验一个 `gpt-image-2` 项目图像资产，并理解其与 Storyboard 的关系。
7. 用户导出项目包，包内包含真实成功 Storyboard 结果。
8. 下一轮产品任务读取验收记录，能判断当前版本是通过、失败、未完成还是需要用户确认外部调用策略。

## 体验要求

- 真实模型验收状态必须可读、可追溯、可交接。
- 生成中、失败、中断、未完成、旧成功结果和本次成功状态应清晰区分。
- Provider 503 应显示为真实失败或发布阻塞，不得被弱化为普通提示。
- Shot 和资产展示仍应保持镜头生产结构，而不是退化成长文本。
- 错误信息不得暴露密钥值。
- 不得出现假生成结果、占位成功结果或静默成功。
- 真实 smoke 结果应能被下一轮产品任务直接读取和判断。

## 产品验收标准

### 真实模型链路验收

- 使用真实 `.env` 配置时，agent 项目运行 completed，并产生结构化脚本和拍摄包。
- Storyboard 生成 completed，并使用 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`。
- Storyboard 成功结果包含多个结构化 shot，并覆盖顺序、剧情关联、角色、场景、道具、画面描述、动作/表演、对白/声音、建议时长、视觉要求和图像 prompt。
- 项目图像生成或复验 completed，并使用 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`。
- 导出包 completed，并包含 Storyboard metadata、shots、资产摘要和图像关联摘要。
- `docs/real-model-smoke-result.md` 总状态为 completed，且四个核心阶段均为 completed。

### 失败与阻塞验收

- Provider 返回 503 时，验收结果显示对应阶段 failed，不显示 completed。
- 后续未运行阶段显示 incomplete 或等价未完成状态，不被伪造成成功。
- 缺少 `HM_BASE_URL`、`HM_LLM_APIKEY` 或 `HM_IMG_APIKEY` 时，对应阶段进入可见失败状态。
- Provider 错误、非结构化结果或任务中断时，用户和验收文档能看到失败或未完成状态。
- 已有成功 Storyboard 后再次生成失败，不得让用户误以为旧结果是本次成功结果。
- 错误信息不得包含密钥值。

### Studio 审阅验收

- 用户可从 Studio 进入 Storyboard 视图或等价工作区。
- 用户可查看 Storyboard 状态、shot 列表、资产摘要和图像关联位置。
- 每个 shot 能展示 prompt 准备度和审阅状态。
- 旧项目没有 Storyboard 时，不得在界面或导出包中伪造 Storyboard。

### 文档验收

- README 明确记录最新真实 smoke 是通过、失败还是未完成。
- README 明确区分上一轮历史通过记录与最新验收结果。
- `docs/real-model-smoke-result.md` 包含 run timestamp、总状态、阶段状态、模型名、关键计数和错误摘要。
- 产品、架构和开发文档对“真实模型接入是否完成”的判断一致。

### 回归验收

- 自动化检查继续通过。
- 现有 agent、项目图像生成、项目创建、运行、暂停、修订、Review 编辑、交付导出保持可用。
- 常规测试不得自动消耗真实模型额度。

## 非目标

本轮不切换到其他 LibTV 对齐功能：

- 不做自由无限画布节点创建。
- 不做完整 shot 深度编辑器作为唯一目标。
- 不做跨项目资产库。
- 不做批量分镜图生成。
- 不做图像编辑、全景、多角度、打光、九宫格、标注或分镜组完整工具套件。
- 不做批量视频生成。
- 不做视频剪辑或视频合成。
- 不做音频生成、提取、变速或音视频分离。
- 不做导演台 3D 构图。
- 不做主体库、风格库、自定义风格、运镜控制或真人素材合规校验。
- 不做自动改用其他模型、备用 provider、假数据或占位结果。

## 与 LibTV 的对应关系

本需求对应 LibTV 脚本/故事板链路中的“真实模型拆解剧本为结构化分镜并形成可信上游”阶段：

- 从剧本或故事想法拆解为结构化 shot。
- 提取角色、场景、道具等项目资产摘要。
- 生成用于后续分镜图和视频片段的 prompt。
- 为批量分镜图、批量视频和视频合成建立可信上游。

LibTV 的导演台、视频合成、人像质感调节、真人素材合规、图像编辑和资产库能力仍是后续差距。但在 Vidiom 最新真实 smoke 仍失败的情况下，这些能力不应成为下一轮主需求。

## 架构师处理要求

请架构师基于本文档判断最新提交、README 迭代记录、`docs/real-model-smoke-result.md` 的 provider 503 失败结果，以及 `docs/model-provider-integration.md` 的模型约束，更新：

- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`

架构师应保留实现路径判断权，再将可执行开发任务交给开发任务处理。本产品需求不直接指定代码文件、类名、数据库表结构或实现步骤。
