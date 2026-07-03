---
name: openprd-diagram-review
description: 在 freeze 前生成并评审 OpenPrd 架构图和产品流程图。
---

<!-- OPENPRD:GENERATED
adapter=codex
source=openprd-diagram-review
version=0.1.11
checksum=9a3699d3706f719a
-->

# OpenPrd Diagram Review

当需要架构、产品流程、用户旅程或可视化确认时，使用这份 skill。

- 用 `openprd diagram . --type architecture` 生成架构图。
- 用 `openprd diagram . --type product-flow` 生成产品流程图。
- 只有在用户审阅完产物后，才使用 `--mark confirmed`。

## 契约语言

- Diagram contract 面向用户。当 `locale` 为 `zh-CN` 时，所有可见文本都要写成简体中文。
- 面向用户的 review.html 或 diagram HTML 文案不要使用 `freeze` 这类内部流程词，改写为“需求定稿前”“进入实现前确认”等业务可理解表达。
- 这包括 `title`、`subtitle`、`components[].name`、`components[].subtitle`、`components[].details`、`flows[].label`、`summaryCards[].title`、`summaryCards[].items`、`sidePanels[].title`、`sidePanels[].items` 和 `reviewInstructions`。
- MotiClaw、Electron、TypeScript、CLI、API、JSON、NDJSON、dry-run、Host API、schema、`waiting_approval` 这类必要术语可以保留，但周围句子必须是简体中文。
- 不要在 zh-CN diagram contract 中保留完整英文句子；运行 `openprd diagram --input` 前先把英文偏重文本改成简体中文。

## 评审门禁

- 出图不等于确认。
- 确认必须来自用户或项目 owner 对结构的接受。
- 如果图示影响实现，同步更新 `docs/basic/app-flow.md`、`docs/basic/backend-structure.md` 或 `docs/basic/frontend-guidelines.md`。
