<!-- OPENPRD:GENERATED
adapter=project
source=command-catalog
version=0.1.11
checksum=843ce7b0a9f941c7
-->

# OpenPrd Command Catalog

这份清单只负责回答两件事：当前 CLI 有哪些稳定入口，以及什么情况下该用哪条命令。

## 状态与修复

- `openprd run . --context`：读取 hook-stable 建议上下文；它是建议，不是自动执行指令。续做历史任务或按用户描述找对应需求/任务时，可带 `--message <用户原话>` 先解析显式目标。
- `openprd run . --verify`：校验当前 run 门禁，并把 `taskReady` 与 `workspaceReady` 分开报告；如果只剩 `feature-coverage`，表示任务账本或覆盖证据待收口，不等于本次功能失败。
- `openprd doctor .`：检查生成引导、hooks、skills、standards 与验证健康度；`--tools codex` 还会检查 `codex --version`。
- `openprd doctor . --tools codex --fix`：在用户明确同意后运行 `npm install -g @openai/codex@latest`，并在安装后复查 Codex CLI。
- `openprd update .`：修复生成引导、skills、hooks 与 drift。
- `openprd next .`：查看下一步 harness 动作。

## 需求与评审

- `openprd clarify .`：生成需求入口自省，并把澄清压缩回对话内确认。
- `openprd capture . --field <path> --value <text|json>`：把用户确认写回状态。
- `openprd synthesize .`：生成可评审 PRD 与 `review.html`。
- `openprd review . --open`：打开当前 PRD review artifact。
- `openprd review . --mark confirmed --version <id> --digest <sha256> --work-unit <id>`：记录当前稳定评审稿；默认用于人类确认后的记录，若当前 lane 已进入 silent-record policy，也只能对精确匹配的稳定 artifact 记录。

## 设计与实现准备

- 界面、页面、视觉、样式、信息架构或前端体验任务进入实现前，先读取 `$openprd-frontend-design` 与 `.openprd/design/`；优先补齐 `.openprd/design/active/facts-sheet.md`、`asset-spec.md`、`image-preflight.md`、`direction-plan.md`、`selected-direction.md`，再开始编码。如果用户已经给了效果图、设计稿、参考截图或其他明确参考图，先把它当成主参考源：只有现有 starter、theme、layout 足够接近时才复用，不接近就允许偏离默认组合，以参考图为准。空白工作区优先从 `.openprd/design/templates/` 里挑最近模板；如果当前轮用户已经把页面主题、模块范围或“直接实现”的意图说清，优先运行 `openprd run . --context --message <用户原话>`。如果页面主题和模块范围已经明确，优先运行 `openprd design-starter . --starter <starter-id> --out index.html --brief "<页面主题>" --sections "<模块1|模块2|模块3>"` 起第一版真实页面。只有当前页确认不依赖外部产品事实、品牌素材或真实图片，才在 active design artifacts 写清无依赖并补 `--no-external-facts --no-brand-assets --no-real-images`；若题目更像旅游、导览、展览、博物馆、城市、自然观察或案例内容页，先不要带 `--no-real-images`，让 starter 先尝试补首批真实图片；若这类冷启动即使带 message 仍短暂返回 `clarify-user`，把它当成摘要级提醒，先用 3 到 5 行 mini-plan 收口，再继续。starter 落地后默认进入 `Patch Mode`：必须直接在生成的入口文件上补丁修改；即使结构要大改，也是在同一路径内覆盖，不做 delete-first，更不要删除 `index.html` 后另起新稿。如果确实要整页重写，先把完整新稿写到 sibling draft，例如 `index.next.html`，确认内容成形后再覆盖回 `index.html`，不要让正式入口出现空窗。starter 一落地后，只允许做一轮就地对焦：快速读一次生成的入口文件和必要的 active design artifacts；这轮对焦结束后，下一步就必须是真实写入口，不要再回头搜网页、翻 `docs/basic/` 或继续模板漫游。把最后一批必要的查事实、查图、读模板动作放在口头宣布之前做完；一旦已经说“开始覆盖入口文件”或“开始整页重写”，下一步必须出现真实写文件动作，而不是继续只读浏览、压图或停在口头承诺；必要时 hook 会把这类非写入动作挡回去。`Patch Mode` 完成不等于只补合同、只下载素材或只写计划；至少要把入口文件本体改完、主要占位清掉，并把已准备好的真实图片或参考约束真正落进页面。
- `openprd design-starter . --starter <content-home|product-launch|ops-dashboard> --out <index.html>`：把内置页面模板直接落成当前项目入口文件，避免空白工作区卡在“知道该用哪份模板，但还没真正开始写页面”的阶段。若再补 `--brief <页面主题> --sections <模块1|模块2|模块3>`，starter 会同步写实 active design artifacts，并把模板占位替成第一版真实内容。
- 没有明确参考方向时，不要直接落回同一种安全极简解；先在 `.openprd/design/active/direction-plan.md` 里给出 3 个异源方向，至少拉开 lens、theme、layout 或素材策略。
- 大界面改动视觉方案评审：先按用户目标、信息架构变化、视觉决策成本和验证风险判断是否需要方案评审；已有界面时用 Codex Computer Use 截取产品内当前功能截图，冷启动没有现有界面时用已确认 PRD、用户群体、第一版切片和视觉目标生成设计 brief；再用 `imagegen`（Codex 原生 Image 2）生成至少 3 个设计方向，并横向拼接为一张左上角标注 1/2/3 的大图作为候选效果图。Agent 主动确认是否符合预期、是否纳入后续效果图/实现截图对比、以及是否按此继续实现；只有确认后，才把选定方向、整张图或其中子图整理到 `.openprd/harness/visual-reviews/`，并进入大 UI 实现。
- `openprd change . --generate --change <id>`：把 PRD 转成 change。
- `openprd change . --validate --change <id>`：校验 change 结构。
- `openprd tasks . --change <id>`：查看当前 dependency-ready 任务。
- `openprd tasks . --change <id> --advance --verify --item <task-id>`：运行 verify 并推进单个任务。
- `openprd loop . --plan --change <id>`：为长程实现构建单任务列表。
- `openprd loop . --run --agent codex|claude --dry-run`：准备一个 fresh single-task session。
- `openprd loop . --run --agent codex --repair-agent`：Codex 真实运行前健康检查失败时，显式执行同一全局 npm 修复入口后再重试检查。

