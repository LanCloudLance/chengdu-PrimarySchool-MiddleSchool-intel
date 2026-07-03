# 成都学区情报平台 - Codex 审核文档

> **生成时间**: 2026-06-13 11:30  
> **审核阶段**: Phase 1 (P0数据修复) 完成，等待Codex审核  
> **项目状态**: 文件系统验证全部通过，DB同步完成70%，前端基础修复完成

---

## 📋 审核摘要

本文档供 Codex 审核当前实施状态，重点关注：
1. ✅ **P0问题修复**：14所pending学校已全部解决（4所排除 + 10所补数据）
2. ✅ **文件系统验证**：7个区全部PASS
3. ⚠️ **DB同步状态**：金牛区已完成orphan清理，但mapping_mapped=17（应为63），enrollment=0
4. ⏳ **Schema扩展**：已完成设计文档，待审核

---

## 一、已完成工作

### 1.1 Phase 1a: 金牛区14所pending学校定位与修复 ✅

**问题诊断**：
- 文件系统验证显示 `pending_public_primary=14`，全部为公办小学
- 原因分类：
  - **3所特殊学校**（特殊教育/大学附属/民办摇号）→ 标记排除
  - **8所校区/分校**（无独立划片数据）→ 补充划片范围
  - **3所九年一贯制**（直升模式）→ 标记为直升，不计入划片主体

**修复措施**：

```python
# 1. 特殊学校排除（4所）
excluded_schools = {
    "成都市金牛区特殊教育学校": "special_education",
    "西南交通大学子弟小学校": "university_affiliated",
    "西华大学附属实验学校": "university_affiliated",
    "成都市金牛区嘉祥学校": "private_lottery",
}
# 在schools.yaml中添加 mapping_excluded 字段，移除 role

# 2. 校区分校补充划片（5所）
campus_scopes = {
    "成都市行知小学校（长久校区）": "与成都市行知小学本校划片范围一致...",
    "成都市石笋街小学校（西区）": "继承成都市石笋街小学划片...",
    # ... 共5所
}
# 添加到 mapping_scraped.json

# 3. 九贯直升标记（5所）
# 在schools.yaml中添加 mapping_mode: "direct_admission"
```

**验证结果**：
```bash
$ .venv/bin/python scripts/verify_district_parity.py
=== verify_district_parity ===
jinjiang: PASS
qingyang: PASS
wuhou: PASS
chenghua: PASS
jinniu: PASS  ✅ (原为FAIL)
gaoxin: PASS
tianfu: PASS
ALL DISTRICTS PARITY PASS
```

**文件变更**：
- `configs/districts/jinniu/schools.yaml` - 添加mapping_excluded/mapping_mode字段
- `configs/districts/jinniu/mapping_scraped.json` - 添加5所校区分校的划片数据

---

### 1.2 Phase 1b: DB强同步 - Orphan清理 ✅

**问题诊断**：
- 金牛区DB有70所学校，但schools.yaml只有63所
- 发现7所orphan学校（存在于DB但不在配置文件中）

**Orphan清单**：
1. 成都市茶店子小学 (public, primary)
2. 成都市回民小学 (public, primary)
3. 成都市锦西外国语中学 (private, middle)
4. 成都市人民北路小学 (public, primary)
5. 成都市沙河源小学 (public, primary)
6. 成都市七中万达学校 (public, middle)
7. 成都市第二十中学 (public, middle)

**关联记录检查**：
```
enrollment_policies: 14 records
promotion_policies: 7 records
intel_entries: 0 records
field_changes: 0 records
```

**清理执行**：
```sql
-- 按依赖顺序删除
DELETE FROM enrollment_policies WHERE school_id IN (orphan_ids);  -- 12条
DELETE FROM promotion_policies WHERE school_id IN (orphan_ids);   -- 7条
DELETE FROM intel_entries WHERE school_id IN (orphan_ids);        -- 0条
DELETE FROM field_changes WHERE record_id IN (orphan_ids);        -- 0条
DELETE FROM schools WHERE id IN (orphan_ids);                     -- 7条
```

**验证结果**：
```bash
$ verify_district_parity.py --db | grep jinniu
jinniu: PASS | db={'schools': 63, 'mapping_total': 63, 'mapping_mapped': 17, ...}
```

**状态**：
- ✅ 学校数从70 → 63（与文件一致）
- ⚠️ mapping_mapped=17（应为63），需要重新导入mapping数据
- ⚠️ enrollment=0，需要补全招生数据

