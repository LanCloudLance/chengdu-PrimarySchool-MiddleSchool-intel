# 成都学区情报平台 — 项目近况报告

> 生成时间：2026-06-13 11:00  
> 分支：`feat/chengdu-edu-intel-mvp`（worktree）  
> 最后提交：`87c7213` fix(parsers): preserve image height in OCR tiling

---

## 一、项目目标

建设覆盖成都**七大核心城区**（武侯、锦江、青羊、成华、金牛、高新、天府）的教育情报平台，为家长提供：

| 学段 | 核心信息 |
|------|---------|
| **小学** | 所属区域、划片街道/范围、招生人数、不同招生类型比例 |
| **初中** | 招生人数、所属区域、对口小学、各类招生人数、区指标/市指标 |
| **高中** | 中考分数线、指标到校人数/要求 |

---

## 二、当前进度总览

```
 ████████████████████  文件系统数据   90%
 █████████████░░░░░░░  DB导入+同步    60%
 ██████████░░░░░░░░░░  前端稳定性     50%
 ████████░░░░░░░░░░░░  初中升学数据   40%
 ████░░░░░░░░░░░░░░░░  高中数据       20%
 ██░░░░░░░░░░░░░░░░░░  交叉验证       10%
```

---

## 三、文件系统数据状态

### 3.1 学校名录（`configs/districts/{code}/schools.yaml`）

| 区域 | 学校总数 | 小学 | 初中 | 九年一贯 | 数据来源 |
|------|---------|------|------|---------|---------|
| 武侯 | 101 | 63 | 37 | 1 | 本地宝学校大全（2026-06抓取），含mirror验证 |
| 锦江 | 28 | 26 | 1 | 1 | 本地宝 + 教育局公告 |
| 青羊 | 36 | 34 | 2 | 0 | 本地宝登记点公告 |
| 成华 | 41 | 38 | 2 | 1 | 本地宝登记点公告 |
| 金牛 | 63 | 56 | 0 | 7 | 本地宝学校名录（2026-04抓取） |
| 高新 | 43 | 33 | 1 | 9 | 本地宝 + 100hsl.com 划片表 |
| 天府 | 41 | 39 | 2 | 0 | 本地宝登记点公告 |
| **合计** | **353** | **289** | **47** | **19** | |

### 3.2 划片数据（`configs/districts/{code}/mapping_scraped.json`）

| 区域 | 文件总数 | 真实划片 | 待划片 | 数据年份 | 数据来源 |
|------|---------|---------|--------|---------|---------|
| 武侯 | 47 | 47 | 0 | 2025 | 教育局公告 + OCR + overrides |
| 锦江 | 25 | 25 | 0 | 2025 | 本地宝划片文章 |
| 青羊 | 32 | 32 | 0 | 2025 | 本地宝划片文章 |
| 成华 | 36 | 36 | 0 | 2025 | 本地宝划片文章 |
| 金牛 | 49 | 49 | 0 | 2025 | jjnz.com 完整表格 |
| 高新 | 41 | 41 | 0 | 2024+2026 | 100hsl.com + 本地宝中和片区 |
| 天府 | 38 | 38 | 0 | 2025 | 本地宝划片文章 |
| **合计** | **268** | **268** | **0** | | |

**文件层面已全部无 pending。**

---

## 四、数据库状态（DB）

### 4.1 学校表

| 区域 | DB学校数 | 文件学校数 | 差异 |
|------|---------|----------|------|
| 武侯 | 101 | 101 | ✅ 一致 |
| 锦江 | 28 | 28 | ✅ 一致 |
| 青羊 | 36 | 36 | ✅ 一致 |
| 成华 | 41 | 41 | ✅ 一致 |
| 金牛 | **70** | 63 | ⚠️ DB多出7所（可能是旧数据残留） |
| 高新 | 43 | 43 | ✅ 一致 |
| 天府 | 41 | 41 | ✅ 一致 |
| **合计** | **360** | **353** | 差7 |

