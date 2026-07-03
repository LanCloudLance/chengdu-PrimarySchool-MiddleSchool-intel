# 成都学区招生情报系统（chengdu-edu-intel）

> **项目代号**：chengdu-edu-intel MVP  
> **分支**：`feat/chengdu-edu-intel-mvp`  
> **样板区**：武侯区（`wuhou`）— W1–W4 已验收；锦江首遍复制完成  
> **框架数据年**：2025（2026 yjrx 官方源刻意后置至招生季）  
> **最后更新**：2026-06-05

面向成都 7 个核心区的学区招生情报平台：采集、解析、版本化划片与对口数据，经 **REST API + HTMX 门户** 供家长查询。数据源以本地宝转载与区教育局公告为主，**非** yjrx 官方终稿。

---

## 新 Agent 接手：先看这里

| 优先级 | 文档 / 入口 | 用途 |
|--------|-------------|------|
| 1 | 本文 `README.md` | 全貌、启动、验收、下一步 |
| 2 | [`docs/PROJECT_PROGRESS.md`](docs/PROJECT_PROGRESS.md) | 阶段交付清单 + 迭代更新记录 |
| 3 | [`docs/WUHOU_ROADMAP.md`](docs/WUHOU_ROADMAP.md) | 武侯 W1–W4 节奏与复制顺序 |
| 4 | [`.cursor/skills/chengdu-district-intel/SKILL.md`](.cursor/skills/chengdu-district-intel/SKILL.md) | 分区管线操作步骤（复制到其他区） |
| 5 | [`.cursor/rules/chengdu-edu-verify-on-complete.mdc`](.cursor/rules/chengdu-edu-verify-on-complete.mdc) | **每项任务完成必跑验收** |

**接手后第一件事**（无需 Docker 也可跑）：

```bash
cd <项目根>
uv sync --group dev --group ocr   # 首次；OCR 可选但武侯建议装
.venv/bin/python scripts/verify_wuhou_all.py
```

期望输出：`ALL PASS: W1 + W2 + W3 + W4 + pytest`（当前 **37 passed**）。

---

## 当前状态总览

### 路线图进度（武侯样板）

| 阶段 | 主题 | 状态 | 验收脚本 |
|------|------|------|----------|
| **W1** | 划片闭环（pending / OCR / overrides） | ✅ | `verify_wuhou_mapping.py` |
| **W2** | 对口升学（PNG OCR + 白名单推断） | ✅ | `verify_wuhou_promotion.py` |
| **W3** | 门户可读（划片搜索 / 徽章 / 免责声明） | ✅ | `verify_wuhou_portal.py` |
| **W4** | 运营化（镜像 intel / 登记点 / 复制锦江） | ✅ | `verify_wuhou_w4.py` |
| **P0** | 2026 yjrx 官方划片 + 登记点 | ⏳ 2026-04 / 06 | 单独迭代 |

### 最新验收指标（dry-run，2026-06-05）

| 指标 | 值 |
|------|-----|
| 划片 mapped | 56 |
| unmatched 校名 | **0** |
| pending 公办小学 | **0** |
| 对口覆盖（公办小学） | **85.2%**（46/54） |
| promotion_links（scraped） | 54 |
| pytest | **37 passed** |
| mirror intel manifest | **73** |
| 武侯登记点 | **54** 公办小学 |
| 锦江划片（首遍） | **25** scopes / **28** 校 |

> **注意**：部分指标基于 `mapping_scraped.json` 与配置 dry-run；**DB 全量 import** 需 `docker compose up -d` 后补跑 `--db` 验收。

### 基础设施阶段（A–E）

| 阶段 | 内容 | 状态 |
|------|------|------|
| A | Docker、7 区 seed、ORM、Alembic、pytest | ✅ |
| B | 学校 inventory（武侯 96 校）、aliases、镜像页 | ✅ |
| C | 区级 gov_policy、P0 源 seed | 🔶 校级 enrollment 未全量验收 |
| D | 划片解析、intel、OCR、import、overrides | ✅（武侯） |
| E | 对口 OCR、推断白名单、import | ✅ dry-run；DB import 待 Docker |
| 门户 | API + HTMX、`scope_q`、状态徽章 | ✅ W3 |

### 其他 6 区

仅 `districts` seed + 部分 URL；**未**按武侯 2025 框架验收。复制顺序见 `WUHOU_ROADMAP.md`：jinjiang → qingyang → chenghua → jinniu → gaoxin → tianfu。

---

## 技术架构