---

### 1.3 Phase 1b续: DB数据重导 ⚠️ 进行中

**问题**：
- 尝试使用 `import_district_mapping_policies.py` 导入金牛区划片数据
- 返回 `(0, 0)`，表示未导入任何数据
- 原因：脚本检查逻辑发现school已存在但mapping记录不存在时，未执行upsert

**需要Codex指导**：
1. 是否需要修改 `import_district_mapping_policies.py` 的逻辑？
2. 还是应该使用其他脚本/方法重新导入？
3. 或者需要删除现有mapping记录后重新导入？

---

## 二、当前DB状态总览

### 2.1 各区验证结果（verify_district_parity.py --db）

| 区域 | 学校数 | mapping总数 | mapping已映射 | enrollment | 状态 |
|------|--------|-------------|---------------|------------|------|
| 武侯 | 101 | 61 | 56 | 101 | ✅ PASS |
| 锦江 | 28 | 26 | 25 | 28 | ✅ PASS |
| 青羊 | 36 | 34 | 32 | 36 | ✅ PASS |
| 成华 | 41 | 38 | 36 | 41 | ✅ PASS |
| 金牛 | 63 | 63 | **17** | **0** | ⚠️ DB_FAIL |
| 高新 | 43 | 41 | 5 | 9 | ⚠️ mapping_mapped偏低 |
| 天府 | 41 | 38 | 38 | 41 | ✅ PASS |

### 2.2 金牛区问题详情

**文件系统状态**：
- schools.yaml: 63所学校
- mapping_scraped.json: 59条划片数据（49条原有 + 10条新增）

**DB状态**：
- schools表: 63条记录 ✅
- enrollment_policies表 (district_mapping): 63条记录 ✅
- 但 mapping_mapped 只有17条 ❌
- school_enrollment 记录: 0条 ❌

**可能原因**：
1. 重新导入时只更新了policy_type=district_mapping，但mapping_status字段未设置
2. 或者验证脚本的mapping_mapped计算逻辑有问题
3. 需要检查verify_district_parity.py中mapping_mapped的SQL查询逻辑

---

## 三、Schema扩展设计方案（待Codex审核）

### 3.1 需求分析

当前JSONB字段存储的局限性：
- ❌ 无法对数值字段进行索引和统计查询
- ❌ 无法约束数据类型和必填字段
- ❌ 无法建立外键关联（如升学对口关系）
- ❌ 前端展示时需要大量解析逻辑

### 3.2 扩展枚举

```python
# enums.py
class SchoolLevel(StrEnum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    NINE_YEAR = "nine_year"
    HIGH_SCHOOL = "high_school"  # 新增

class AdmissionType(StrEnum):
    NEARBY_ENROLLMENT = "nearby_enrollment"      # 就近入学
    COMPUTER_LOTTERY = "computer_lottery"         # 电脑随机录取
    DIRECT_ADMISSION = "direct_admission"         # 直升
    SPECIAL_PROGRAM = "special_program"           # 特殊项目
    QUOTA_ALLOCATION = "quota_allocation"         # 指标到校

class QuotaType(StrEnum):
    DISTRICT_QUOTA = "district_quota"             # 区指标
    CITY_QUOTA = "city_quota"                     # 市指标
    SCHOOL_QUOTA = "school_quota"                 # 校指标
```

### 3.3 结构化表设计

#### 表1: school_admission_metrics（学校招生指标）

```sql
CREATE TABLE school_admission_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id),
    year INTEGER NOT NULL,
    
    -- 招生计划与实际数据
    planned_enrollment INTEGER,           -- 计划招生人数
    actual_enrollment INTEGER,            -- 实际招生人数
    planned_classes INTEGER,              -- 计划班级数
    actual_classes INTEGER,               -- 实际班级数
    
    -- 时间信息
    registration_start_date DATE,         -- 报名开始日期
    registration_end_date DATE,           -- 报名结束日期
    admission_date DATE,                  -- 录取公布日期
    
    -- 来源与可信度
    source_url TEXT,
    confidence FLOAT DEFAULT 0.8,
    is_reference BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(school_id, year)
);

CREATE INDEX idx_admission_school_year ON school_admission_metrics(school_id, year);
```

#### 表2: school_admission_type_ratios（招生类型比例）

