# Architecture Control Plan: Real Model Storyboard Acceptance

更新时间：2026-07-10 CST

## 读取输入

- 产品需求版本：`docs/next-product-requirement.md`，更新时间 2026-07-10 CST，主题为 Real Model Storyboard Acceptance。
- 差距判断：`docs/product-gap-analysis.md` 将 P0 缺口从“Storyboard 真实模型能力未实现”更新为“真实模型端到端验收不可重复、长耗时状态和发布记录需要收口”。
- LibTV 对齐目标：`docs/libtv-product-function-description.md` 要求脚本/故事板链路能把剧本拆成结构化 shot，提取角色/场景/道具，并为后续分镜图、视频片段和合成准备可信上游。
- 模型接入约束：`docs/model-provider-integration.md` 固定语言模型 `gpt-5.5`、图像模型 `gpt-image-2`，生产 runtime 不得生成假结果；缺少配置或 provider 失败必须进入可见失败状态。

## 当前实现状态

- 最新提交：`21713d0 Update product requirement for storyboard model acceptance`，当前 `main` 与 `origin/main` 对齐。
- 上一轮实现提交：`fcc1a57 Implement real storyboard generation workflow` 已落地真实 Storyboard generation attempt 状态模型、`gpt-5.5` Storyboard generator、Storyboard Web API、Studio 故事板页、shot 审阅、图像关联和导出包。
- 工作区存在未跟踪 `tmp-image/`，视为 LibTV 参考截图目录，本轮继续不纳入文档提交。
- README 迭代记录显示上一轮自动化测试通过，且一次真实 `.env` smoke 通过：agent 完成 5/5 节点，Storyboard `gpt-5.5` completed，`gpt-image-2` 图像资产 completed，导出包包含 Storyboard。
- 产品任务本轮独立复验时 `.env` 存在，但真实配置 smoke 在语言 agent provider 调用阶段等待超过三分钟后被中断，未完成 agent、Storyboard、图像和导出四段端到端链路。
- 当前 `src/vidiom/storyboard.py` 已有 `StoryboardContextBuilder`、`OpenAIStoryboardGenerator` 和 `generate_project_storyboard()`，但真实 provider 调用没有可复用的 smoke runner、阶段耗时记录或中断后的可交接验收结果。
- 当前 `src/vidiom/web.py` 使用 `BackgroundTasks` 运行 agent 与 Storyboard job；API 能表达 Storyboard `generating`、`completed`、`failed` 和保留旧成功结果，但真实长耗时时缺少面向验收的阶段级运行记录。
- 当前前端仍是无构建静态 Studio，已出现 Storyboard tab；长期仍需要前端模块化和 LibTV 式画布/资产/任务架构，但本轮产品明确不切换到无限画布、视频、音频或导演台。
- 当前测试覆盖 Storyboard storage、schema、generator、API、frontend smoke 和导出回归；缺少真实 `.env` 端到端 smoke 脚本、阶段化验收产物和 README 中对“上次通过、本轮复验超时”的统一解释。

## 架构判断

现有架构已经支撑本轮产品所需的 Storyboard 领域模型、持久化、API、Studio 展示、最小审阅和导出语义。本轮不应把首要开发任务设为新的 Storyboard UI 或下游 LibTV 能力，也不需要推翻已完成的 Storyboard 存储结构。

本轮真正阻碍发布的是真实模型验收闭环：一次真实 smoke 通过不能证明链路可重复，产品复验又暴露了语言 provider 长时间等待且无可交接阶段结果的问题。因此，本轮首要开发任务应是验收基础设施与运行状态收口，而不是继续堆叠功能。

本轮架构结论：

- 前端架构：本轮足够支撑 Storyboard 状态查看和审阅，但仍需保持 Storyboard 逻辑边界；不启动自由无限画布重构。
- 后端存储：Storyboard 一等表结构和 generation attempt 语义可继续沿用；需要补充真实 smoke run 记录或等价验收产物，避免 README、产品复验和实现状态互相矛盾。
- 数据模型：继续以 project、canvas nodes、generated image assets、storyboards、shots、story assets、shot-image links 为主，不把 Storyboard 回写成 agent 节点长文本。
- API 边界：现有 Storyboard API 可用；本轮只允许为状态观测和 smoke 验收补小边界，不新增视频、音频、导演台或跨项目资产库 API。
- 异步任务：`BackgroundTasks` 可继续用于 Studio 生成；真实 smoke runner 应从 CLI 或测试脚本层面顺序执行并记录阶段结果，避免只依赖浏览器轮询判断。
- Provider 抽象：继续复用 `OpenAICompatibleLanguageClient` 和 `OpenAICompatibleImageClient`；不加入备用模型、假数据或默认降级路径。
- 测试结构：现有 fake-client 自动化测试继续保留；新增真实 `.env` smoke 只作为显式手动/验收命令，不应让常规 pytest 消耗模型额度。
- README 迭代记录：必须同步写明自动化测试状态、真实 smoke 是否通过、若未通过具体停在哪个阶段，以及和上一轮通过记录的关系。

## 本轮架构决策

### 1. 首要改造：真实端到端 smoke runner 与验收记录

新增一个显式验收入口，按产品链路顺序执行：

1. 使用 `HM_BASE_URL`、`HM_LLM_APIKEY`、`gpt-5.5` 创建并运行 agent 项目。
2. 等待 Premise、Character、Beat、Script、Production 节点完成，记录每阶段开始、结束、耗时、状态和错误摘要。
3. 使用同一语言模型触发 Storyboard 生成，记录生成状态、shot 数、asset 数、错误摘要和是否保留旧成功结果。
4. 使用 `HM_BASE_URL`、`HM_IMG_APIKEY`、`gpt-image-2` 生成或复验一个项目图像资产。
5. 导出项目包并校验 Storyboard metadata、shots、assets、relations、image links 和 project image assets 摘要。
6. 将本次 smoke 结果写入一个可被下一轮产品/架构任务读取的验收文件，例如 `docs/real-model-smoke-result.md`。

