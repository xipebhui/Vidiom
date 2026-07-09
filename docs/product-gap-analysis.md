# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮继续保持“真实模型接入与验收”为最高优先级，下一步仍不能切换到自由无限画布、视频、音频、导演台、资产库或其他 LibTV 对齐功能。

最新开发提交 `1534beb Strengthen real smoke release gate` 已完成真实 smoke 发布门禁强化：`vidiom smoke-real-model-storyboard` 只有在 agent、Storyboard、项目图像和导出包四段全部 `completed` 时才视为通过；未通过时会返回非零状态，并且仍会写入 `docs/real-model-smoke-result.md`。这解决了“验收命令可能被误判为通过”的问题，但没有完成真实模型接入验收。

最新 `docs/real-model-smoke-result.md` 显示本轮真实 `.env` smoke 总状态为 `interrupted`：

- `agent_project` 使用 `gpt-5.5` 完成 5/5 agent 节点，耗时 178.121 秒。
- `storyboard_generation` 使用 `gpt-5.5` 等待 291.208 秒后被中断。
- `project_image_generation` 为 `incomplete`。
- `export_package` 为 `incomplete`。

因此，当前产品结论是：**真实模型发布门禁已经建立，但真实模型端到端链路仍未通过；下一步产品需求必须继续交给架构师处理 Storyboard 阶段中断/长耗时导致的端到端验收阻塞。**

当前事实判断：

- 当前分支为 `main`，最新提交为 `1534beb Strengthen real smoke release gate`，与 `origin/main` 对齐。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，本轮不纳入产品文档提交。
- README 迭代记录显示本轮开发已完成真实 smoke 门禁强化，并记录验证结果：`tests/test_smoke.py` 9 passed、全量 pytest 67 passed、ruff 通过、`node --check` 通过、`git diff --check` 通过。
- 最新真实 smoke 已不再停在 provider 503；agent 阶段已完成，但 Storyboard 阶段中断，图像与导出未进入同一轮 completed 验收。
- `docs/model-provider-integration.md` 仍约束语言模型使用 `gpt-5.5`，图像模型使用 `gpt-image-2`，调用地址和密钥来自 `HM_BASE_URL`、`HM_LLM_APIKEY`、`HM_IMG_APIKEY`，且不得生成假成功结果。
- `docs/architecture-control-plan.md` 和 `docs/development-task-breakdown.md` 仍主要围绕上一轮 provider 503 和门禁强化展开；门禁强化已经由最新开发提交完成，下一轮架构师需要基于最新 `interrupted` 结果更新架构判断和开发拆解。
- 抽样查看 `tmp-image/` 和读取 `docs/libtv-product-function-description.md` 后，LibTV 重点差距仍包括无限画布、自由节点、脚本/故事板深度编辑、角色/场景/道具资产化、批量分镜图、视频合成、音频工具和导演台。但这些下游能力都依赖可信的真实模型上游。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力仍是脚本/故事板主链路：

- 将剧本或故事想法拆解为结构化 shot。
- 提取角色、场景、道具等项目资产。
- 让用户检查、编辑、排序和确认 shot。
- 为每个 shot 合成可用于分镜图和视频片段的提示词。
- 将后续图像、视频和合成任务建立在 shot 与资产关系上。

Vidiom 已经具备 Storyboard 数据底座和真实生成入口，但最新真实验收停在 Storyboard 生成阶段。只要 Storyboard 不能在真实环境中完成，后续批量分镜图、视频片段、导演台和合成能力就缺少可信上游。

## Vidiom 当前已完成能力

Vidiom 已具备短剧 agent 工作流、真实模型调用基础、Storyboard 数据底座和真实 smoke 门禁：