### 4.2 划片记录（`enrollment_policies` WHERE policy_type='district_mapping'）

| 区域 | 总划片 | 已映射(非pending) | 待映射(pending) | 状态 |
|------|--------|-----------------|----------------|------|
| 武侯 | 112 | 86 | 26 | ⚠️ 有26条待映射 |
| 锦江 | 26 | 25 | 1 | ✅ |
| 青羊 | 34 | 32 | 2 | ⚠️ |
| 成华 | 38 | 36 | 2 | ⚠️ |
| 金牛 | 68 | 19 | **49** | ❌ 严重过期 |
| 高新 | 42 | 5 | **36** | ❌ 严重过期 |
| 天府 | 38 | 38 | 0 | ✅ |

**核心问题：DB划片数据与文件严重不同步。** 金牛和高新的文件已有49和41条真实数据，但DB里只有19和5条被映射。需要重新导入。

### 4.3 招生记录（`school_enrollment`）

| 区域 | 招生记录数 | 状态 |
|------|----------|------|
| 武侯 | 101 | ✅ 全覆盖 |
| 锦江 | 28 | ✅ 全覆盖 |
| 青羊 | 36 | ✅ 全覆盖 |
| 成华 | 41 | ✅ 全覆盖 |
| 金牛 | **7** | ❌ 仅7所 |
| 高新 | **9** | ❌ 仅9所 |
| 天府 | 41 | ✅ 全覆盖 |

### 4.4 升学记录（`promotion_policies`）

| 区域 | 升学记录数 | 状态 |
|------|----------|------|
| 武侯 | 97 | ✅ |
| 锦江 | 26 | ✅ |
| 青羊 | 8 | ⚠️ 偏少 |
| 成华 | 7 | ⚠️ 偏少 |
| 金牛 | 7 | ⚠️ 偏少 |
| 高新 | 5 | ⚠️ 偏少 |
| 天府 | 6 | ⚠️ 偏少 |

### 4.5 情报采集记录（`intel_entries`）

| 区域 | mapping | gov_article | mirror_page | 状态 |
|------|---------|-------------|-------------|------|
| 武侯 | 3 | 1 | 73 | ✅ 基准区 |
| 锦江 | 1 | 1 | 0 | ⚠️ 缺mirror |
| 青羊 | 1 | 1 | 0 | ⚠️ 缺mirror |
| 成华 | 1 | 1 | 0 | ⚠️ 缺mirror |
| 金牛 | **0** | 1 | 0 | ❌ 缺mapping+mirror |
| 高新 | 3 | 1 | 0 | ⚠️ 缺mirror |
| 天府 | 1 | 1 | 0 | ⚠️ 缺mirror |

---

## 五、数据库结构现状

### 5.1 表结构

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `districts` | 区/县 | name, code, level(core/extended) |
| `schools` | 学校主数据 | name, short_name, district_id, type(public/private), level(primary/middle/nine_year), address, source_urls(JSONB), metadata(JSONB) |
| `enrollment_policies` | 招生/划片政策 | school_id, district_id, policy_type(school_enrollment/gov_policy/district_mapping), year, fields(JSONB), confidence |
| `promotion_policies` | 升学政策 | school_id, target_school_id, district_id, year, fields(JSONB) |
| `intel_entries` | 情报采集 | district_id, school_id, intel_type, source_url, raw_text, structured_fields(JSONB), data_year, is_reference |
| `data_sources` | 数据源配置 | name, source_type, url, parser_strategy, schedule |
| `raw_documents` | 原始文档 | source_id, content_hash, raw_content, fetched_at |
| `record_versions` | 版本快照 | record_type, record_id, version, fields_snapshot |
| `field_changes` | 变更检测 | record_type, record_id, from/to_version, field_path, old/new_value |
| `job_runs` | 任务运行记录 | source_id, status, docs_fetched, changes_detected |

### 5.2 枚举值