## Benchmark 与学习包

- `openprd benchmark add <url|repo|file> --notes <text>`：把外部最佳实践先写入 candidate，用于后续 approve/verify。
- `openprd benchmark observe <url|repo|file> --notes <text>`：记录本轮被采纳的外部信源，累计 evidence 和采纳次数；达到阈值后只提示 approve，不自动晋级。
- `openprd benchmark list .`：查看当前项目的 approved 与 candidate benchmark source。
- `openprd benchmark approve <benchmark-id>`：把 candidate 纳入项目级长期 registry。
- `openprd benchmark verify .`：检查重复来源、失效链接、缺场景和过宽触发词。
- `openprd learn . --topic <text> --open`：生成当前项目的学习包骨架和 HTML 阅读器；当用户目标是学习、复盘、教学、经验沉淀或长期阅读，并且产物需要章节、证据锚点、图文讲解、检索练习或阅读体验时，默认先走这条路径。
- `openprd learn . --content-json <file> --open`：让 Agent 写完 `learning-content.json` 后重新渲染最终图文阅读器。

## 发布与版本

- `openprd release . --set <0.1.23>`：设置当前项目版本，并启用 release-ledger。
- `openprd release . --notes "<新增 / 修复 / 优化 ...>"`：把本轮用户可感知变化累计到当前项目版本。
- `node scripts/openprd-github-release-notes.mjs . --version <0.1.23> --tag <0.1.23|v0.1.23> --out <file>`：从当前 release-ledger 渲染 GitHub Release 文案；缺少匹配版本或版本条目时直接失败。

## 视觉与质量

- `openprd visual-prepare . --reference <效果图> --grid <列>x<行>` / `--boxes <plan.json>`：把整板、网格图或多对象参考图整理成 reference-set，生成 crops、contact sheet 和 board 模板；先检查 contact sheet，再决定哪些对象进入后续实现与验收。
- `openprd visual-compare . --reference <效果图> --actual <实现截图>`：实现阶段已有确认参考图后，输出左右对比 JPG；如果参考图是一张多子图、网格或多对象组合，先运行 `visual-prepare` 整理 reference-set，再逐项对比。
- `openprd visual-compare . --before <修改前截图> --after <修改后截图>`：实现阶段没有参考图时先判断新建界面还是修改既有界面；新建界面回到实现前 3 方向方案评审，修改既有界面输出修改前后自检 JPG。
- `openprd visual-compare . --board <board.json>`：当要审局部细节、整板局部映射或多对象验收时输出“局部焦点证据板”；当并行跑了多个优化方向时输出“并行实验证据板”。
- `openprd dev-check . <file...>`：收工回顾 touched code files 的行数状态与下一步动作；需要关注的文件会给最终回复可直接使用的“后续建议”表格行。
- `openprd standards . --verify`：校验 `docs/basic/`、文件说明书、文件夹 README 等标准。
- `openprd quality . --verify`：生成 HTML 质量评估报告并检查 EVO 门禁。
- `openprd grow . --review`：审查执行中发现的规则/配置候选，再决定是否 apply。

## 深度扫描与历史项目

- `openprd discovery . --resume|--verify`：恢复或校验 discovery 状态。
- `openprd fleet <root> --dry-run`：批量审计历史项目。
- `openprd fleet <root> --sync-registry`：把当前 root 下已初始化的 `.openprd/` 工作区回填到全局 registry。
- `openprd fleet <root> --backfill-work-units`：补历史 PRD work unit 绑定。
- `openprd fleet <root> --update-openprd`：只刷新已有 `.openprd/` 的项目。

## 使用原则

- 规划、分析、评审、解释影响范围时，保持只读；不要因为命令存在就直接执行写入。
- 只有用户明确要求实现、继续任务、深度调研、对标复刻或提交时，才进入 `tasks --advance`、`loop --run`、commit、push 等执行动作。
- 高风险动作前先过 `openprd standards . --verify`、`openprd quality . --verify` 和 `openprd run . --verify`；`openprd doctor .` 主要用于集成漂移、生成引导 drift，或 commit/push/freeze/handoff 前的最终健康检查。
- OpenPrd 自身发布到 GitHub 的新版本，默认要同时具备匹配的项目版本、版本 tag 和 GitHub Release；只有 push/tag 没有 Release 不算发布闭环。
