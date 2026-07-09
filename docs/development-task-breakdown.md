# Development Task Breakdown: Storyboard Shot Assetization

更新时间：2026-07-10 CST

产品需求来源：`docs/next-product-requirement.md`，Storyboard Shot Assetization，更新时间 2026-07-10 CST。

首要执行项：先完成 Storyboard 领域模型、存储迁移、API 边界和测试基础，再开发生成与前端 UI。现有架构缺少 storyboard/shot/asset 一等模型，直接堆 UI 会阻碍后续 LibTV 对齐。

## Task 1: 建立 Storyboard 领域模型与存储基础

目标：新增可持久化、可编辑、可导出的 storyboard、shot、项目内资产和关联数据结构。

产品需求来源：

- 故事板生成验收：结构化故事板持久化，刷新后仍可查看。
- Shot 编辑验收：查看、编辑、新增、删除、调整顺序和标记状态。
- 资产化验收：角色、场景、道具资产与 shot 对应关系。
- 分镜图准备验收：shot 与生成图像资产之间的关联位置。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/storyboard_schema.py`
- `src/vidiom/storyboard.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`
- `README.md`

实现步骤：

1. 新增 `storyboard_schema.py`，定义 `STORYBOARD_SCHEMA` 和本地校验函数；schema 至少包含 `shots`、`assets`、`relationships`。
2. 在 `storage.migrate()` 中新增表：`storyboards`、`storyboard_shots`、`project_story_assets`、`storyboard_shot_assets`、`storyboard_shot_image_assets`。
3. 为旧库迁移增加幂等建表和索引；不得破坏现有 `projects`、`canvas_nodes`、`generated_image_assets`。
4. 新增 Storage 方法：创建/获取 storyboard、更新生成状态、替换生成结果、批量保存 shots、批量保存 assets、保存 shot-asset 关系、保存/删除 shot-image 关系。
5. `get_project()` 可以继续返回现有字段，但新增 `get_project_storyboard(project_id)` 专门服务 storyboard API。
6. `export_project_package()` 在存在 completed storyboard 时加入 `deliverables.storyboard`，包含 shots、assets、relations 和 image asset 关联摘要；旧项目没有 storyboard 时不得伪造字段内容。
7. 为 storyboard 修改写入 `project_events`，事件类型建议包含 `storyboard_generation`、`storyboard_edit`、`story_asset_edit`、`storyboard_image_link`。

验收标准：

- 空库迁移后具备所有 storyboard 表和索引。
- 已存在项目库迁移后，原项目、节点、Review notes 和 image assets 可读取。
- completed 项目可保存并重新读取 storyboard、shots、assets 和关系。
- 导出包在存在 storyboard 时包含完整 storyboard 摘要。

测试要求：

- 新增 storage migration 测试，覆盖空库和含旧表的库。
- 新增 schema 校验测试，缺少 shot 必填字段、资产类型非法、空 prompt 均应失败。
- 新增导出包测试，验证 storyboard 和现有 image assets 同时存在。
- 运行 `.venv/bin/python -m pytest`。

是否允许/要求重构：要求。该任务是后端存储和领域边界基础改造。

风险和注意事项：

- 不要把 storyboard 存进 `canvas_nodes.output_json` 作为唯一来源。
- 不要把项目级 `generated_image_assets` 改成只属于 shot；通过关联表兼容已有项目图像。
- 不要引入备用生成器、占位 storyboard 或静默成功路径。

## Task 2: 接入真实模型 Storyboard 生成流程

目标：使用 `gpt-5.5` 从 completed 项目的脚本、角色、节拍、拍摄包、Brief 和已有图像资产生成结构化 storyboard。

产品需求来源：

- 故事板生成必须使用真实语言模型能力，并保持可见成功或失败状态。
- 每个 shot 包含顺序、剧情/节拍、角色、场景、道具、画面描述、动作、对白/声音摘要、建议时长、画幅/视觉风格和图像 prompt。
- 不得产生假生成结果、占位成功结果或静默成功。

影响文件/模块：

- `src/vidiom/storyboard.py`
- `src/vidiom/storyboard_schema.py`
- `src/vidiom/providers.py`
- `src/vidiom/web.py`
- `src/vidiom/config.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 在 `storyboard.py` 新增 `OpenAIStoryboardGenerator`，依赖 `LanguageJSONClient`，模型名从 `Settings.language_model` 传入。
2. 组装生成上下文：`project.seed_text`、`brief`、`premise`、`characters`、`beats`、`script`、`production`、已有 `image_assets`。
3. 调用 `client.generate_json(model="gpt-5.5", schema_name="storyboard", schema=STORYBOARD_SCHEMA, ...)`。
4. 生成前校验项目必须为 `completed`，且 script 和 production 节点已 completed。
5. Web 层新增 `POST /api/projects/{project_id}/storyboard/generate`，使用 `BackgroundTasks` 启动生成工作。
6. 请求受理后将 storyboard 状态写为 `generating`；成功写入 shots/assets/relations 并标记 `completed`；异常写入 `failed` 和错误信息。
7. 新增 `GET /api/projects/{project_id}/storyboard` 返回状态、错误、shots、assets、relations、image links。
8. 生成失败不能清空上一次已完成 storyboard；是否覆盖旧 storyboard 由“重新生成”按钮显式触发，默认生成只在没有进行中任务时执行。