| 枚举 | 当前值 | 缺失 |
|------|--------|------|
| SchoolLevel | primary, middle, nine_year | **high_school（高中）** |
| SchoolType | public, private | — |
| PolicyType | school_enrollment, gov_policy, district_mapping | 无专门的高中指标类型 |
| IntelType | mapping, enrollment, promotion, gov_article, mirror_page | 无中考分数线类型 |

### 5.3 字段存储方式

所有业务字段都存储在 JSONB 的 `fields` 列中，常用 key 包括：

```
enrollment_scope     → 划片范围（街道/社区文本）
mapping_status       → 划片状态（verified/reference/pending_official）
registration_time    → 登记时间
requirements         → 招生条件
contact              → 咨询电话
promotion_overview   → 小升初概要
target_schools       → 对口初中
target_source        → 对口依据
lottery_note         → 摇号说明
```

**问题**：招生人数、指标数、分数线等**数值型**字段目前无标准存储约定。

---

## 六、前端现状

### 6.1 页面结构

| 页面 | URL | 功能 | 状态 |
|------|-----|------|------|
| 学校搜索首页 | `/` | 下拉框选择学校/片区/区县/类型/学段，HTMX实时搜索 | ✅ 基本可用 |
| 学校详情页 | `/schools/{id}` | 显示基本信息、划片范围、招生政策、升学政策、变更历史 | ⚠️ 格式不稳定 |
| 政府政策页 | `/policies/government` | 展示区级统一招生政策 | ✅ 基本可用 |

### 6.2 已知前端问题

1. **划片文本格式不统一**：
   - 武侯区划片均长182字符，高新均长仅29字符
   - 不同来源的划片描述风格差异大（有的详细到门牌号，有的只写"XX路以南"）
   - 金牛区划片来自网页抓取，包含HTML解析残留（多余空格、断句不完整）

2. **搜索结果展示不稳定**：
   - `school_results.html` 依赖 `mapping_summaries` 上下文变量，若后端未正确传入会报 `UndefinedError`
   - HTMX局部刷新时，部分CSS样式可能丢失

3. **下拉框选项过多**：
   - 学校名称下拉框有 360+ 个选项，无分组/搜索功能
   - 片区下拉框内容混杂，不同区的scope混在一起

4. **学段标签不完整**：
   - 只有"小学/初中/九年一贯制"三种显示
   - 金牛区7所nine_year学校显示为"九年一贯制"，不够直观

---

## 七、问题清单

### 🔴 P0 — 阻塞MVP

| # | 问题 | 影响 | 修复方案 |
|---|------|------|---------|
| 1 | DB划片数据与文件严重不同步 | 金牛49→DB仅19，高新41→DB仅5 | 重新运行 `import_district_mapping_policies.py --all-core` |
| 2 | 金牛区14所公办小学缺划片 | 文件系统已0 pending但verify仍FAIL（因为DB中旧pending未清） | 先清DB旧数据再重导 |
| 3 | 金牛区DB有70所学校但文件仅63所 | DB残留旧数据，多出的7所无对应文件 | 需要清理DB中无文件对应的学校 |
| 4 | 划片文本格式不统一 | 前端展示混乱，用户体验差 | 标准化脚本统一格式（标点、分段） |

### 🟡 P1 — 影响质量

| # | 问题 | 影响 | 修复方案 |
|---|------|------|---------|
| 5 | 缺少高中数据（SchoolLevel无high_school） | 用户要求的高中学段完全缺失 | 扩展枚举 + 新建采集脚本 |
| 6 | 初中升学数据偏少（5区仅5-8条） | 对口关系、指标数据不完整 | 多源采集中考升学对口 |
| 7 | 金牛/高新招生记录极少（7/9条） | 学校详情页显示"暂无招生政策数据" | 补全school_enrollment导入 |
| 8 | 前端下拉框体验差（360+无分组） | 用户难以快速定位 | 添加区县分组 + 搜索输入框 |
| 9 | 前端mapping_summaries偶尔undefined | 页面报错 | 确保所有路由都传入该变量 |

