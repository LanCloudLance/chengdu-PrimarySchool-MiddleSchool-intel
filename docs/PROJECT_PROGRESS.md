# 成都学区招生情报系统 — 项目进度总览

> **文档用途**：记录已交付能力、当前数据状态、管线入口与已知缺口。  
> **维护方式**：每次迭代完成后，在文末「更新记录」追加一节（使用固定模板）。  
> **项目总览 / 新 Agent 接手**：根目录 [`README.md`](../README.md)  
> **关联文档**：`docs/WUHOU_ROADMAP.md`（武侯推进节奏）、`.cursor/skills/chengdu-district-intel/SKILL.md`（复制到其他区的操作技能）

| 字段 | 值 |
|------|-----|
| 项目代号 | chengdu-edu-intel MVP |
| 工作分支 | `feat/chengdu-edu-intel-mvp` |
| 框架数据年 | **2025**（2026 yjrx 官方源刻意后置） |
| 样板区 | **武侯区（wuhou）** |
| 最后更新 | 2026-06-11（七区划片首遍 + 全量验收） |

---

## 1. 目标与边界

**目标**：采集、解析、版本化成都核心区的招生政策与划片情报，经 API / 门户可查。

**当前边界（MVP）**：
- 7 个核心区分 district seed 已完成；**仅武侯区**划片情报达到可用框架深度
- 数据源以本地宝转载 + 教育局公告为主；**非** yjrx 官方终稿
- P0（2026-06-15 yjrx 正式划片）**未接入**，待招生季再开

---

## 2. 阶段交付清单（A → E + 基础设施）

### Phase A — 基础脚手架与数据模型 ✅

| 项 | 状态 | 说明 |
|----|------|------|
| Docker Compose（PostgreSQL + API） | ✅ | `docker compose up`，API `:8000`，DB `:5432` |
| 7 区 `districts` seed | ✅ | jinjiang / qingyang / wuhou / chenghua / jinniu / gaoxin / tianfu |
| 领域枚举与 hashing / diff | ✅ | `packages/core` |
| ORM + Alembic 迁移 | ✅ | `packages/storage/alembic` |
| pytest 基线 | ✅ | 当前 **39 passed** |

### Phase B — 学校主数据（Inventory）✅（武侯深化中）

| 项 | 状态 | 说明 |
|----|------|------|
| 全局 + 分区 `schools.yaml` | ✅ | `configs/schools.yaml` + `configs/districts/{code}/schools.yaml` |
| `import_schools.py` | ✅ | 支持 `former_names` 安全更名 |
| 武侯 93→**96** 校 inventory | ✅ | 补弟维、西川悦湖、特教；行知→龙江路悦湖更名 |
| 校名别名 | ✅ | `configs/districts/wuhou/school_aliases.yaml` |
| 武侯 enrichment / checklist | ✅ | `enrichment.yaml`、`CHECKLIST.md` |
| 镜像页抓取 | ✅ | `scraped_mirrors.json`、alternate_urls |

### Phase C — 招生政策与政府文 ✅（部分）

| 项 | 状态 | 说明 |
|----|------|------|
| P0 政府源 seed | ✅ | `seed_p0_sources.py` |
| 区级 gov_policy 入库 | ✅ | 武侯等区有 `GOV_POLICY` |
| 校级 enrollment 政策 | 🔶 | 脚本存在，武侯覆盖未全量验收 |

### Phase D — 划片范围（district_mapping）✅（武侯 2025 框架）

| 项 | 状态 | 说明 |
|----|------|------|
| HTML 一览表解析 | ✅ | `parse_bendibao_mapping_tables`（含「分校」后缀） |
| 调整公告解析 | ✅ | `parse_mapping_adjustment_sections`（197052 类） |
| 分区源配置 | ✅ | `configs/district_mapping_sources.yaml`，`data_year: 2025` |
| 情报库 `intel_entries` | ✅ | migration `b2c3d4e5f6a7` |
| `sync_intel_library.py` | ✅ | hash 去重；解析器升级可刷新 structured_fields |
| `import_district_mapping_policies.py` | ✅ | 优先 intel；reference/verified 分状态；pending 占位 |
| PNG OCR 试点 | ✅ | `mapping_ocr.py` + `--ocr` + `ocr_mapping_images.py` |
| 多源 merge | ✅ | `merge_scope_dicts`（新年份/非 reference 优先） |