- Studio Web 可创建项目、保存创作 Brief、运行 agent 画布、查看节点、Timeline 和 Review。
- Agent 流程覆盖 Premise、Character、Beat、Script、Production。
- 节点级生成指令、修订草稿、暂停/继续、失败重置、Review 编辑和 JSON 导出已存在。
- 完成项目可人工编辑脚本和拍摄包，并保存审阅备注、发布任务和交付清单。
- 语言 agent 已接入 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`；缺少配置或 provider 错误会进入可见失败状态。
- 项目图像生成已接入 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`；项目图像资产可在 Studio 查看并进入导出语境。
- Storyboard 数据底座已具备：可保存 storyboard、shots、项目内资产、shot-asset 关系、shot-image 关系，并在导出包中体现 completed storyboard。
- Storyboard Studio 能触发真实 `gpt-5.5` 生成，显示生成状态、失败错误、结构化 shots、资产摘要和图像关联。
- `vidiom smoke-real-model-storyboard` 已能按 agent、Storyboard、项目图像和导出阶段记录真实 smoke 状态。
- smoke 发布门禁已要求四段全部 completed 才算通过；failed、interrupted 或 incomplete 不再被命令层误判为发布通过。

## 主要产品差距

### P0：真实模型端到端验收仍未通过

当前最大缺口已经从“缺少门禁”变化为“门禁正确阻塞，但最新真实链路未 completed”：

- 最新真实 smoke 总状态为 `interrupted`。
- agent 阶段已完成，说明 `gpt-5.5` agent 主链路本轮走通。
- Storyboard 阶段等待 291.208 秒后中断，未产生本轮 completed Storyboard 结果。
- 项目图像与导出阶段为 `incomplete`，没有在同一轮真实验收中复验通过。
- 因为总状态不是 `completed`，真实模型接入不能视为完成。

用户价值影响：用户可以看到 agent 真实生成能力推进到了下一段，但仍无法依赖完整“agent -> Storyboard -> 图像 -> 导出”的真实工作流完成创作交付。

### P0：Storyboard 阶段长耗时/中断是新的发布阻塞

最新阻塞点位于 Storyboard 生成阶段，而不是 provider 503。产品侧需要架构师判断这代表外部服务响应时间、调用窗口、验收运行环境或任务生命周期控制问题，但不能把中断包装成通过。

当前产品缺口：

- 需要明确 Storyboard 阶段长时间运行后中断时，用户、产品任务和架构任务如何判断发布状态。
- 需要确认中断时不会生成假 Storyboard、假图像资产或假导出包。
- 需要确保结果文件、README、产品需求、架构计划和开发拆解都以最新 `interrupted` 作为当前状态。
- 如需讨论调用超时、自动重试、排队等待、验收窗口延长或人工复跑策略，必须标为“需用户确认”，不能作为既定 fallback 或默认降级路径写入方案。

用户价值影响：用户需要知道 Storyboard 卡在真实模型生成阶段，而不是误以为图像、导出或 LibTV 下游能力已经具备稳定上游。

### P0：图像与导出仍缺少同一轮真实通过证据

因为最新 smoke 在 Storyboard 阶段中断，`gpt-image-2` 项目图像和导出包没有在同一轮验收中完成。

当前产品缺口：

- 无法确认当前环境下真实 Storyboard 能稳定完成 shot 与资产生成。
- 无法确认当前环境下 `gpt-image-2` 图像能力能在同一条端到端链路中完成复验。
- 无法确认导出包在当前真实链路中包含 completed Storyboard。
- 历史通过记录证明能力曾走通，但不能替代最新门禁结果。

用户价值影响：后续分镜图、视频片段、导演台构图和合成都依赖这一条上游链路，不能在最新门禁未通过时继续扩功能。

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

- 如果把“门禁已经建立”误读为“真实模型接入已经完成”，会绕过最新 Storyboard 中断事实。
- 如果把历史真实 smoke 通过记录当作当前发布状态，会覆盖最新 `interrupted` 结果。
- 如果产品需求继续围绕上一轮 provider 503，而忽略本轮 agent 已完成、Storyboard 中断的新状态，架构师会基于过期事实拆解任务。
- 如果为了解决中断而引入备用模型、假数据、占位 Storyboard 或默认降级路径，会违背用户约束并破坏验收可信度。
- 如果过早推进视频、音频、导演台或复杂图像工具，会把下游能力建立在未通过验收的模型主链路上。

## 优先级结论

下一步产品需求：**真实模型端到端验收完成：Storyboard 中断与下游未复验阻塞处理**。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/real-model-smoke-result.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`

本轮产品任务不直接给开发下实现指令。请架构师先基于最新 smoke 门禁已完成但真实验收仍为 `interrupted` 的事实，更新架构方案和开发任务，再路由给开发。