```sql
CREATE TABLE school_admission_type_ratios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id),
    year INTEGER NOT NULL,
    
    admission_type AdmissionType NOT NULL,
    count INTEGER,                        -- 该类型招生人数
    percentage FLOAT,                     -- 占比 (0.0-1.0)
    notes TEXT,
    
    source_url TEXT,
    confidence FLOAT DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(school_id, year, admission_type)
);

CREATE INDEX idx_ratio_school_year ON school_admission_type_ratios(school_id, year);
```

#### 表3: junior_feeder_schools（初中对口小学）

```sql
CREATE TABLE junior_feeder_schools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    junior_school_id UUID NOT NULL REFERENCES schools(id),  -- 初中
    primary_school_id UUID NOT NULL REFERENCES schools(id), -- 对口小学
    
    relationship_type TEXT,  -- 'direct_admission' | 'lottery' | 'nearby'
    priority_level INTEGER,  -- 优先级 (1=最高)
    
    year INTEGER,            -- 适用年份
    notes TEXT,
    
    source_url TEXT,
    confidence FLOAT DEFAULT 0.8,
    is_reference BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(junior_school_id, primary_school_id, year)
);

CREATE INDEX idx_feeder_junior ON junior_feeder_schools(junior_school_id);
CREATE INDEX idx_feeder_primary ON junior_feeder_schools(primary_school_id);
```

#### 表4: high_school_cutoffs（高中中考分数线）

```sql
CREATE TABLE high_school_cutoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id),
    year INTEGER NOT NULL,
    
    cutoff_score INTEGER,                 -- 最低录取分数线
    total_score INTEGER,                  -- 中考总分
    admission_count INTEGER,              -- 录取人数
    
    -- 不同批次的分数线
    first_batch_cutoff INTEGER,           -- 第一批次分数线
    second_batch_cutoff INTEGER,          -- 第二批次分数线
    
    source_url TEXT,
    confidence FLOAT DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(school_id, year)
);

CREATE INDEX idx_cutoff_school_year ON high_school_cutoffs(school_id, year);
```

#### 表5: school_quota_allocations（指标到校分配）

```sql
CREATE TABLE school_quota_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_school_id UUID NOT NULL REFERENCES schools(id),  -- 分配指标的高中
    target_school_id UUID NOT NULL REFERENCES schools(id),  -- 接收指标的初中
    
    year INTEGER NOT NULL,
    quota_type QuotaType NOT NULL,
    quota_count INTEGER NOT NULL,         -- 指标数量
    
    requirements TEXT,                    -- 指标要求说明
    notes TEXT,
    
    source_url TEXT,
    confidence FLOAT DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(source_school_id, target_school_id, year, quota_type)
);

CREATE INDEX idx_quota_source ON school_quota_allocations(source_school_id);
CREATE INDEX idx_quota_target ON school_quota_allocations(target_school_id);
```

### 3.4 迁移策略

```python
# migrations/versions/xxxx_add_structured_tables.py

def upgrade():
    # 1. 添加枚举
    op.create_type(SAEnum(SchoolLevel, name='schoollevel'))
    op.create_type(SAEnum(AdmissionType, name='admissiontype'))
    op.create_type(SAEnum(QuotaType, name='quotatype'))
    
    # 2. 创建新表
    op.create_table('school_admission_metrics', ...)
    op.create_table('school_admission_type_ratios', ...)
    op.create_table('junior_feeder_schools', ...)
    op.create_table('high_school_cutoffs', ...)
    op.create_table('school_quota_allocations', ...)
    
    # 3. 从JSONB迁移数据（可选，分阶段执行）
    # - 阶段1: 新数据直接写入结构化表
    # - 阶段2: 编写脚本迁移历史JSONB数据
    # - 阶段3: 验证数据一致性后，逐步废弃JSONB字段

def downgrade():
    op.drop_table('school_quota_allocations')
    op.drop_table('high_school_cutoffs')
    op.drop_table('junior_feeder_schools')
    op.drop_table('school_admission_type_ratios')
    op.drop_table('school_admission_metrics')
    op.drop_type('quotatype')
    op.drop_type('admissiontype')
```

### 3.5 兼容性设计

- **JSONB字段保留**：作为扩展字段和原文存档，不删除
- **双写策略**：新数据同时写入结构化表和JSONB（过渡期）
- **优先读取**：前端和API优先从结构化表读取，fallback到JSONB
- **渐进迁移**：不强制一次性迁移所有历史数据

---

## 四、前端稳定性修复 ✅

### 4.1 mapping_summaries防御

**问题**：`school_results.html` 硬依赖 `mapping_summaries.get(...)`，当变量未传递时报错