**武侯划片源（2025 框架）**：

| 源 | kind | data_year | 角色 |
|----|------|-----------|------|
| `182983_8.shtm` | school_scope | 2024 | HTML 表，reference 基底 |
| `198872_7.shtm` | image_list | 2025 | PNG 长图，OCR 试点 |
| `197052.shtm` | adjustment | 2025 | 2025 调整公告，verified |

### Phase E — 升学对口（promotion）✅（武侯 2025 框架）

| 项 | 状态 | 说明 |
|----|------|------|
| 对口文本解析 | ✅ | `parse_promotion_links`、`infer_group_promotion_links` |
| 升学 PNG OCR | ✅ | `promotion_ocr.py`（片号/小学/初中/备注五列） |
| `import_school_promotion_targets.py` | ✅ | OCR + 白名单推断 + 九年一贯制 |
| 武侯 promotion_urls | ✅ | 2025 `199288` + 2024 `185963` reference |
| `promotion_inference.yaml` | ✅ | 品牌词白名单（棕北/玉林/龙江路等） |
| 武侯 dry-run 对口覆盖 | ✅ | **45/54 公办小学（83%）** |
| 武侯 DB 对口 FK | 🔶 | 待 Docker 启动后 `import_school_promotion_targets` |

### 门户与 API ✅（W3 武侯样板）

| 项 | 状态 | 说明 |
|----|------|------|
| FastAPI schools 路由 | ✅ | 基础查询 + `scope_q` 划片搜索 |
| 校名/地址模糊搜索 | ✅ | `search_query.py` |
| 划片正文/街道搜索 | ✅ | `scope_q` → `district_mapping.enrollment_scope` |
| 政策状态徽章 UI | ✅ | reference / verified / 待官方 |
| 来源链 + 免责声明 | ✅ | `mapping_display.py` + 页脚 |
| HTMX Web 完整度 | 🔶 | 搜索/详情可用；W4 运营化继续 |

---

## 3. 武侯区当前数据快照（2026-06-05）

```
inventory schools (wuhou)       : 96
district_mapping (dry-run)      : 56 mapped, unmatched 0, pending 0
promotion_links (scraped)       : 54
promotion 公办小学覆盖 (dry-run): 85.2% (46/54)
mapping_scraped merged scopes   : 48
pytest                          : 36 passed
verify_wuhou_all                : W1 + W2 + W3 PASS
```

> 项目接手总览见根目录 [`README.md`](../README.md)。

| mapping_status | 数量（W1.3 后预期） | 含义 |
|----------------|------|------|
| reference | ~52 | 2024 HTML 表 + overrides/alias 更名校 |
| verified | 4 | 2025 调整公告等 |
| pending_official | **0**（预期） | 53 公办小学 dry-run 全覆盖 |
| **unmatched 校名** | **0** | 划片文本均能映射 inventory |

**verified 示例校**：四川大学附属实验小学明雅学校、成都市龙江路小学、成都市龙江路小学悦湖学校、成都市武侯区西川悦湖学校（以 DB 为准）。

---

## 4. 关键文件与脚本索引

### 配置

| 路径 | 用途 |
|------|------|
| `configs/district_mapping_sources.yaml` | 各区划片/对口 URL、kind、data_year |
| `configs/districts/wuhou/schools.yaml` | 武侯 inventory |
| `configs/districts/wuhou/school_aliases.yaml` | 划片/公告校名 → 标准校名 |
| `configs/districts/wuhou/mapping_overrides.yaml` | 人工划片覆盖（更名/停招/一校两区） |
| `configs/districts/wuhou/mapping_pending.yaml` | W1 pending 台账（10/10 done） |
| `configs/districts/wuhou/promotion_inference.yaml` | W2 品牌推断白名单 |
| `configs/districts/wuhou/mapping_scraped.json` | sync 镜像缓存（含 `promotion_links`） |

### 管线（推荐顺序）