### 🟢 P2 — 锦上添花

| # | 问题 | 影响 | 修复方案 |
|---|------|------|---------|
| 10 | 缺少mirror_page情报记录 | 非武侯区无镜像页存证 | 后续补采 |
| 11 | 数据源单一（主要依赖本地宝） | 用户要求多源交叉验证 | 引入教育局官网、学校官网等 |
| 12 | 无数据更新机制 | 手动抓取无法持续 | 设计定时任务框架 |

---

## 八、待办任务列表

### Phase 1：数据修复（预计2小时）

- [ ] 1.1 清理DB中金牛区7所多余学校
- [ ] 1.2 重新导入所有区的划片数据到DB（`import_district_mapping_policies.py --all-core`）
- [ ] 1.3 补全金牛/高新的 school_enrollment 记录
- [ ] 1.4 运行 `verify_district_parity --db` 确认全部PASS
- [ ] 1.5 金牛区14所剩余学校寻找数据源并补全

### Phase 2：前端稳定化（预计1.5小时）

- [ ] 2.1 划片文本格式标准化脚本（统一标点、去除HTML残留、分段显示）
- [ ] 2.2 修复 mapping_summaries undefined 问题
- [ ] 2.3 下拉框添加按区县分组
- [ ] 2.4 学校详情页优化划片展示（分段、折叠长文本）

### Phase 3：多源交叉验证（预计2小时）

- [ ] 3.1 轮次1：学校名录 — 本地宝 vs 教育局官网 vs 100hsl.com 比对
- [ ] 3.2 轮次2：划片范围 — jjnz.com vs bendibao vs 学校官网 比对
- [ ] 3.3 轮次3：招生人数 — 各区教育局招生计划文件
- [ ] 3.4 轮次4：初中对口 — 小升初划片表 vs 小学划片 交叉
- [ ] 3.5 轮次5：最终数据质量报告

### Phase 4：数据扩展（预计1.5小时）

- [ ] 4.1 扩展 SchoolLevel 枚举添加 high_school
- [ ] 4.2 采集高中数据（中考分数线、指标到校）
- [ ] 4.3 补充初中升学对口详细数据（区指标/市指标）

### Phase 5：验收与提交（预计1小时）

- [ ] 5.1 浏览器端到端测试
- [ ] 5.2 `verify_district_parity --db` 全PASS
- [ ] 5.3 Git commit + push
- [ ] 5.4 更新PR

---

## 九、数据源清单

| 来源 | URL | 数据类型 | 已使用 |
|------|-----|---------|--------|
| 成都本地宝 | cd.bendibao.com | 学校名录、划片、政策 | ✅ |
| 好师来 | 100hsl.com | 划片表格、升学对口 | ✅ |
| 金牛教育(jjnz) | jjnz.com | 2025金牛划片完整表 | ✅ |
| 成都教育局 | edu.chengdu.gov.cn | 官方政策文件 | ⚠️ 待采 |
| 成都招生考试网 | cdzk.com | 招生平台入口 | ⚠️ 待采 |
| 各区教育局官网 | 各区 | 区级划片公告 | ⚠️ 待采 |
| 学校官网/公众号 | 各学校 | 招生简章 | ⚠️ 待采 |

---

## 十、未提交的代码变更

```
 configs/districts/gaoxin/mapping_scraped.json      | 429 ++++++++--
 configs/districts/gaoxin/schools.yaml              | 378 ++++++++-
 configs/districts/jinniu/mapping_scraped.json      | 903 ++++++++++-----------
 configs/districts/jinniu/schools.yaml              | 745 ++++++++++++++++-
 docker-compose.yml                                 |   20 +-
 packages/api/src/chengdu_edu_api/routes/pages.py   |   26 +
 .../api/src/chengdu_edu_api/templates/index.html   |   26 +-
 .../parsers/src/chengdu_edu_parsers/mapping_ocr.py |    2 +-
 8 files changed, 1954 insertions(+), 575 deletions(-)
```
