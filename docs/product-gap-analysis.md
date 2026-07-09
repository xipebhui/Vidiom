# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮继续保持“真实模型接入与验收”为最高优先级，下一步仍不能切换到视频、音频、导演台、自由无限画布或其他 LibTV 对齐功能。

原因已经从“缺少真实模型 Storyboard 验收入口”变化为“真实端到端验收入口已经建立，但最新真实 `.env` smoke 未通过”。最新提交 `8b24c8f Add real model storyboard smoke runner` 已新增 `vidiom smoke-real-model-storyboard`，并将真实验收结果写入 `docs/real-model-smoke-result.md`。该结果显示本轮真实 smoke 总状态为 `failed`：`agent_project` 阶段调用 `gpt-5.5` 等待 73.444 秒后，provider 返回 503 `system_cpu_overloaded`；Storyboard、项目图像和导出阶段均为 `incomplete`。

在用户明确要求真实模型接入完成并通过验收前，产品需求不能切换到其他 LibTV 能力。下一步应交给架构师处理的主题是：**真实模型端到端验收通过门槛与 provider 503 发布阻塞处理**。

当前事实判断：

- 当前分支为 `main`，最新提交为 `8b24c8f Add real model storyboard smoke runner`，与 `origin/main` 对齐。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，本轮不纳入产品文档提交。
- README 迭代记录显示 smoke runner 开发已完成，并记录自动化验证通过：`.venv/bin/python -m ruff check .` 通过；`.venv/bin/python -m pytest` 通过，63 passed；`node --check src/vidiom/static/app.js` 通过；`git diff --check` 通过。
- `docs/real-model-smoke-result.md` 显示最新真实 `.env` smoke 未通过，失败阶段为 `agent_project`，语言模型为 `gpt-5.5`，错误为 provider 503 `system_cpu_overloaded`。
- README 仍保留上一轮真实 smoke 通过记录：agent 完成 5/5 节点，Storyboard `gpt-5.5` completed（12 shots、17 assets），`gpt-image-2` 图像资产 completed，导出包包含 Storyboard。该记录证明能力曾经走通，但不能替代本轮失败结果。
- `docs/model-provider-integration.md` 仍约束语言模型使用 `gpt-5.5`，图像模型使用 `gpt-image-2`，调用地址和密钥来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`，且不得生成假成功结果。
- 抽样查看 `tmp-image/` 中 LibTV 截图后，继续确认 LibTV 重点包含故事板 shot 编辑、角色/场景/道具资产化、人像质感调节、导演台、视频合成和工作流画布。Vidiom 当前最短对齐路径仍是先把真实模型主链路验收稳定。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力仍是脚本/故事板链路：

- 将剧本或故事想法拆解为结构化 shot。
- 提取角色、场景、道具等项目资产。
- 让用户检查、编辑、排序和确认 shot。
- 为每个 shot 合成可用于分镜图和视频片段的提示词。
- 将后续图像、视频和合成任务建立在 shot 与资产关系上。

抽样截图还显示，LibTV 正在强化导演台、人像质感调节、视频合成、角色库批量素材接入和素材合规能力。Vidiom 现阶段不应直接追这些下游功能；如果真实模型主链路不能在当前配置下完成，后续分镜图、视频和导演台能力都会建立在不可信上游之上。

## Vidiom 当前已完成能力

Vidiom 已具备短剧 agent 工作流、真实模型调用基础和 Storyboard 验收入口：

- Studio Web 可创建项目、保存创作 Brief、运行 agent 画布、查看节点、Timeline 和 Review。
- Agent 流程覆盖 Premise、Character、Beat、Script、Production。
- 节点级生成指令、修订草稿、暂停/继续、失败重置、Review 编辑和 JSON 导出已存在。
- 完成项目可人工编辑脚本和拍摄包，并保存审阅备注、发布任务和交付清单。
- 语言 agent 已接入 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`；缺少配置或 provider 错误会进入可见失败状态。
- 项目图像生成已接入 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`；项目图像资产可在 Studio 查看并进入导出语境。
- Storyboard 数据底座已具备：可保存 storyboard、shots、项目内资产、shot-asset 关系、shot-image 关系，并在导出包中体现 completed storyboard。
- Storyboard Studio 能触发真实 `gpt-5.5` 生成，显示生成状态、失败错误、结构化 shots、资产摘要和图像关联。
- `vidiom smoke-real-model-storyboard` 已能按 agent、Storyboard、项目图像和导出阶段记录真实 smoke 状态，并避免把失败、中断或未完成写成成功。

## 主要产品差距

### P0：真实模型端到端验收未通过

当前最大缺口不是缺少验收命令，而是最新真实验收仍然失败：

- 最新 `docs/real-model-smoke-result.md` 总状态为 `failed`。
- `agent_project` 阶段未完成，provider 返回 503 `system_cpu_overloaded`。
- Storyboard、项目图像和导出阶段均未运行完成，因此不能宣称真实端到端链路通过。
- 上一轮曾有真实 smoke 通过记录，但本轮失败说明模型链路仍未达到可发布的重复验收门槛。

用户价值影响：用户可能在创建项目后卡在第一段真实语言 agent 生成，无法进入 Storyboard、图像或导出流程。只要该链路未通过，Vidiom 就还不能被视为完成真实模型接入。

### P0：provider 503 与发布阻塞缺口

最新失败来自 provider 503 `system_cpu_overloaded`。产品侧需要架构师判断这是否属于外部服务不可用、调用策略不足、验收窗口问题或发布阻塞条件，但不能把它包装成通过。

当前产品缺口：

- 需要明确真实 smoke 的发布门槛：哪些阶段必须 completed，哪些计数必须存在，哪些错误会阻止切换到下一类 LibTV 需求。
- 需要明确 provider 503 出现时，用户、产品任务和架构任务如何判断当前发布状态。
- 需要避免 README 里的历史通过记录掩盖当前失败结果。
- 如需讨论调用超时、重试或等待窗口策略，必须标为“需用户确认”，不能作为既定 fallback 写入需求或方案。

用户价值影响：用户需要知道失败是发生在真实模型服务阶段，而不是误以为 Storyboard、图像或导出功能本身已经通过。

### P0：真实 Storyboard 下游仍缺少本轮通过证据

因为最新 smoke 在 agent 阶段失败，Storyboard、`gpt-image-2` 项目图像和导出包没有在同一轮验收中被复验通过。

当前产品缺口：

- 无法确认当前环境下 `gpt-5.5` agent 输出能够稳定进入 Storyboard 输入。
- 无法确认当前环境下真实 Storyboard 仍能完成 shot 与资产生成。
- 无法确认当前环境下 `gpt-image-2` 图像能力在同一条端到端链路中仍可用。
- 无法确认导出包在当前真实链路中包含 completed Storyboard。

用户价值影响：后续分镜图、视频片段、导演台构图和合成都依赖这一条上游链路，不能在未通过时继续扩功能。

### P1：无限画布与节点系统差距

Vidiom 的画布仍是固定 agent 流程。LibTV 支持自由新建文本、图片、视频、音频、脚本节点，拖入素材、连线、复用、打组和保存工作流。

用户价值影响：Vidiom 目前更像结构化 agent 审阅台，还不是自由组织素材和生成任务的影视工作台。

### P1：资产/历史/项目管理差距

Vidiom 已有项目列表、activity、导出包、项目图像资产和项目内 Storyboard 资产底座，但缺少 LibTV 左侧资产栏、历史记录、素材复用、跨项目资产库和画布级操作回溯。

用户价值影响：长项目和多版本生产时，用户难以沉淀角色、场景、风格和分镜资产。

### P2：图像、视频、音频和导演台差距

Vidiom 仍只有项目级图像生成、Storyboard 图像关联和故事板上游能力。LibTV 覆盖图像编辑、高清、扩图、重绘、擦除、抠图、全景、多角度、打光、分镜组、视频生成、剪辑、合成、音频工具、导演台 3D 构图、主体库、风格库、运镜控制和真人素材合规。

用户价值影响：Vidiom 距离完整 AI 影视创作工作台还有明显距离，但这些能力不应在真实模型主链路验收前抢占优先级。

## 风险

- 如果把上一轮真实 smoke 通过误判为当前发布通过，会绕过最新 provider 503 失败。
- 如果把 provider 503 视为“非产品问题”而切换到其他功能，用户仍会在真实生成第一步失败。
- 如果 README、真实 smoke 结果和产品需求之间状态不一致，架构师下一轮会基于错误事实拆解任务。
- 如果为了解决失败而引入备用模型、假数据、占位 Storyboard 或默认降级路径，会违背用户约束并破坏验收可信度。
- 如果过早推进视频、音频、导演台或复杂图像工具，会把下游能力建立在未通过验收的模型主链路上。

## 优先级结论

下一步产品需求：**真实模型端到端验收通过门槛与 provider 503 发布阻塞处理**。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/real-model-smoke-result.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`

本轮产品任务不直接给开发下实现指令。请架构师先基于最新 smoke runner 已完成但真实验收失败的事实，判断架构方案和开发任务是否需要继续围绕真实 provider 失败状态、发布门槛和验收记录收口。