```bash
# 0. 环境
docker compose up -d
packages/storage/../../.venv/bin/alembic -c packages/storage/alembic.ini upgrade head

# 1. 学校主数据
.venv/bin/python scripts/import_schools.py

# 2. 情报同步（武侯建议带 OCR）
.venv/bin/python scripts/sync_intel_library.py --district wuhou --ocr

# 3. 划片入库
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou

# 3.5 对口升学（W2）
.venv/bin/python scripts/scrape_district_mapping.py --district wuhou --promotion-only
.venv/bin/python scripts/import_school_promotion_targets.py --district wuhou

# 4. 验收（任务完成必跑）
.venv/bin/python scripts/verify_wuhou_all.py
.venv/bin/python scripts/verify_wuhou_all.py --db   # 可选，需 Docker + import
```

### 代码包

| 包 | 核心模块 |
|----|----------|
| `parsers` | `mapping_parser.py`、`mapping_ocr.py` |
| `storage` | `intel_repository.py`、`repository.py` |
| `core` | `school_names.py`、`search_query.py`、`enums.py` |
| `api` | `routes/schools.py` |

---

## 5. 已知缺口与刻意后置

| 优先级 | 项 | 说明 |
|--------|-----|------|
| P0 | 2026 yjrx 官方划片 | 6 月 15 日前后接入 gov + 平台源 |
| P1 | ~~pending 补全~~ | **W1.4 完成**；dry-run 53/53；DB 待 Docker 重启后 `--db` 补验 |
| P1 | OCR 质量 | 分校/跨行单元格；约 17/46 校来自 OCR |
| P2 | ~~升学对口~~ | **W2 完成**；DB import 待 Docker |
| P3 | 其他 6 区复制 | 参照 SKILL 与武侯样板 |
| P4 | ~~划片全文搜索 / UI 状态~~ | **W3 完成** |

---

## 6. 其他区状态（一览）

| 区 | mapping_urls | 说明 |
|----|--------------|------|
| wuhou | 3 | 2025 框架完整 |
| gaoxin | 2 | 有 URL，未按 2025 框架验收 |
| jinjiang | 1 | 2025 HTML 划片首遍（25 scopes / 28 校） |
| qingyang / chenghua / jinniu / tianfu | 0 | 待复制 |

---

## 7. 更新记录

> **给维护者**：每次迭代在下方**追加**一节，不要改历史条目。复制「更新模板」填空即可。

---

### [2026-06-07] 2025 框架 + inventory 补全 + OCR 试点

**执行人 / 会话**：feat/chengdu-edu-intel-mvp 迭代

**本次目标**
- 以 2025 年数据完成武侯划片框架（P0/2026 yjrx 后置）
- 补 inventory 缺口校名
- PNG 一览表 OCR 试点

**交付**
- [x] `data_year: 2025` + 三源（2024 表 / 2025 图 / 2025 公告）
- [x] 表格解析支持「分校」；调整公告解析器
- [x] `intel_entries` + `sync_intel_library`（含 `--ocr`）
- [x] inventory +96 校；别名；`former_names` 更名
- [x] `mapping_ocr.py` + RapidOCR 试点
- [x] pytest 30 passed；unmatched 校名 0

**数据变化（武侯）**

| 指标 | 前 | 后 |
|------|----|----|
| schools | 93 | 96 |
| mapping reference | ~37 | 42 |
| mapping verified | 2 | 4 |
| mapping pending | ~21 | 10 |
| unmatched | 5 | 0 |

**未做 / 下一跳**
- [ ] 10 校 pending 逐校补划片
- [ ] promotion 系统导入
- [ ] OCR 列对齐第二轮

**验证命令**
```bash
.venv/bin/python scripts/sync_intel_library.py --district wuhou --ocr
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou
.venv/bin/python -m pytest -q
```

---

### [2026-06-07] W1.1 启动 — pending 清单与路线图确认

**执行人 / 会话**：用户确认 W1→W4 节奏；代理执行 W1.1

**本次目标**
- 确认执行逻辑（W1 划片闭环优先，P0 后置）
- 导出 10 校 pending 并标注数据源缺口

**交付**
- [x] `docs/PROJECT_PROGRESS.md` / `WUHOU_ROADMAP.md` / SKILL 已定稿
- [x] `configs/districts/wuhou/mapping_pending.yaml`（10 校逐校 next_action）
- [x] `configs/districts/wuhou/mapping_overrides.yaml`（脚手架）