验收标准：

- completed 项目可触发 storyboard 生成，并在完成后读取多个 shot。
- Fake language client 测试能证明调用模型为 `gpt-5.5`。
- 缺少必需模型配置时，API 返回项目可见的 storyboard failed 状态。
- 生成失败时 `project_events` 记录错误，UI 可读取错误文案。

测试要求：

- fake client 成功生成测试。
- fake client 抛错测试。
- 非 completed 项目触发生成返回 400。
- 已缺 script 或 production 输出的 completed 异常状态返回 400。
- `tests/test_web.py` 覆盖 GET/POST storyboard API。

是否允许/要求重构：允许。可抽出后台 job helper，但不要引入通用任务系统作为本轮前置条件。

风险和注意事项：

- 不能复用 `OpenAICanvasAgent` 的固定 agent step schema；storyboard 是独立生成器。
- 不要把模型错误吞掉后返回空 shots。
- 生成上下文必须包含已有项目图像资产 metadata，但不得要求一定已有图像。

## Task 3: 实现 Shot 编辑、排序和审阅状态 API

目标：让用户可以保存人工编辑后的 shot 列表，并保证顺序、状态和 prompt 准备度进入后续导出和生成上下文。

产品需求来源：

- 用户可查看、编辑、新增、删除和调整 shot 顺序。
- 用户可标记 shot 审阅状态。
- 编辑后的故事板会被保存，并进入项目导出包。
- 编辑不会破坏现有脚本、拍摄包、项目图像和 Review 数据。

影响文件/模块：

- `src/vidiom/web.py`
- `src/vidiom/storage.py`
- `src/vidiom/storyboard_schema.py`
- `tests/test_web.py`
- `tests/test_storyboard.py`

实现步骤：

1. 新增 Pydantic 请求模型：shot id 可选、`sequence_index`、`review_status`、`beat_ref`、`scene_ref`、`characters`、`scene`、`props`、`visual_description`、`action_focus`、`dialogue_or_sound`、`duration_seconds`、`aspect_ratio`、`visual_style`、`image_prompt`、`prompt_ready`。
2. 新增 `PATCH /api/projects/{project_id}/storyboard/shots`，采用完整列表保存语义，后端统一重排 `sequence_index`。
3. 删除前校验被删除 shot 的 image link 是否同步删除；允许删除关联记录，但不得删除原始 `generated_image_assets`。
4. 保存后写入 `storyboard_edit` event，摘要包含 shot 数、approved 数、prompt_ready 数。
5. 编辑接口必须只影响 storyboard 表，不改写 script、production、Review notes 或项目级 image assets。

验收标准：

- 可以新增 shot，保存后刷新仍存在。
- 可以删除 shot，保存后顺序连续。
- 可以调整顺序，后端读取顺序与保存顺序一致。
- 可以修改审阅状态为 `pending`、`needs_changes`、`approved`。
- 导出包反映编辑后的 shots。

测试要求：

- Web API 测试覆盖新增、删除、排序、状态修改。
- Storage 测试覆盖删除 shot 后 image link 清理但 image asset 保留。
- 回归测试现有 script/production edit 仍通过。

是否允许/要求重构：允许。编辑保存逻辑应集中在 storage/storyboard helper，不要在 Web handler 内拼 SQL。

风险和注意事项：

- 不要用前端数组下标作为持久化 id；数据库 id 和 sequence_index 要分开。
- 不要让空 image prompt 被标记为 prompt_ready。

