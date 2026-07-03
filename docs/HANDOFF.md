# 七区划片首遍 — 交接留痕

> **日期**：2026-06-11  
> **分支**：`feat/chengdu-edu-intel-mvp`  
> **工作树**：`.worktrees/feat-chengdu-edu-intel-mvp`  
> **会话目标**：跑通 7 区划片/inventory/DB 首遍管线，完成自我验证并留痕交接。

---

## 1. 验收结论（2026-06-12 末次跑通）

```bash
cd .worktrees/feat-chengdu-edu-intel-mvp
docker compose up -d db
.venv/bin/alembic -c packages/storage/alembic.ini upgrade head

.venv/bin/python scripts/verify_district_parity.py --db   # 5/7 PASS (jinniu/gaoxin OCR 不可用)
.venv/bin/python scripts/verify_wuhou_all.py --db         # W1–W4 + 7区 + pytest ALL PASS
.venv/bin/pytest -q                                       # 39 passed
```

| 区 code | inventory | scraped scopes | DB mapping policies | 非 pending 划片 | intel_mapping | 状态 |
|---------|-----------|----------------|---------------------|-----------------|---------------|------|
| jinjiang | 28 | 25 | 26 | 25 | 1 | ✅ |
| qingyang | 36 | 32 | 34 | 32 | 1 | ✅ |
| wuhou | 101 | 47 | 61 | 56 | 3 | ✅ 样板深化 |
| chenghua | 41 | 36 | 38 | 36 | 1 | ✅ |
| jinniu | 7 | 0 | 0 | 0 | 0 | 🔶 OCR 超时 |
| gaoxin | 9 | 5 | 7 | 5 | 3 | 🔶 OCR 超时 |
| tianfu | 41 | 38 | 38 | 38 | 1 | ✅ |

**全局 DB**：`import_schools` 约 **304** 校；`district_mapping` 合计约 **204** 行（含 pending）。

---

## 2. 一键管线入口

### 全七区首遍（抓取 + 扩 inventory + 入库）

```bash
.venv/bin/python scripts/bootstrap_all_core_districts.py
```

顺序：5 区 scrape（锦江/青羊/成华/高新/天府）→ expand → `apply_registration_points --all-core` → import schools/enrollment/mapping（武侯含 promotion）→ 武侯 mirror intel。

**跳过 scrape**：`wuhou`（样板已验收）、`jinniu`（本地宝 198847 正文缺失）。

### 分区划片抓取

```bash
.venv/bin/python scripts/scrape_district_mapping.py --district <code>
.venv/bin/python scripts/expand_inventory_from_mapping.py --district <code>
.venv/bin/python scripts/import_district_mapping_policies.py --district <code>
```

### 验收

```bash
.venv/bin/python scripts/verify_all_districts.py [--db]
.venv/bin/python scripts/verify_wuhou_all.py [--db]   # 含七区 + W1–W4 + pytest
```

---

## 3. 各区数据源与解析器

配置：`configs/district_mapping_sources.yaml`

| 区 | URL / kind | 解析器 | 备注 |
|----|------------|--------|------|
| jinjiang | `198845` / `school_scope` | `parse_bendibao_mapping_tables`（两列表） | promotion PNG 待 OCR |
| qingyang | `198848` / `road_name_scope` | `parse_road_name_scopes` | 道路名称版式 |
| chenghua | `198846` / `school_scope` | 标准 HTML 表（桌面 cd.bendibao） | |
| gaoxin | `209029` school_scope + `209025` zone_list | 标准表 + 片区列表 | 仅中和片区首批 |
| tianfu | `196216` / `zone_school_list` | `parse_zone_school_list_scopes` | 学区+学校名单 |
| jinniu | **无** | — | `mapping_urls: []`，见缺口 |
| wuhou | 三源（182983/198872/197052） | 表 + OCR + 调整公告 | 见 `WUHOU_ROADMAP.md` |

新增解析器位置：`packages/parsers/src/chengdu_edu_parsers/mapping_parser.py`

---

## 4. 已知缺口与风险

1. **金牛区（jinniu）**：本地宝 `198847` 页面正文为空；当前仅 7 校 seed inventory，**无划片 scopes**，DB mapping 为 0。需另找教育局公告或 HTML 表源。
2. **高新区（gaoxin）**：仅中和 A/B 片区 5 条 scope；`198872_2` 为导航页非数据，未采用。
3. **intel_entries mapping 行**：非武侯区 `intel_mapping=0`；当前 import 走 `mapping_scraped.json` 缓存。可选：`sync_intel_library --all-core` 补 intel 库。
4. **本地宝 captcha**：批量并行抓 mirror 易触发；武侯 mirror 用 `sync_mirror_intel.py --from-inventory`。
5. **W4 manifest 验收**：重复同步时 `synced=0` 但 `skipped=73` 仍算通过（`verify_wuhou_w4.py` 已修）。

---

## 5. 本批次新增/修改文件

| 类型 | 路径 |
|------|------|
| 批量管线 | `scripts/bootstrap_all_core_districts.py` |
| 七区验收 | `scripts/verify_all_districts.py` |
| 解析器 | `mapping_parser.py`：`parse_road_name_scopes`、`parse_zone_school_list_scopes` |
| 配置 | `configs/district_mapping_sources.yaml`（5 区 URL + jinniu 说明） |
| 分区产物 | `configs/districts/{code}/mapping_scraped.json`、`schools.yaml` |
| 测试 | `test_parse_road_name_scopes`、`test_parse_zone_school_list_scopes` 等 |
| 验收修复 | `verify_wuhou_w4.py`（manifest effective 计数）、`verify_all_districts.py`（单 event loop DB） |

---

## 6. 建议下一跳（优先级）

1. **jinniu**：检索教育局 2025 划片 PDF/HTML，补 `mapping_urls` 后重跑 scrape + import。
2. **gaoxin**：补全区划片源（非仅中和）。
3. **jinjiang**：promotion PNG OCR + `school_aliases.yaml`。
4. **intel 库**：`sync_intel_library` 覆盖六区 mapping intel，与 import 双轨对齐。
5. **P0**：2026 yjrx 正式源（6/15 后）接入计划不变。

---

## 7. 关联文档

- 总进度：`docs/PROJECT_PROGRESS.md`（文末 2026-06-11 七区节）
- 武侯节奏：`docs/WUHOU_ROADMAP.md`
- 复制技能：`.cursor/skills/chengdu-district-intel/SKILL.md`
- 设计/计划：`docs/superpowers/specs/`、`docs/superpowers/plans/`

---

*本文件为会话留痕；后续迭代请在 `PROJECT_PROGRESS.md` 更新记录中追加，并视需要更新本节日期与验收表。*