**数据变化（武侯）**

| 指标 | 前 | 后 |
|------|----|----|
| pending | 10 | 10（清单已建档，未减） |

**发现**
- 10 校均不在 2024 HTML 一览表独立行中；非 parser 漏抓，属**新校/代招/更名校**
- 红专西路与弟维同址，优先核实 merge/alias
- 三河小学校可由太平寺西区「代招」条目衍生 override

**未做 / 下一跳（W1.2）**
- [ ] OCR bbox 列对齐，提高 2025 长图覆盖率
- [ ] `mapping_overrides.yaml` 接入 import
- [ ] 红专西路/三河等 quick win 先清 2–3 校 pending

**验证命令**
```bash
docker compose exec -T db psql -U edu -d chengdu_edu -c "
  SELECT COUNT(*) FROM enrollment_policies ep
  JOIN districts d ON d.id=ep.district_id
  WHERE d.code='wuhou' AND ep.fields->>'mapping_status'='pending_official';"
```

---

### [2026-06-07] W1.2 — OCR 列对齐 + overrides 接入 + quick win

**执行人 / 会话**：W1.2 迭代

**本次目标**
- OCR bbox 分列解析改进
- `mapping_overrides.yaml` 接入 import
- 红专西路 / 三河 / 弟维 quick win

**交付**
- [x] `parse_ocr_table_boxes` 三列分列 + 校名跨行拼接
- [x] `merge_scope_dicts` 优先级：override > adjustment > html > ocr
- [x] `sync_intel_library` 标记 `scope_source`
- [x] `import_district_mapping_policies` 读取 overrides + `copy_scope_from`
- [x] `mapping_overrides.yaml` 弟维校正、红专西路、三河
- [x] pytest **32 passed**（+2）

**数据变化（武侯，待 Docker 重启后 import 验证）**

| 指标 | 前 | 后（预期） |
|------|----|----|
| pending | 10 | **7** |
| reference | 42 | **45** |

**验证命令**（需 `docker compose up -d`）
```bash
.venv/bin/python scripts/sync_intel_library.py --district wuhou --ocr
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou
docker compose exec -T db psql -U edu -d chengdu_edu -c "
  SELECT fields->>'mapping_status', COUNT(*) FROM enrollment_policies ep
  JOIN districts d ON d.id=ep.district_id WHERE d.code='wuhou'
  AND ep.policy_type='district_mapping' AND ep.year=2025 GROUP BY 1;"
```

**未做 / 下一跳（W1.3）**
- [x] 余下 7 校 pending 搜 2025 源 / OCR 补行 → 见 W1.3 节
- [ ] 启动 Docker 后跑管线确认 pending≤3

---

### [2026-06-07] W1.3 — 10 校 pending 台账闭环

**执行人 / 会话**：W1.3 迭代

**本次目标**
- 查清 7 校「表内无独立行」根因（多为更名/停招/一校两区）
- alias + override 补全，清零 mapping_pending.yaml

**交付**
- [x] `school_aliases.yaml` +2：北二外北区→华兴、附小南区学校→附小南区
- [x] `mapping_overrides.yaml` +7：洗面桥、附小西区、太平小学、新城南区、金兴北路、百草园/新生路 copy
- [x] `mapping_pending.yaml`：10/10 done
- [x] 本地 dry-run：台账 10 校 + 公办小学 **53/53** 均有 scope
- [x] pytest **32 passed**

**根因摘要**

| 校名 | 处理 |
|------|------|
| 华兴 / 百草园 | 2024 表用北二外新校名 → alias |
| 新生路 / 百草园 | inventory 新旧并存 → 新校名直配表 + 旧校名 copy |
| 洗面桥 | 弟维片号1含洗面桥街 → copy 弟维 |
| 附小西区 | 同址附小分校片号8 → copy 分校 |
| 太平小学 | 2023 停招，明远书院承接 → override 片号20 |
| 新城分校南区 | 一校两区 → copy 新城分校片号36 |
| 金兴北路 | 2024 表无行 → 2022 调整公告 override |

**数据变化（武侯，待 Docker 重启后 import 验证）**

