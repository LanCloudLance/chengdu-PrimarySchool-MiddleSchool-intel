# 武侯区做透路线图 & 复制节奏

> **原则**：武侯区作为**唯一样板区**做到「家长可查、来源可追溯、状态可解释」，再复制到其他 6 区。  
> **配套**：操作步骤见 `.cursor/skills/chengdu-district-intel/SKILL.md`；进度回填见 `docs/PROJECT_PROGRESS.md` 第 7 节。

---

## 总体节奏（建议 4 周，可压缩）

| 周次 | 代号 | 主题 | 完成标志 |
|------|------|------|----------|
| W1 | **W1-划片闭环** | 清 pending + OCR 提质 + overrides | pending = 0；每校有 source_page |
| W2 | **W2-对口升学** | promotion 源 + 导入 + 推断白名单 | 公办小学对口说明覆盖 > 60% |
| W3 | **W3-门户可读** | 搜索 + 状态展示 + 来源标注 | 划片/地址可搜；UI 显示 reference/verified/pending |
| W4 | **W4-运营化** | 镜像 intel + 登记点 + 文档/ SKILL 定稿 | 镜像页入库；可复制到其他区 |

**2026 招生季（P0）**：在 W4 之后、**2026-04** 前接入登记点公告，**2026-06-15** 前切换 yjrx 官方划片（单独开迭代，不阻塞 W1–W4）。

---

## W1 — 划片闭环（当前优先级最高）

### W1.1 拉出 pending 清单 ✅

**工作文件**：`configs/districts/wuhou/mapping_pending.yaml`（10 校 + next_action）

```sql
-- 与 yaml 保持同步的验收 SQL
SELECT s.name, s.address, ep.fields->>'notes'
FROM enrollment_policies ep
JOIN schools s ON s.id = ep.school_id
JOIN districts d ON d.id = ep.district_id
WHERE d.code = 'wuhou'
  AND ep.policy_type = 'district_mapping'
  AND ep.year = 2025
  AND ep.fields->>'mapping_status' = 'pending_official'
ORDER BY s.name;
```

### W1.2 逐校补源（优先级）

1. 2025 OCR 长图（`198872_7` + `--ocr`）— 已有 17 校，扩覆盖
2. 2024 HTML 表 — 分校/跨行 parser 修复
3. 2025 零散调整文 — 搜本地宝「武侯 划片 调整」
4. 人工 overrides — `configs/districts/wuhou/mapping_overrides.yaml`（待建）

### W1.2 OCR + overrides ✅（2026-06-07）

- [x] OCR bbox 三列分列 + 校名跨行拼接
- [x] `scope_source` 合并优先级（html 优于 ocr）
- [x] `mapping_overrides.yaml` 接入 import
- [x] quick win：弟维校正、红专西路、三河（pending 10→7 预期）

### W1.3 余下 pending（技术 + 搜源）✅（2026-06-07）

- [x] 7 校根因：更名（北二外/音乐学院）、停招（太平→明远）、一校两区（新城南区）、同片区（洗面桥/附小西区）、2022 调整（金兴北路）
- [x] `school_aliases.yaml` +2、`mapping_overrides.yaml` +7（含新旧校名 copy）
- [x] `mapping_pending.yaml` 10/10 done；dry-run 原 pending 校均有 scope

### W1.4 验收 ✅（2026-06-05）

| 检查项 | 结果 |
|--------|------|
| unmatched = 0 | dry-run **0** |
| pending ≤ 3 | dry-run **0**；`mapping_pending.yaml` **10/10 done** |
| pytest 绿 | **32 passed** |
| 验收脚本 | `scripts/verify_wuhou_mapping.py`（`--db` 待 Docker 启动后补跑） |
| 进度文档 | `PROJECT_PROGRESS.md` W1.4 节 |

```bash
.venv/bin/python scripts/verify_wuhou_mapping.py
.venv/bin/python scripts/verify_wuhou_mapping.py --db   # 需 docker compose up -d
```

---

## W2 — 对口升学

### W2.1 发现源

- 本地宝「武侯 小升初 对口 / 升学安排」文章
- 填入 `configs/district_mapping_sources.yaml` → `promotion_urls`

### W2.2 导入

```bash
.venv/bin/python scripts/sync_intel_library.py --district wuhou  # 若 promotion 走 intel
.venv/bin/python scripts/import_school_promotion_targets.py --district wuhou
```

### W2.3 品牌推断白名单

- 文件：`configs/districts/wuhou/promotion_inference.yaml`（待建）
- 仅允许：棕北、玉林、龙江路等**已核实**品牌对
- 禁止：`武侯` 等 district 级 token（已在代码 stop_tokens）

### W2.4 验收

- 公办小学中 `promotion` 有 `target_school_id` 或明确「多校划片/摇号」文案 > 60%

---

## W3 — 门户可读

| 任务 | 位置 |
|------|------|
| 划片/地址全文搜索 | `search_query.py` + API query param |
| 详情页 mapping_status 徽章 | API fields + web 模板 |
| 来源链展示 | source_page、reference_year、framework_year |
| 免责声明 | 「转载仅供参考，以教育局/yjrx 为准」 |

---

## W4 — 运营化 & 复制准备

| 任务 | 说明 |
|------|------|
| 镜像页入 intel | `scraped_mirrors.json` → `intel_entries` MIRROR_PAGE |
| 登记点地址 | 4 月 edu 公告 → registration_point 字段 |
| SKILL 定稿 | 基于武侯踩坑更新 `.cursor/skills/.../SKILL.md` |
| 复制锦江 | 第一个非武侯区，走完整 SKILL 一遍 |

---

## 复制到其他区（W4 之后）

**顺序建议**：jinjiang → qingyang → chenghua → jinniu → gaoxin → tianfu

**每区最小交付**（1–2 天/区）：

1. `configs/districts/{code}/schools.yaml` inventory 对齐
2. `school_aliases.yaml`（如有更名/简称）
3. `district_mapping_sources.yaml` 至少 1 HTML + 可选 image_list
4. 跑 SKILL 标准管线三段式
5. `PROJECT_PROGRESS.md` 追加一节（可简写，指标换区 code）

**不做**：在武侯 W1 未完成前，不并行开多区 OCR 深度优化。

---

## 迭代节奏（日常）

| 频率 | 动作 |
|------|------|
| 每次开发会话结束 | 跑验证命令 + 更新 `PROJECT_PROGRESS.md` |
| 每周 | 对照 W* 阶段验收表；调整 roadmap 勾选 |
| 2026-04 | 启动 P0 登记点源 |
| 2026-06 | 启动 P0 yjrx 正式划片源 |