```
configs/          # 学校清单、源 URL、aliases、overrides、scraped 缓存
scripts/          # 导入、同步、抓取、验收管线
packages/
  core/           # 枚举、校名匹配、搜索、hash/diff
  storage/        # ORM、Alembic、repository、intel_repository
  parsers/        # 划片/对口解析、mapping_ocr、promotion_ocr
  collectors/     # HTTP 抓取
  scheduler/      # 定时任务
  api/            # FastAPI + Jinja2/HTMX 门户
```

**运行栈**：Python 3.12+ · uv workspace · PostgreSQL 16 · FastAPI · SQLAlchemy async · Alembic · pytest

**服务端口**（`docker compose up`）：

| 服务 | 端口 |
|------|------|
| API / 门户 | http://localhost:8000 |
| PostgreSQL | localhost:5432（user/pass/db: `edu` / `edu` / `chengdu_edu`） |
| OpenAPI | http://localhost:8000/docs |

---

## 快速启动

### 1. 依赖与环境

```bash
cp .env.example .env          # 按需修改
uv sync --group dev --group ocr
```

### 2. 数据库与迁移

```bash
docker compose up -d db
.venv/bin/alembic -c packages/storage/alembic.ini upgrade head
.venv/bin/python scripts/seed_districts.py          # 若 districts 为空
.venv/bin/python scripts/bootstrap_core_districts.py  # 按需
```

### 3. 武侯数据管线（推荐顺序）

```bash
# 学校主数据
.venv/bin/python scripts/import_schools.py

# 划片情报同步（PNG 建议 --ocr）
.venv/bin/python scripts/sync_intel_library.py --district wuhou --ocr

# 划片入库
.venv/bin/python scripts/import_district_mapping_policies.py --district wuhou

# 对口升学（仅 promotion，不覆盖已有划片缓存）
.venv/bin/python scripts/scrape_district_mapping.py --district wuhou --promotion-only
.venv/bin/python scripts/import_school_promotion_targets.py --district wuhou

# 可选：区级招生政策、政府源
.venv/bin/python scripts/import_district_promotion_policies.py --district wuhou
```

### 4. 启动 API

```bash
docker compose up -d          # 或仅本地：uvicorn chengdu_edu_api.main:app --reload
# 门户：http://localhost:8000
# 划片街道搜索示例：/?scope_q=玉林东路&district=wuhou
```

### 5. 验收（任务完成必跑）

```bash
.venv/bin/python scripts/verify_wuhou_all.py
# Docker + 已 import 后：
.venv/bin/python scripts/verify_wuhou_all.py --db
```

---

## 武侯区数据与配置

### Inventory

- **96 校**（`configs/districts/wuhou/schools.yaml`）
- 别名：`school_aliases.yaml`（划片/公告异名 → 标准校名）
- 人工划片：`mapping_overrides.yaml`（10 条：更名、停招、一校两区等）
- pending 台账：`mapping_pending.yaml`（**10/10 done**）

### 划片源（`configs/district_mapping_sources.yaml`）

| URL 摘要 | kind | data_year | 角色 |
|----------|------|-----------|------|
| `182983_8` 本地宝 HTML 表 | school_scope | 2024 | reference 基底 |
| `198872_7` PNG 长图 | image_list | 2025 | OCR |
| `197052` 调整公告 | adjustment | 2025 | verified |

合并优先级：`override > adjustment > html > ocr`（`merge_scope_dicts`）。

### 对口源

| URL 摘要 | kind | 说明 |
|----------|------|------|
| `199288` | promotion_table | 2025 升学 PNG（OCR） |
| `185963` | promotion_table | 2024 reference |

品牌推断白名单：`promotion_inference.yaml`（棕北、玉林、龙江路等；禁止「武侯」等区名 token）。

### 缓存文件

- `configs/districts/wuhou/mapping_scraped.json` — 划片 scopes + `promotion_links`（离线 import 可读）

### mapping_status 含义（门户徽章）

| 值 | 含义 |
|----|------|
| `verified` | 2025 调整公告等较新核实源 |
| `reference` | 2024 HTML 表 / 转载参考 |
| `pending_official` | 待当年官方公布（武侯已清零） |

政策字段：`enrollment_scope`、`source_page`、`reference_year`、`framework_year`、`mapping_status`。

---

## API 与门户要点（W3）

| 能力 | 入口 |
|------|------|
| 校名/地址搜索 | `GET /api/schools?q=...` |
| **划片/街道搜索** | `GET /api/schools?scope_q=洗面桥街` |
| 学校详情 | `GET /api/schools/{id}` |
| 门户首页 | `GET /`（双搜索框：校名 + 划片街道） |
| 学校详情页 | `GET /schools/{id}`（划片卡片、状态徽章、来源链） |