| 指标 | 前 | 后（预期） |
|------|----|----|
| pending（台账） | 7 open | **0** |
| pending_official（DB） | 10 | **0** |
| reference | 45 | **~52** |

**未做 / 下一跳（W1.4）**
- [x] `verify_wuhou_mapping.py` dry-run 验收 PASS
- [ ] Docker 启动后 sync + import + `--db` 补验（非阻塞 W1 闭环）

---

### [2026-06-05] W1.4 — 划片闭环验收

**执行人 / 会话**：W1.4 迭代

**本次目标**
- 按 `WUHOU_ROADMAP.md` W1.4 标准验收：unmatched=0、pending≤3、pytest 绿
- 固化验收脚本，回填进度文档

**交付**
- [x] `scripts/verify_wuhou_mapping.py`：dry-run 覆盖 + 可选 `--db` SQL
- [x] dry-run：**56 mapped**，unmatched **0**，pending_public_primary **[]**
- [x] `mapping_pending.yaml`：**10/10 done**
- [x] pytest **32 passed**
- [x] `WUHOU_ROADMAP.md` W1.4 标记完成

**数据变化（武侯）**

| 指标 | W1.3 后预期 | W1.4 验收（dry-run） |
|------|-------------|----------------------|
| mapped policies | 56 | 56 |
| unmatched | 0 | **0** |
| pending（公办小学） | 0 | **0** |
| pending 台账 | 10/10 done | **10/10 done** |
| pytest | 32 | **32 passed** |

**未做 / 下一跳（W2）**
- [ ] `promotion_urls` 配置 + `import_school_promotion_targets.py`
- [ ] Docker 可用时：`sync --ocr` → `import` → `verify_wuhou_mapping.py --db`

**验证命令**
```bash
.venv/bin/python scripts/verify_wuhou_mapping.py
.venv/bin/python -m pytest -q
# DB 补验（Docker 启动后）：
docker compose up -d
.venv/bin/python scripts/sync_intel_library.py --district wuhou --ocr
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou
.venv/bin/python scripts/verify_wuhou_mapping.py --db
```

---

### [2026-06-05] W2 — 对口升学闭环

**执行人 / 会话**：W2 迭代

**本次目标**
- 配置 promotion 源、OCR 解析升学 PNG、白名单推断、验收 >60% 公办小学对口覆盖

**交付**
- [x] `promotion_urls`：2025 `199288` + 2024 `185963`
- [x] `promotion_ocr.py`：升学对应区域五列 OCR + 续页识别
- [x] `promotion_inference.yaml` + 初中校名 `school_aliases.yaml` 扩展
- [x] `scrape_district_mapping.py --promotion-only` 合并 `promotion_links`
- [x] `import_school_promotion_targets.py`：白名单推断 + 九年一贯制
- [x] `verify_wuhou_promotion.py` dry-run **PASS**（83.3%）
- [x] pytest **34 passed**

**数据变化（武侯）**

| 指标 | 前 | 后 |
|------|----|----|
| promotion_links（scraped） | 0 | **54** |
| 公办小学对口覆盖（dry-run） | ~6%（推断 3 校） | **83.3%（45/54）** |
| 多校划片/摇号标注 | 0 | **45 校** |
| promotion 有 FK（DB） | 未验收 | 待 Docker import |

**未覆盖 9 校（预期）**：停招/更名/无独立片（太平、新生路、洗面桥、红专西路、三河、望江楼、读者、金兴北路等）— 可 W2.5 overrides 补

**未做 / 下一跳（W3）**
- [x] 见 W3 节

---

### [2026-06-05] W3 — 门户可读

**执行人 / 会话**：W3 迭代

**本次目标**
- 划片/街道搜索、mapping_status 徽章、来源链、免责声明

**交付**
- [x] `scope_q`：API `GET /api/schools` + 门户双搜索框
- [x] `mapping_display.py`：徽章、来源链、免责声明文案
- [x] 详情页划片卡片（状态徽章 + provenance + 正文）
- [x] 列表页划片状态徽章
- [x] `verify_wuhou_portal.py`；`verify_wuhou_all.py` 纳入 W3
- [x] pytest **36 passed**

**验证命令**
```bash
.venv/bin/python scripts/verify_wuhou_portal.py
.venv/bin/python scripts/verify_wuhou_all.py
```