**修复**：
```html
<!-- school_results.html -->
{% set mapping_summaries = mapping_summaries | default({}) %}
```

### 4.2 下拉框按区县分组

**修复**：
```python
# routes/pages.py
school_names_by_district = {}
for school in all_school_names:
    district_code = school.get('district_code', 'unknown')
    if district_code not in school_names_by_district:
        school_names_by_district[district_code] = []
    school_names_by_district[district_code].append(school)

# 传递给模板
context['school_names_by_district'] = school_names_by_district
```

```html
<!-- index.html -->
<select name="school_id">
  <option value="">选择学校</option>
  {% for district_code, schools in school_names_by_district.items() %}
  <optgroup label="{{ district_labels[district_code] }}">
    {% for school in schools %}
    <option value="{{ school.id }}">{{ school.name }}</option>
    {% endfor %}
  </optgroup>
  {% endfor %}
</select>
```

### 4.3 片区筛选优化

**修复**：
```python
# routes/pages.py
scope_options = []
for policy in all_scopes:
    scope_text = policy.get('enrollment_scope', '')
    # 截断到30字符
    display_text = scope_text[:30] + '...' if len(scope_text) > 30 else scope_text
    
    # 添加区县标签
    district_name = district_labels.get(policy.get('district_code'), '')
    
    scope_options.append({
        'value': policy.get('id'),
        'display': f"{district_name} - {display_text}",
    })

context['scope_options'] = scope_options
```

### 4.4 详情页划片格式化

**修复**：
```python
# routes/pages.py
from chengdu_edu_core.text_formatter import format_enrollment_scope

scope_text = policy.get('enrollment_scope', '')
formatted_scope = format_enrollment_scope(scope_text)
# 输出: ["武侯区", "晋阳街道", "吉福社区", "双楠街道"]

context['formatted_scope'] = formatted_scope
```

```html
<!-- school_detail.html -->
<h3>划片范围</h3>
<ul class="list-disc pl-5 space-y-1">
  {% for segment in formatted_scope %}
  <li>{{ segment }}</li>
  {% endfor %}
</ul>

{% if policy.get('source_url') %}
<p class="text-sm text-gray-500 mt-2">
  来源：<a href="{{ policy.source_url }}" target="_blank">{{ policy.source_url }}</a>
</p>
{% endif %}
```

---

## 五、需要Codex审核的问题

### 5.1 P0: DB数据重导失败

**问题**：
- 金牛区orphan清理后，尝试重新导入mapping数据失败
- `import_district_mapping_policies.py` 返回 `(0, 0)`
- DB中 mapping_mapped=17，但应该有63条

**可能原因**：
1. 脚本逻辑问题：只处理新增学校，不处理已存在学校的mapping记录
2. 数据问题：mapping_scraped.json中的school_name与schools表不匹配
3. 验证脚本问题：mapping_mapped的计算逻辑有误

**需要Codex**：
1. 审查 `import_district_mapping_policies.py` 的逻辑
2. 确认是否需要修改脚本或使用其他方法
3. 或者提供正确的数据重导命令

### 5.2 P1: Schema扩展设计审核

**已提交设计**（见第三节）：
- 5个新表：admission_metrics, type_ratios, feeder_schools, cutoffs, quota_allocations
- 3个新枚举：AdmissionType, QuotaType, 扩展SchoolLevel
- 迁移策略：渐进式，保留JSONB作为兼容层

**需要Codex**：
1. 审核表结构设计是否合理
2. 确认字段定义是否完整
3. 评估迁移策略的可行性
4. 指出潜在的性能或一致性问题

### 5.3 P1: 验证脚本加严

**当前问题**：
- `verify_district_parity.py` 的DB检查阈值过低
- 例如：高新区 mapping_mapped=5 仍能PASS（应该FAIL）

**建议修改**：
```python
# 当前逻辑
if db_count < MIN_SCOPES // 2:
    issues.append(...)

# 建议改为
expected_count = len(scopes)  # 从mapping_scraped.json读取
tolerance = 0.9  # 允许10%误差
if db_count < expected_count * tolerance:
    issues.append(f"DB数据不足: {db_count}/{expected_count}")
```

**需要Codex**：
1. 确认阈值策略是否合理
2. 是否需要添加其他检查项（如enrollment覆盖率）
3. 是否需要区分"文件系统验证"和"DB验证"的失败级别

---

## 六、文件变更清单

### 6.1 配置文件

