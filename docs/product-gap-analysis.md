# Product Gap Analysis

更新时间：2026-07-10 CST

## 本轮产品判断

本轮必须继续保持“真实模型接入与验收”为最高优先级。原因不是基础 provider 完全缺失，而是当前仓库只完成了项目级语言 agent 与项目级单张图像生成的真实模型闭环；最新一轮开发完成的是 Storyboard 领域模型与存储基础，尚未把 LibTV 对齐所需的故事板生成流程接入真实 `gpt-5.5` 并通过端到端验收。

当前事实判断：

- 已完成：Premise、Character、Beat、Script、Production agent 使用 OpenAI-compatible `gpt-5.5`，并有 README 记录的真实 `.env` smoke test。
- 已完成：项目图像生成使用 OpenAI-compatible `gpt-image-2`，可生成并持久化项目级图像资产。
- 已完成：Storyboard、shot、项目内角色/场景/道具资产、shot-image 关联具备存储和导出基础。
- 未完成：用户无法从完成项目触发真实 `gpt-5.5` Storyboard 生成。
- 未完成：Studio 还没有可见的 Storyboard 生成、成功、失败、编辑和验收体验。
- 未完成：缺少“真实模型生成 Storyboard 后可审阅、可导出、可回归验证”的产品闭环。

因此，下一步产品需求不能切换到视频、音频、导演台、复杂图像工具或自由无限画布；必须继续围绕 `docs/model-provider-integration.md` 的真实模型约束，把模型接入推进到 Storyboard 主链路。

## LibTV 参考能力

LibTV 的核心价值是把创意、脚本、资产、分镜、图像、视频、音频和合成组织在同一个 AI 影视工作台中。对 Vidiom 当前阶段最关键的参考能力是脚本/故事板：

- 将剧本或故事想法拆解为结构化 shot。
- 提取角色、场景、道具等项目资产。
- 让用户检查、编辑、排序和确认 shot。
- 为每个 shot 合成可用于分镜图和视频片段的提示词。
- 将后续图像、视频和合成任务建立在 shot 与资产关系上。

`tmp-image/` 抽样截图也显示，LibTV 最新能力重点包括故事板、导演台、图像调节、视频合成和真人素材生成。Vidiom 目前最短的对齐路径仍是先把真实模型驱动的故事板生成做扎实。

## Vidiom 当前已完成能力

Vidiom 已具备短剧 agent 工作流和部分模型基础：

- Studio Web 可创建项目、保存创作 Brief、运行 agent 画布、查看节点、Timeline 和 Review。
- Agent 流程覆盖 Premise、Character、Beat、Script、Production。
- 节点级生成指令、修订草稿、暂停/继续、失败重置、Review 编辑和 JSON 导出已存在。
- 完成项目可人工编辑脚本和拍摄包，并保存审阅备注、发布任务和交付清单。
- 语言 agent 已使用 `HM_BASE_URL`、`HM_LLM_APIKEY` 和 `gpt-5.5`。
- 项目图像生成已使用 `HM_BASE_URL`、`HM_IMG_APIKEY` 和 `gpt-image-2`。
- Storyboard 数据底座已具备：可保存 storyboard、shots、项目内资产、shot-asset 关系、shot-image 关系，并在导出包中体现 completed storyboard。

## 主要产品差距

### P0：真实模型 Storyboard 生成与验收缺口

Storyboard 目前只有数据底座，尚未成为用户可触发、可观察、可验收的真实模型功能：

- 完成项目不能在 Studio 中触发真实 `gpt-5.5` Storyboard 生成。
- 系统尚未用真实模型从脚本、角色、节拍、拍摄包、Brief 和已有图像资产生成结构化 shot。
- 用户无法看到 Storyboard 生成中、成功、失败或错误状态。
- 缺少真实配置缺失或 provider 错误时的 Storyboard 可见失败验收。
- 缺少 Storyboard 生成后刷新可见、导出可见、回归可测的产品闭环。

用户价值影响：用户虽然能得到真实模型脚本和项目图像，但还不能把这些结果推进到 LibTV 式逐镜头生产；当前 Storyboard 底座对用户仍不可用。

### P0：Storyboard 审阅体验缺口

LibTV 的故事板不是后台数据，而是创作者逐镜头决策界面。Vidiom 目前缺少：

- shot 列表视图。
- 单个 shot 的画面、动作、对白/声音、角色、场景、道具、时长和 prompt 检查。
- shot 审阅状态和 prompt 准备度。
- 项目内角色、场景、道具资产与 shot 关系的可视化。
- 已有图像资产与 shot 关联位置的产品呈现。

用户价值影响：即使后端能保存 storyboard，用户也无法完成“检查、修改、确认、交付”的真实工作。

### P1：无限画布与节点系统差距

Vidiom 的画布仍是固定 agent 流程。LibTV 支持自由新建文本、图片、视频、音频、脚本节点，拖入素材、连线、复用、打组和保存工作流。

用户价值影响：Vidiom 目前更像结构化 agent 审阅台，还不是自由组织素材和生成任务的影视工作台。

### P1：资产/历史/项目管理差距

Vidiom 已有项目列表、activity、导出包和项目内 Storyboard 资产底座，但缺少 LibTV 左侧资产栏、历史记录、素材复用、跨项目资产库和画布级操作回溯。

用户价值影响：长项目和多版本生产时，用户难以沉淀角色、场景、风格和分镜资产。

### P2：图像、视频、音频和导演台差距

Vidiom 只有项目级首张图像生成和 Storyboard 的图像关联底座。LibTV 覆盖图像编辑、高清、扩图、重绘、擦除、抠图、全景、多角度、打光、分镜组、视频生成、剪辑、合成、音频工具、导演台 3D 构图、主体库、风格库、运镜控制和真人素材合规。

用户价值影响：Vidiom 仍停留在“真实模型脚本与首个视觉资产”，距离完整 AI 影视创作工作台还有明显距离。

## 风险

- 如果继续推进视频、音频、导演台或复杂图像工具，会绕过当前最关键的真实模型 Storyboard 验收缺口。
- 如果 Storyboard 只停留在存储层，用户仍无法感知 LibTV 式脚本到分镜生产线。
- 如果 Storyboard 生成没有真实 `gpt-5.5` 回归，后续分镜图、视频和合成都会建立在不可验收的上游结果上。
- 如果真实模型错误被包装成空数据或成功态，会破坏用户对生成链路的信任。
- 如果下一轮产品需求继续泛化为“Storyboard 全量能力”，架构师和开发可能优先做编辑 UI，而不是先补齐真实模型生成闭环。

## 优先级结论

下一步产品需求：**真实模型驱动的 Storyboard 生成与验收闭环**。

该需求延续用户最新优先级：在真实模型接入完成并通过验收前，不切换到其他 LibTV 对齐功能。具体到当前仓库，基础 agent 与项目图像已接入真实模型，但 Storyboard 作为下一条核心生产链路尚未完成真实 `gpt-5.5` 生成、可见失败和端到端验收，因此应成为架构师下一轮处理主题。

架构师下一轮应读取：

- `docs/product-gap-analysis.md`
- `docs/next-product-requirement.md`
- `docs/model-provider-integration.md`
- `docs/libtv-product-function-description.md`
- `docs/architecture-control-plan.md`
- `docs/development-task-breakdown.md`
