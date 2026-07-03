---
name: chengdu-district-intel
description: >-
  成都学区招生情报：按区采集划片/对口、同步 intel_entries、导入 enrollment_policies。
  武侯区为样板。Use when working on chengdu-edu-intel, district mapping, wuhou,
  sync_intel_library, import_district_mapping, school inventory, or OCR mapping PNGs.
---

# 成都学区情报 — 分区交付技能

## 何时使用

- 为某区**新增/更新划片**或**对口**情报
- 复制武侯样板到**其他核心七区**
- 跑管线、验收 DB、回填 `docs/PROJECT_PROGRESS.md`

## 前置条件

- 工作目录：项目根（含 `docker-compose.yml`）
- Docker DB 运行中；`.venv` 已创建
- OCR 可选：`uv sync --group ocr`（`rapidocr-onnxruntime` + `pillow`）

## 标准管线（三区段）

### 段 1 — Inventory

1. 编辑 `configs/districts/{code}/schools.yaml`
2. 如有公告/表格异名 → `configs/districts/{code}/school_aliases.yaml`
3. 更名用 `former_names`，**不要**删旧校名留 FK 孤儿
4. 导入：

```bash
.venv/bin/python scripts/import_schools.py
```

### 段 2 — 情报同步

1. 编辑 `configs/district_mapping_sources.yaml`：
   - 全局 `data_year`（当前 **2025**）
   - 每源：`url`、`kind`（`school_scope` | `image_list` | `adjustment` | `zone_list`）、`data_year`、`is_reference`
2. 同步：

```bash
.venv/bin/alembic -c packages/storage/alembic.ini upgrade head
.venv/bin/python scripts/sync_intel_library.py --district {code} --ocr   # 有 PNG 时加 --ocr
```

3. 检查 `configs/districts/{code}/mapping_scraped.json` 的 `scopes` 与 `errors`

**kind 说明**

| kind | 解析入口 |
|------|----------|
| school_scope | HTML 表 + 正文 |
| image_list | 提取 `data-echo`/`bigpicsrc`；`--ocr` 时走 `mapping_ocr.py` |
| adjustment | `parse_mapping_adjustment_sections` |
| zone_list | 仅 zone_blocks，不入 school_scopes |

### 段 2.5 — 人工覆盖（可选）

- `configs/districts/{code}/mapping_overrides.yaml`：`override` > `adjustment` > `html` > `ocr`
- 支持 `copy_scope_from` 从已解析校复制范围
- pending 台账：`configs/districts/wuhou/mapping_pending.yaml`

### 段 2.6 — 对口升学抓取（W2）

1. 在 `district_mapping_sources.yaml` 配置 `promotion_urls`（`kind: promotion_table`）
2. 抓取（PNG OCR，保留已有划片缓存）：

```bash
.venv/bin/python scripts/scrape_district_mapping.py --district {code} --promotion-only
```

3. 品牌推断白名单（武侯样板）：`configs/districts/{code}/promotion_inference.yaml`

### 段 3 — 政策入库

```bash
.venv/bin/python scripts/import_district_mapping_policies.py --district {code}
.venv/bin/python scripts/import_school_promotion_targets.py --district {code}
```

### 段 4 — W4 运营化（武侯样板 / 复制新区后）

```bash
# 登记点：4 月 edu 公告 URL → schools.yaml role=registration_point
.venv/bin/python scripts/apply_registration_points.py --district {code}

# 镜像页 → intel_entries（MIRROR_PAGE）；captcha 时用 inventory 缓存
.venv/bin/python scripts/sync_mirror_intel.py --district {code} --from-inventory
# Docker 可用时入库：
.venv/bin/python scripts/sync_mirror_intel.py --district {code} --from-inventory  # 去掉 --manifest-only

# 新区第一遍：划片抓取后补 inventory
.venv/bin/python scripts/scrape_district_mapping.py --district {code}
.venv/bin/python scripts/expand_inventory_from_mapping.py --district {code}
.venv/bin/python scripts/import_schools.py
```

## 验收清单（必须通过）

**每项任务完成后必跑**（见 `.cursor/rules/chengdu-edu-verify-on-complete.mdc`）：

```bash
.venv/bin/python scripts/verify_wuhou_all.py
# Docker 可用：.venv/bin/python scripts/verify_wuhou_all.py --db
```

分项脚本：

```bash
.venv/bin/python scripts/verify_wuhou_mapping.py      # W1
.venv/bin/python scripts/verify_wuhou_promotion.py    # W2
.venv/bin/python scripts/verify_wuhou_portal.py       # W3
.venv/bin/python scripts/verify_wuhou_w4.py           # W4
.venv/bin/python -m pytest -q

docker compose exec -T db psql -U edu -d chengdu_edu -c "
SELECT fields->>'mapping_status', COUNT(*)
FROM enrollment_policies ep
JOIN districts d ON d.id=ep.district_id
WHERE d.code='{code}' AND ep.policy_type='district_mapping' AND ep.year=2025
GROUP BY 1;"
```

| 指标 | 武侯样板目标 | 新区最低目标 |
|------|--------------|--------------|
| unmatched 校名 | 0 | 0 |
| pending（公办小学） | ≤ 3 | ≤ 30% 公办小学 |
| intel mapping 条数 | ≥ 2 | ≥ 1 |
| pytest | 全绿 | 全绿 |
| W3 门户 | `verify_wuhou_portal.py` PASS | scope_q + 免责声明（复制模板） |

## 武侯区特规

- 三源：2024 HTML 表（reference）+ 2025 PNG（OCR）+ 2025 调整公告（verified）
- OCR 过滤：跳过非「武侯」表头长图（见 `mapping_ocr.py`）
- 人工覆盖：`configs/districts/wuhou/mapping_overrides.yaml`（W1 已建，10 条）

## 常见坑

| 现象 | 处理 |
|------|------|
| 桌面 bendibao captcha | 用 `m.cd.bendibao.com`；fetch 已自动 fallback |
| 分校校名不匹配 | 表格解析需接受「分校」后缀；查 aliases |
| 更名 FK 冲突 | `former_names` + `upsert_school(former_names=...)` |
| OCR 混入其他区地图 | 表头不含「武侯」则 skip |
| hash 未变但解析器升级 | `intel_repository` 会比较 structured_fields 并刷新 |

## 完成后必做

在 `docs/PROJECT_PROGRESS.md` **第 7 节**追加更新记录（用文档内「更新模板」）。

**输出给用户的摘要格式**（会话结束时）：

```markdown
## 本次交付摘要 — {code} / {YYYY-MM-DD}

**目标**：（一句话）

**数据**
| 指标 | 前 → 后 |
|------|---------|
| schools | |
| reference / verified / pending | |
| unmatched | |

**命令**
- （列出实际执行的 2–4 条命令）

**下一跳**
- （1–3 条，对应 WUHOU_ROADMAP 的 W* 阶段）
```

## 参考文件

- 进度总览：`docs/PROJECT_PROGRESS.md`
- 武侯节奏：`docs/WUHOU_ROADMAP.md`
- 解析：`packages/parsers/src/chengdu_edu_parsers/mapping_parser.py`、`mapping_ocr.py`
- 同步：`scripts/sync_intel_library.py`
- 导入：`scripts/import_district_mapping_policies.py`