## Task 4: 实现项目内角色、场景、道具资产编辑与 shot 关系

目标：把 storyboard 中的角色、场景、道具作为项目内资产展示和保存，并维护它们与 shot 的关系。

产品需求来源：

- 用户可看到项目内角色、场景和道具资产。
- 用户可看到资产与 shot 的对应关系。
- 用户可为资产补充描述、提示词或一致性备注。
- 导出包包含资产摘要和 shot 关联。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/storyboard_schema.py`
- `tests/test_storyboard.py`
- `tests/test_web.py`

实现步骤：

1. 新增资产请求模型：`asset_type`、`name`、`description`、`reference_prompt`、`consistency_notes`。
2. 新增 `PATCH /api/projects/{project_id}/storyboard/assets` 保存项目内资产完整列表。
3. 新增 shot-asset 关系保存逻辑，支持角色、场景、道具在多个 shot 中出现。
4. 资产名称变更后，关系仍通过 asset id 保持，不依赖名称匹配。
5. 查询 API 返回每个 asset 的 `shot_ids` 或 `shot_sequence_indexes`，供前端展示出现位置。
6. 导出包包含 assets 和 shot relations。

验收标准：

- 用户保存资产描述、参考提示词、一致性备注后刷新仍可查看。
- 一个角色/场景/道具可关联多个 shot。
- 删除资产会删除关系，但不删除 shots。
- 导出包包含资产摘要与关联 shot。

测试要求：

- Storage 测试覆盖资产 CRUD 和关系维护。
- Web API 测试覆盖资产编辑和关系展示。
- Schema 测试覆盖非法 asset_type。

是否允许/要求重构：允许。可新增资产 helper，避免 `storage.py` 方法过长；如果拆分，保持现有导入路径清晰。

风险和注意事项：

- 本轮只做项目内资产，不做跨项目资产库。
- 不要把资产关系仅以字符串写在 shot 字段中；必须有关系表。

## Task 5: 实现 Shot 与图像资产关联入口

目标：把已有或后续生成的项目图像资产关联到具体 shot，为下一轮批量分镜图生成准备数据位置和产品入口。

产品需求来源：

- 用户可识别哪些 shot 已准备好生成分镜图。
- 已有或后续生成的项目图像资产可以在产品语义上关联到 shot。
- 本轮产物能支撑继续拆解批量分镜图生成能力。

影响文件/模块：

- `src/vidiom/storage.py`
- `src/vidiom/web.py`
- `src/vidiom/static/app.js` 或拆分后的 storyboard 前端模块
- `tests/test_web.py`

实现步骤：

1. 新增 link/unlink API：`POST` 和 `DELETE /api/projects/{project_id}/storyboard/shots/{shot_id}/image-assets/{asset_id}`。
2. 校验 shot 和 image asset 必须属于同一 project。
3. Link 类型至少支持 `reference` 和 `storyboard_frame`。
4. 查询 storyboard 时返回每个 shot 的关联 image assets 摘要。
5. 前端展示 shot 的已关联图片数量、最新关联图像状态、项目图像可绑定入口。
6. 不在本任务中实现批量调用 `gpt-image-2`；只保留入口状态和数据关系。

验收标准：

- 现有项目图像资产可绑定到指定 shot。
- 绑定后刷新仍显示关联。
- 解除绑定后 image asset 仍保留在项目图像列表。
- 不同项目之间的 shot/image 不能互相绑定。

测试要求：

- API 测试覆盖同项目绑定、解除绑定、跨项目拒绝。
- 导出包测试覆盖 shot-image 关联摘要。

是否允许/要求重构：允许。可以为 image asset link 增加 storage helper。

风险和注意事项：

- 不要把图片复制到 shot 记录中；shot 只通过关联表引用 image asset。
- 不要改变现有项目级图像生成 API 的行为。

## Task 6: Studio 前端接入 Storyboard 工作流

目标：在 Studio 中提供可实际使用的故事板视图，支持生成、查看、编辑 shot，管理资产，并显示 shot-image 关联。

产品需求来源：

- 用户可从脚本/Review 流程进入故事板。
- Shot 列表便于快速扫描：顺序、状态、画面、角色、场景和 prompt 准备度一眼可见。
- 单个 shot 编辑轻量，适合反复微调。
- 资产关系帮助发现角色名、场景名、道具名不一致。
- 生成中、成功、失败和人工编辑状态必须清晰可见。

影响文件/模块：

- `src/vidiom/static/index.html`
- `src/vidiom/static/app.js`，或新增 `src/vidiom/static/storyboard.js` 并改为 module script
- `src/vidiom/static/styles.css`
- `tests/test_web.py`

实现步骤：

1. 新增 Review tab：`故事板`，并把 `REVIEW_TABS` 扩展为包含 `storyboard`。
2. 增加前端状态：`storyboard`、`storyboardLoading`、`storyboardGenerating`、`storyboardEditing`。
3. 进入故事板 tab 时调用 `GET /api/projects/{id}/storyboard`。
4. completed 项目显示“生成故事板”入口；生成中显示状态；失败显示错误；成功显示 shot 列表和资产区。
5. Shot 列表显示序号、review status、visual description、characters、scene、props、duration、prompt_ready 和 image link 状态。
6. 提供编辑模式，支持新增、删除、上移/下移、字段编辑、审阅状态修改和保存。
7. 资产区展示角色、场景、道具，支持编辑描述、参考提示词和一致性备注。
8. 图像关联区显示项目 image assets，并允许把现有 image asset 绑定到 selected shot。
9. Delivery/导出清单显示 storyboard shot 数、approved 数、prompt_ready 数、资产数和关联图像数。
10. README 迭代记录补充本轮功能、涉及文件和验证命令。

验收标准：

- 完成项目可从 Studio 进入故事板视图并触发生成。
- 生成成功后可查看多个 shot。
- 用户可编辑、新增、删除、排序 shot 并保存。
- 用户可编辑项目内资产。
- 用户可看到 shot 与 image assets 的关联位置。
- 刷新页面后 storyboard 状态和编辑结果保持。

测试要求：

- 静态前端 smoke 测试检查 Storyboard tab、生成入口、shot editor、asset editor、image link UI 关键函数/标记存在。
- Web API 测试覆盖前端依赖响应结构。
- 运行 `.venv/bin/python -m pytest`。

是否允许/要求重构：要求对 storyboard 前端逻辑形成独立边界。若继续单文件实现，必须集中命名并与 script/production editor 分离；如果拆模块，需要保持无构建步骤即可运行。

风险和注意事项：

- 不要把故事板做成脚本文本简单拆段。
- 不要在生成中或失败时显示空白成功态。
- 不要让 storyboards UI 破坏现有项目创建、运行、暂停、Review、图像和导出操作。

## Task 7: 回归、真实配置验证和文档更新

目标：确保 storyboard 能力不破坏现有真实模型运行、项目图像生成和导出闭环，并把迭代记录写清楚。

产品需求来源：

- 现有真实语言模型运行能力保持可用。
- 现有 `gpt-image-2` 项目图像生成能力保持可用。
- 现有项目创建、运行、暂停、修订、Review 编辑、导出和测试能力不应退化。

影响文件/模块：

- `README.md`
- `tests/`
- `docs/development-blockers.md` 如出现真实阻塞再更新

实现步骤：

1. 运行 `.venv/bin/python -m ruff check .`。
2. 运行 `.venv/bin/python -m pytest`。
3. 使用 fake clients 的自动化测试覆盖 provider 行为，避免测试消耗真实模型额度。
4. 如本机 `.env` 可用，手动 smoke：创建项目、运行 agent、生成 storyboard、编辑一个 shot、绑定一张项目图像、导出 JSON 包。
5. README 迭代记录写明需求来源、开发内容、用户价值、涉及文件、验证命令和仍待处理事项。
6. 若真实 provider 不可用，只记录具体缺失环境变量或 provider 错误；不得写成成功。

验收标准：

- 自动化测试通过。
- README 包含 storyboard 迭代记录。
- 导出的 JSON 包包含脚本、拍摄包、Review notes、image assets、storyboard、shots、assets 和 shot-image 关联摘要。

测试要求：

- 完整执行 ruff 和 pytest。
- 至少新增 storyboard 相关单元/API 测试。

是否允许/要求重构：不要求新增重构；只允许为测试稳定性做小范围整理。

风险和注意事项：

- 不要提交 `.env` 或输出密钥。
- 不要把真实 smoke 失败写成通过。
- 不要把批量分镜图生成、视频生成、音频、导演台或自由无限画布作为本轮已完成能力。
