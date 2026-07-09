# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮继续保持“真实模型接入与验收”为最高优先级，下一步仍不能切换到视频、音频、导演台、自由无限画布或其他 LibTV 对齐功能。

原因已经从“Storyboard 真实模型能力尚未实现”变化为“最新提交已经实现并记录真实 smoke 通过，但本轮产品任务的独立复验在真实语言 agent provider 调用阶段超过三分钟未完成”。在用户明确要求真实模型接入完成并通过验收前，产品需求不能马上切换到其他 LibTV 能力；下一步应先收口真实验收可重复性、长耗时状态和发布记录一致性。

当前事实判断：

- 最新提交为 `fcc1a57 Implement real storyboard generation workflow`，`main` 与 `origin/main` 对齐。
- 最新提交已覆盖 Storyboard 生成状态、真实 `gpt-5.5` Storyboard 生成、Studio 故事板页、shot 审阅、图像关联和测试。
- 自动化验证通过：`.venv/bin/python -m ruff check .` 通过；`.venv/bin/python -m pytest` 通过，58 passed，1 个 StarletteDeprecationWarning。
- README 迭代记录已写明上一轮真实 `.env` smoke 通过：临时数据库中 agent 完成 5/5 节点，Storyboard `gpt-5.5` completed（12 shots、17 assets），`gpt-image-2` 图像资产 completed，导出包包含 Storyboard。
- 本轮产品任务独立复验时 `.env` 存在；真实配置 smoke 使用临时数据库执行，但运行超过三分钟后仍停留在语言 agent provider 调用等待响应，已中断。本轮复验未完成 agent、Storyboard、图像和导出四段真实端到端链路。
- `tmp-image/` 抽样截图继续确认 LibTV 最新重点包含故事板、导演台、视频合成、真人素材合规、角色库和素材批量接入能力。

因此，产品侧暂不把下一步需求切换到视频、音频或导演台。下一步应交给架构师处理的主题是：**真实模型 Storyboard 接入的可重复验收与发布封口**。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力仍是脚本/故事板链路：

- 将剧本或故事想法拆解为结构化 shot。
- 提取角色、场景、道具等项目资产。
- 让用户检查、编辑、排序和确认 shot。
- 为每个 shot 合成可用于分镜图和视频片段的提示词。
- 将后续图像、视频和合成任务建立在 shot 与资产关系上。

抽样截图还显示，LibTV 正在强化导演台、视频合成、真人素材合规检测、角色库批量素材接入等能力。Vidiom 现阶段最短对齐路径仍是先把真实模型驱动的 Storyboard 主链路验收稳定，再谈下游素材和视频能力。

## Vidiom 当前已完成能力

Vidiom 已具备短剧 agent 工作流和部分真实模型基础：

- Studio Web 可创建项目、保存创作 Brief、运行 agent 画布、查看节点、Timeline 和 Review。
- Agent 流程覆盖 Premise、Character、Beat、Script、Production。
- 节点级生成指令、修订草稿、暂停/继续、失败重置、Review 编辑和 JSON 导出已存在。
- 完成项目可人工编辑脚本和拍摄包，并保存审阅备注、发布任务和交付清单。
- 语言 agent 已按产品记录接入 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`，且 README 记录过上一轮真实 `.env` smoke。
- 项目图像生成已按产品记录接入 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`，且 README 记录过上一轮真实 `.env` smoke。
- Storyboard 数据底座已具备：可保存 storyboard、shots、项目内资产、shot-asset 关系、shot-image 关系，并在导出包中体现 completed storyboard。
- 最新提交已经把 Storyboard 推进到可生成、可查看、可审阅、可关联项目图像资产的产品形态，并通过自动化测试与 README 记录的真实 smoke。

## 主要产品差距

### P0：真实模型端到端验收缺口

本轮最大缺口不是测试 fake client，也不是功能形态缺失，而是真实 provider 端到端验收需要可重复、可解释：