该 runner 只做验收编排和状态记录，不引入备用模型、假 payload 或自动改走其他 provider。若开发认为需要 provider 调用超时策略，只能在文档中标为“需用户确认”，不得作为既定实现写入。

### 2. 长耗时、中断和未完成状态语义

产品要求用户能区分未开始、生成中、真实成功、真实失败、用户中断或任务未完成，以及已有旧成功结果但本次未成功。现有 Storyboard generation attempt 已覆盖 Storyboard 层的 completed/failed/generating 和旧结果保留；本轮需要把 smoke 验收阶段也结构化：

- `not_started`：阶段尚未触发。
- `running`：阶段已开始且仍在等待 provider 或后台任务。
- `completed`：阶段真实完成并通过结构校验。
- `failed`：provider、配置、schema、存储或导出错误。
- `interrupted`：验收 runner 被用户或外部进程中断。
- `incomplete`：总链路未完成，且不能写成通过。

这些状态用于验收记录和 README，不要求本轮扩大到完整任务队列系统。UI 已有生成中与失败显示；开发只需补足验收产物能说明真实 smoke 卡在哪个阶段。

### 3. API 与异步任务边界

本轮不重写 `BackgroundTasks` 架构。开发需要确认现有 API 响应满足：

- Storyboard 生成 POST 后立即落库 `generating`。
- 后台成功后落库 `completed` 和完整 shots/assets/relations。
- 后台失败后落库 `failed` 和 sanitised error message。
- 已有成功结果后再次失败时保留旧 shots，并通过 `has_completed_result`、`latest_attempt_failed`、`result_source` 或等价字段说明来源。
- 导出包只把明确存在的 completed Storyboard 作为交付结果，同时保留 latest attempt metadata。

若真实 smoke 证明 agent provider 长时间等待时用户侧看不到足够状态，开发可补充运行阶段活动记录或 README 说明，但不得把等待包装成成功。

### 4. 前端长期架构约束

用户已明确判断当前架构撑不住 LibTV 级产品，需要允许适时重构前端架构和后端存储结构。该约束继续有效：

- 当前单文件 `app.js` 只能作为短期 Studio 壳使用；后续推进自由无限画布、节点系统、资产栏、历史记录、视频/音频/导演台时，必须拆成模块化前端边界。
- 本轮产品目标仍是真实 Storyboard 验收封口，不能借此启动大规模前端重构。
- 新增 smoke 状态 UI 或文案时，应放在现有 Storyboard/Delivery 边界内，不把验收逻辑散落到脚本、拍摄、图像多个页面。

### 5. 后端长期数据模型方向

后端继续坚持一等领域表，而不是把所有能力塞进 JSON blob：

- 项目、agent 节点、Storyboard、shot、项目内故事资产、项目图像资产、shot-image link 继续保持独立结构。
- 后续 LibTV 对齐的画布节点、视频资产、音频资产、导演台构图、生成任务历史应新增领域边界和迁移，不复用 Storyboard 表承载无关能力。
- 本轮只允许新增 smoke run 记录文件或轻量验收记录结构，不做跨项目资产库迁移。

### 6. 测试策略

本轮新增测试与验证分两层：

- 自动化测试：继续使用 fake clients，覆盖 smoke runner 的阶段状态转换、错误脱敏、导出校验、README/验收文件写入格式和现有 Storyboard/API 回归。
- 真实验收：新增显式命令，读取 `.env` 并调用真实 `gpt-5.5` 与 `gpt-image-2`，结果写入验收文件；该命令不得在普通 pytest 中自动运行。

必须继续运行：

- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m pytest`
- `node --check src/vidiom/static/app.js`

如真实 `.env` smoke 未通过，README 和验收文件必须记录具体阶段、耗时、状态和错误摘要，不能写成通过。

## 风险与控制

- 风险：把 README 上一次真实 smoke 通过误读为当前可发布。控制：本轮要求写入新的可重复验收结果，并解释本轮三分钟等待中断发生在 agent provider 阶段。
- 风险：真实 provider 长时间等待时没有可交接状态。控制：smoke runner 记录阶段、耗时和 interrupted/incomplete 状态。
- 风险：为了收口验收而加入备用模型或假结果。控制：禁止备用模型、假 shot、占位 Storyboard 和默认降级路径；超时策略如需引入必须标为需用户确认。
- 风险：继续堆 Storyboard UI 或切换到视频/音频/导演台，绕开真实模型稳定性问题。控制：本轮开发任务只来自 Real Model Storyboard Acceptance。
- 风险：真实 smoke 输出泄露密钥。控制：只记录变量名、阶段、模型名和错误摘要，不输出 `.env` 值。
- 风险：真实 smoke 脚本依赖浏览器手工操作，下一轮产品无法复验。控制：提供 CLI/脚本化入口和结构化结果文件。

## 为什么能支撑 LibTV 对齐

LibTV 的脚本/故事板链路要求上游 shot、资产和 prompt 可信，后续分镜图、视频片段、音频和合成才能建立在稳定数据上。Vidiom 当前已经有 Storyboard 存储、真实生成、Studio 审阅和导出基础；本轮如果不先解决真实模型验收可重复性，就会把后续 LibTV 能力建立在不可判断的 provider 等待和发布记录冲突之上。

因此，本轮架构控制选择先补真实 smoke 验收闭环、长耗时/中断状态和文档一致性。完成后，下一轮产品才有依据判断是否进入更深 Storyboard 编辑、批量分镜图、自由画布或视频能力。