实现位置：

- `packages/core/.../search_query.py` — 模糊搜索词展开
- `packages/api/.../mapping_display.py` — 徽章、免责声明、来源链
- `packages/api/.../routes/schools.py`、`pages.py`

页脚免责声明：信息仅供参考，以教育局 / yjrx 平台为准。

---

## 验收脚本说明

| 脚本 | 阶段 | 通过标准（摘要） |
|------|------|------------------|
| `verify_wuhou_mapping.py` | W1 | unmatched=0；pending≤3；pending yaml done |
| `verify_wuhou_promotion.py` | W2 | 公办小学对口 ≥60%；scraped links >0 |
| `verify_wuhou_portal.py` | W3 | scope_q API；模板含徽章/来源/免责 |
| `verify_wuhou_all.py` | 全部 | 上述 + `pytest -q` |

**项目规则**：每次迭代结束必须跑 `verify_wuhou_all.py`，再更新 `docs/PROJECT_PROGRESS.md` 第 7 节。

---

## 已知缺口与下一步（给新 Agent）

### 立即可做（W4 之后）

1. ~~**DB 补验**~~ ✅（`verify_wuhou_all.py --db` 全 PASS；mirror_page intel 73）
2. **锦江深化**：aliases / pending 清零 / promotion OCR
3. **复制青羊**：按 SKILL 段 1–4 走第二区

### 刻意后置（P0）

| 时间 | 项 |
|------|-----|
| 2026-04 | 登记点地址官方源 |
| 2026-06-15 前后 | yjrx 正式划片，切换 `data_year` 与 gov 源 |

### 技术债 / 质量

- OCR 对分校、跨行单元格仍有噪声；约部分校依赖 overrides
- 对口未覆盖 8 校：停招/更名/同片区（太平、洗面桥等），可加 `promotion_overrides.yaml`
- 抓取偶发 SSL / 本地宝 captcha：用 `mapping_scraped.json` 缓存或 mobile URL

---

## 目录索引

```
.
├── README.md                 # 本文（项目报告 + 接手指南）
├── docker-compose.yml
├── pyproject.toml            # uv workspace
├── configs/
│   ├── district_mapping_sources.yaml
│   ├── schools.yaml
│   └── districts/wuhou/      # 样板区配置与缓存
├── docs/
│   ├── PROJECT_PROGRESS.md   # 详细进度与更新日志
│   ├── WUHOU_ROADMAP.md
│   └── superpowers/          # 早期设计 spec/plan
├── packages/                 # 见「技术架构」
├── scripts/                  # 管线与 verify_*
└── .cursor/
    ├── rules/                # 验收规则
    └── skills/               # 分区交付 SKILL
```

### 核心脚本

| 脚本 | 用途 |
|------|------|
| `import_schools.py` | 学校主数据入库 |
| `sync_intel_library.py` | 配置源 → intel_entries + scraped 缓存 |
| `import_district_mapping_policies.py` | 划片 → enrollment_policies |
| `scrape_district_mapping.py` | 抓取划片/对口（`--promotion-only`） |
| `import_school_promotion_targets.py` | 对口 → promotion_policies |
| `verify_wuhou_all.py` | **统一验收** |

### 核心解析模块

| 模块 | 用途 |
|------|------|
| `mapping_parser.py` | HTML 表、调整公告、对口文本、merge |
| `mapping_ocr.py` | 划片 PNG 三列 OCR |
| `promotion_ocr.py` | 升学 PNG 五列 OCR |

---

## 设计文档（历史）

- [`docs/superpowers/specs/2026-06-05-chengdu-edu-intel-design.md`](docs/superpowers/specs/2026-06-05-chengdu-edu-intel-design.md) — 设计规格
- [`docs/superpowers/plans/2026-06-05-chengdu-edu-intel.md`](docs/superpowers/plans/2026-06-05-chengdu-edu-intel.md) — 实现计划（部分阶段已完成）

以 `PROJECT_PROGRESS.md` 与 `WUHOU_ROADMAP.md` 为**现行真相来源**；设计文档若有冲突，以进度文档为准。

---

## 许可与免责

本项目整理的教育情报仅供研究与家长参考，**不构成入学建议**。划片范围、对口初中以武侯区教育局当年公布文件及成都市义务教育招生入学服务平台（yjrx）为准。