**未做 / 下一跳（W4）**
- [x] 见 W4 节

---

### [2026-06-11] W4 — 运营化 + 锦江首遍复制

**执行人 / 会话**：feat/chengdu-edu-intel-mvp / W4 迭代

**本次目标**
- 镜像页入 intel（MIRROR_PAGE）
- 4 月 edu 登记点标记
- 锦江划片首遍复制（SKILL 段 1–4）

**交付**
- [x] `sync_mirror_intel.py`（`--from-inventory` 防 captcha）+ `mirror_intel_manifest.json` 73 条
- [x] `apply_registration_points.py`：武侯 54 公办小学 `registration_point`
- [x] `expand_inventory_from_mapping.py` + 锦江 `mapping_urls`（198845 HTML 两列表）
- [x] `parse_bendibao_mapping_tables` 支持锦江两列表格
- [x] `verify_wuhou_w4.py`；`verify_wuhou_all.py` 纳入 W4
- [x] pytest **37 passed**

**数据变化**

| 指标 | 前 | 后 |
|------|----|----|
| mirror intel manifest | 无 | **73** |
| 武侯 registration_point | 0（candidate 59） | **54** |
| 锦江 scopes | 0 | **25** |
| 锦江 inventory | 8 | **28** |
| pytest | 36 | **37** |

**未做 / 下一跳**
- [x] Docker 补验 → 见下节
- [ ] 锦江 promotion OCR / aliases / pending 深化
- [ ] 复制青羊

**验证命令**
```bash
.venv/bin/python scripts/apply_registration_points.py --district wuhou
.venv/bin/python scripts/sync_mirror_intel.py --district wuhou --from-inventory
.venv/bin/python scripts/scrape_district_mapping.py --district jinjiang
.venv/bin/python scripts/expand_inventory_from_mapping.py --district jinjiang
.venv/bin/python scripts/verify_wuhou_all.py
```

---

### [2026-06-11] DB 补验 — mirror intel 入库 + 全量 --db

**执行人 / 会话**：W4 下一跳 / DB 补验

**本次目标**
- Docker DB 启动后完成武侯/锦江 import 与 `verify_wuhou_all.py --db`

**交付**
- [x] `sync_mirror_intel.py --from-inventory` 可写入 DB（修复 manifest-only 早退）
- [x] `import_schools` 198 校；武侯 mapping 56 + 锦江 26；mirror_page intel **73**
- [x] `verify_wuhou_all.py --db`：**W1–W4 + pytest 全 PASS**

**DB 快照（武侯 mapping）**

| mapping_status | 数量 |
|----------------|------|
| reference | 52 |
| verified | 4 |
| pending | 0 |

**验证命令**
```bash
docker compose up -d db
.venv/bin/alembic -c packages/storage/alembic.ini upgrade head
.venv/bin/python scripts/import_schools.py
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou --district jinjiang
.venv/bin/python scripts/import_school_enrollment_policies.py --district wuhou
.venv/bin/python scripts/sync_mirror_intel.py --district wuhou --from-inventory
.venv/bin/python scripts/verify_wuhou_all.py --db
```

**未做 / 下一跳**
- [x] 复制青羊 → 见下节七区首遍
- [ ] 锦江 promotion OCR / aliases

---

### [2026-06-11] 七区划片首遍 — bootstrap + verify_all_districts

**执行人 / 会话**：feat/chengdu-edu-intel-mvp / 七区跑通 + 留痕交接

**本次目标**
- 配置青羊/成华/高新/天府 mapping 源；批量 scrape → expand → DB import
- `verify_all_districts.py` + 纳入 `verify_wuhou_all.py`；全量 `--db` 自我验证
- 交接文档 `docs/HANDOFF.md`

**交付**
- [x] 解析器：`parse_road_name_scopes`（青羊）、`parse_zone_school_list_scopes`（天府）
- [x] `configs/district_mapping_sources.yaml` 五区 URL + 金牛缺口说明
- [x] `scripts/bootstrap_all_core_districts.py` 一键管线
- [x] `scripts/verify_all_districts.py`（七区 filesystem + 可选 DB）
- [x] 修复：`verify_all_districts` 单 event loop DB；`verify_wuhou_w4` manifest 幂等验收
- [x] `docs/HANDOFF.md`
- [x] pytest **39 passed**；`verify_wuhou_all.py --db` **ALL PASS**