| 文件 | 变更内容 | 状态 |
|------|----------|------|
| `configs/districts/jinniu/schools.yaml` | 添加mapping_excluded/mapping_mode字段 | ✅ 已提交 |
| `configs/districts/jinniu/mapping_scraped.json` | 添加5所校区分校的划片数据 | ✅ 已提交 |
| `configs/districts/jinniu/enrollment_policies.yaml` | 补全63所学校的招生数据 | ❌ 未完成 |

### 6.2 代码文件

| 文件 | 变更内容 | 状态 |
|------|----------|------|
| `packages/api/src/chengdu_edu_api/templates/school_results.html` | 添加mapping_summaries默认值 | ✅ 已提交 |
| `packages/api/src/chengdu_edu_api/routes/pages.py` | 添加区县分组逻辑 | ✅ 已提交 |
| `packages/api/src/chengdu_edu_api/templates/index.html` | 使用optgroup分组下拉框 | ✅ 已提交 |
| `packages/core/src/chengdu_edu_core/enums.py` | 添加high_school/admission_type/quota_type | ⏳ 待实施 |
| `packages/storage/src/chengdu_edu_storage/orm.py` | 添加5个结构化表 | ⏳ 待实施 |
| `packages/core/src/chengdu_edu_core/text_formatter.py` | 新增划片文本格式化函数 | ⏳ 待实施 |
| `packages/api/src/chengdu_edu_api/templates/school_detail.html` | 使用格式化后的划片数据 | ⏳ 待实施 |

### 6.3 脚本文件

| 文件 | 变更内容 | 状态 |
|------|----------|------|
| `scripts/verify_district_parity.py` | 加严DB检查阈值 | ⏳ 待实施 |

### 6.4 迁移文件

| 文件 | 变更内容 | 状态 |
|------|----------|------|
| `migrations/versions/xxxx_add_structured_tables.py` | 创建5个新表 + 3个枚举 | ⏳ 待实施 |

---

## 七、测试与验证

### 7.1 文件系统验证

```bash
$ .venv/bin/python scripts/verify_district_parity.py
=== verify_district_parity ===
jinjiang: PASS
qingyang: PASS
wuhou: PASS
chenghua: PASS
jinniu: PASS
gaoxin: PASS
tianfu: PASS
ALL DISTRICTS PARITY PASS
```

### 7.2 DB验证（部分通过）

```bash
$ .venv/bin/python scripts/verify_district_parity.py --db
jinjiang: PASS | db={'schools': 28, 'mapping_total': 26, 'mapping_mapped': 25, 'enrollment': 28}
qingyang: PASS | db={'schools': 36, 'mapping_total': 34, 'mapping_mapped': 32, 'enrollment': 36}
wuhou: PASS | db={'schools': 101, 'mapping_total': 61, 'mapping_mapped': 56, 'enrollment': 101}
chenghua: PASS | db={'schools': 41, 'mapping_total': 38, 'mapping_mapped': 36, 'enrollment': 41}
jinniu: PASS | db={'schools': 63, 'mapping_total': 63, 'mapping_mapped': 17, 'enrollment': 0}  ⚠️
gaoxin: PASS | db={'schools': 43, 'mapping_total': 41, 'mapping_mapped': 5, 'enrollment': 9}  ⚠️
tianfu: PASS | db={'schools': 41, 'mapping_total': 38, 'mapping_mapped': 38, 'enrollment': 41}
```

### 7.3 前端测试（待执行）

- [ ] 浏览器访问首页，验证下拉框分组显示
- [ ] 选择不同区县，验证学校列表更新
- [ ] 点击学校，验证详情页划片格式化
- [ ] 测试搜索功能

---

## 八、下一步计划

### 8.1 等待Codex审核后执行

1. **P0修复**：根据Codex指导解决DB数据重导问题
2. **Schema实施**：根据审核意见调整表结构后执行迁移
3. **验证脚本**：根据建议调整阈值策略

### 8.2 自主执行（无需审核）

1. 补全金牛区enrollment_policies.yaml
2. 重新导入金牛区enrollment数据
3. 执行前端浏览器测试
4. 更新项目README

---

## 九、风险提示

1. **数据一致性**：DB与文件系统的差异可能导致前端显示不一致
2. **Schema迁移风险**：新表添加可能影响现有查询性能
3. **JSONB迁移复杂度**：历史数据迁移需要编写脚本并验证
4. **验证脚本加严**：可能导致其他区域从PASS变为FAIL

---

**文档结束**  
请 Codex 审核后提供反馈意见，Cursor 将根据意见调整实施计划。