- README 已记录上一轮真实 smoke 通过，但本轮独立复验未完成，停留在语言 agent provider 调用等待响应阶段。
- 当前缺少“真实 smoke 可重复执行、超时或长等待可解释、复验结果可被下一轮产品任务直接判断”的产品闭环。
- 当前需要确认真实 `gpt-5.5` 在 agent 输出和 Storyboard 输出路径上的稳定性，而不是只依赖单次成功记录。
- 当前需要确认真实 `gpt-image-2` 在同一条复验链路中仍保持可用。

用户价值影响：用户已经看到产品形态接近 LibTV 的故事板工作流，但如果真实模型复验不可重复，仍可能在实际使用中卡在生成阶段，无法信任后续分镜、图像和导出结果。

### P0：长耗时与失败状态的产品验收缺口

本轮 smoke 暴露了真实 provider 长时间等待的产品风险：

- 如果用户触发生成后长时间没有结果，需要能看懂当前处于模型等待、生成中还是失败。
- 如果 provider 长耗时或中断，产品需要保留清晰状态和可审计记录。
- 不得把长耗时、失败或未完成状态显示成成功。
- 不得自动改走其他模型、假结果或占位结果；如架构师认为需要调用超时策略，应标为“需用户确认”。

用户价值影响：真实模型能力不仅要能调用，还要在等待、失败和恢复场景下保持可信。

### P0：Storyboard 发布记录与可交接状态缺口

README 迭代记录已经反映真实 Storyboard 开发产物和一次真实 smoke 通过记录，但本轮产品复验又出现长时间等待。架构师下一轮需要判断 smoke 记录、复验结果和用户真实等待体验如何统一成可交接的发布标准。

用户价值影响：如果文档只记录一次通过而不记录复验可重复性，后续产品任务可能过早切换到其他 LibTV 功能。

### P1：无限画布与节点系统差距

Vidiom 的画布仍是固定 agent 流程。LibTV 支持自由新建文本、图片、视频、音频、脚本节点，拖入素材、连线、复用、打组和保存工作流。

用户价值影响：Vidiom 目前更像结构化 agent 审阅台，还不是自由组织素材和生成任务的影视工作台。

### P1：资产/历史/项目管理差距

Vidiom 已有项目列表、activity、导出包和项目内 Storyboard 资产底座，但缺少 LibTV 左侧资产栏、历史记录、素材复用、跨项目资产库和画布级操作回溯。

用户价值影响：长项目和多版本生产时，用户难以沉淀角色、场景、风格和分镜资产。

### P2：图像、视频、音频和导演台差距

Vidiom 仍只有项目级图像生成、Storyboard 图像关联和故事板上游能力。LibTV 覆盖图像编辑、高清、扩图、重绘、擦除、抠图、全景、多角度、打光、分镜组、视频生成、剪辑、合成、音频工具、导演台 3D 构图、主体库、风格库、运镜控制和真人素材合规。

用户价值影响：Vidiom 距离完整 AI 影视创作工作台还有明显距离，但这些能力不应在真实模型主链路验收前抢占优先级。

## 风险

- 如果把单次真实 smoke 通过误判为长期稳定完成，会把后续产品建立在复验不充分的 provider 链路上。
- 如果忽略 provider 长耗时体验，用户会在真实生成中无法判断系统是否仍在工作。
- 如果 README 通过记录与本轮复验超时不被统一解释，下一轮架构拆解会失真。
- 如果 Storyboard 生成失败被包装成空数据或成功态，会破坏用户对生成链路的信任。
- 如果过早推进视频、音频、导演台或复杂图像工具，会绕过当前最关键的真实模型验收缺口。

## 优先级结论

下一步产品需求：**真实模型 Storyboard 可重复验收与发布封口**。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`

本轮产品任务不直接给开发下实现指令；请架构师先判断 README 真实 smoke 通过记录、本轮独立复验超时结果和发布验收缺口，再更新架构方案与开发任务。