**数据变化（七区首遍）**

| 区 | inventory | scopes | DB mapping（非 pending） |
|----|-----------|--------|--------------------------|
| jinjiang | 28 | 25 | 25 |
| qingyang | 36 | 32 | 32 |
| wuhou | 96 | 48 | 56 |
| chenghua | 41 | 36 | 36 |
| jinniu | 7 | 0 | 0（待源） |
| gaoxin | 9 | 5 | 5 |
| tianfu | 41 | 38 | 38 |

**未做 / 下一跳**
- [ ] 金牛划片源（bendibao 198847 正文缺失）
- [ ] 高新区全区划片补全
- [ ] 锦江 promotion OCR / aliases
- [ ] `sync_intel_library --all-core` 补六区 intel mapping 行

**验证命令**
```bash
.venv/bin/python scripts/bootstrap_all_core_districts.py
.venv/bin/python scripts/verify_all_districts.py --db
.venv/bin/python scripts/verify_wuhou_all.py --db
```

**交接**：详见 [`docs/HANDOFF.md`](HANDOFF.md)

---

### [2026-06-12] 七区深度对齐 — verify_district_parity 验收

**执行人 / 会话**：feat/chengdu-edu-intel-mvp / 深度管线

**本次目标**
- 按武侯 W1–W4 能力对齐七区：划片 / intel / 登记点 / 入库 / 镜像全链路
- 新增 `verify_district_parity.py` 同级验收脚本
- OCR 分块 + 超时机制（防止大长图卡死）

**交付**
- [x] `scripts/bootstrap_district_parity.py`（深度管线入口，支持 `--district` 单区）
- [x] `scripts/verify_district_parity.py`（武侯同级验收：filesystem + DB）
- [x] `scripts/seed_inventory_from_global.py`（global schools seed 合并进分区 inventory）
- [x] OCR 分块（`_ocr_image_tiled`）+ 30s 超时（`_ocr_with_timeout`）
- [x] `sync_intel_library.py` 不再误清空已有 `mapping_scraped.json`
- [x] `scrape_district_mapping.py --ocr` 支持 image_list OCR
- [x] `verify_wuhou_mapping.py` dry_run 考虑 alias（pending 5→0）
- [x] 金牛/高新 OCR 仍超时，文档化缺口

**数据变化（七区深度对齐）**

| 区 | inventory | scopes | DB mapping（非 pending） | intel_mapping |
|----|-----------|--------|--------------------------|---------------|
| jinjiang | 28 | 25 | 25 | 1 |
| qingyang | 36 | 32 | 32 | 1 |
| wuhou | 101 | 47 | 56 | 3 |
| chenghua | 41 | 36 | 36 | 1 |
| jinniu | 7 | 0 | 0 | 0（OCR 超时） |
| gaoxin | 9 | 5 | 5 | 3 |
| tianfu | 41 | 38 | 38 | 1 |

**验收结论**
```bash
.venv/bin/python scripts/verify_district_parity.py --db
# 5/7 PASS; jinniu/gaoxin FAIL (OCR 不可用)
```

**未做 / 下一跳**
- [ ] 金牛/高新 OCR 手动补划片（或换非 image_list 源）
- [ ] 锦江 promotion OCR
- [ ] 全六区 mirror intel（需 `scraped_mirrors.json`）

**验证命令**
```bash
.venv/bin/python scripts/bootstrap_district_parity.py
.venv/bin/python scripts/verify_district_parity.py --db
```

---

### 更新模板（复制使用）

```markdown
### [YYYY-MM-DD] 标题（一句话）

**执行人 / 会话**：（分支名或负责人）

**本次目标**
- 

**交付**
- [ ] 

**数据变化（武侯）**

| 指标 | 前 | 后 |
|------|----|----|
| schools | | |
| mapping reference | | |
| mapping verified | | |
| mapping pending | | |
| unmatched | | |
| promotion 有 FK | | |

**未做 / 下一跳**
- [ ] 

**验证命令**
\`\`\`bash
# 粘贴实际跑过的命令
\`\`\`
```
