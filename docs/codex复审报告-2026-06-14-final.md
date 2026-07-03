# Codex 复审报告 - Phase 2 执行完成

**执行时间**: 2026年6月14日 23:55  
**执行人**: Cursor（执行工程师）  
**审核人**: Codex

---

## 一、修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `configs/schools.yaml` | 修改 | 删除全部5个区（锦江/青羊/成华/高新/天府）共34条旧学校记录，保留注释引用 |
| `packages/api/src/chengdu_edu_api/routes/pages.py` | 修改 | 添加划片过滤函数 `_is_dropdown_scope()`，学校查询按区县分组 |
| `packages/api/src/chengdu_edu_api/templates/index.html` | 修改 | 学校下拉框使用 `<optgroup>` 按区县分组 |
| `scripts/verify_district_parity.py` | 修改 | 加严7条验证规则，输出文件 vs DB 对比 |
| `scripts/import_schools.py` | 修改 | `load_schools_config()` 防御空 schools 字段（返回空列表而非 None） |

---

## 二、configs/schools.yaml 全量清理结果

**清理前**：34条旧学校记录（锦江8 + 青羊8 + 成华7 + 高新5 + 天府6）

**清理后**：全部替换为注释引用，文件仅保留头部元数据和7个区的注释指向：

```yaml
schools:
  # ── 锦江区 ──
  # 完整清单见 configs/districts/jinjiang/schools.yaml（28 所）

  # ── 青羊区 ──
  # 完整清单见 configs/districts/qingyang/schools.yaml（36 所）

  # ── 武侯区 ──
  # 完整清单见 configs/districts/wuhou/schools.yaml（101 所）

  # ── 成华区 ──
  # 完整清单见 configs/districts/chenghua/schools.yaml（41 所）

  # ── 金牛区 ──
  # 完整清单见 configs/districts/jinniu/schools.yaml（63 所）

  # ── 高新区 ──
  # 完整清单见 configs/districts/gaoxin/schools.yaml（43 所）

  # ── 天府新区 ──
  # 完整清单见 configs/districts/tianfu/schools.yaml（41 所）
```

**防污染效果**：重新运行 `import_schools.py` 时，全局文件不再贡献任何学校记录，所有学校数据仅来自各区的 `configs/districts/{code}/schools.yaml`，彻底消除孤儿学校风险。

---

## 三、首页划片下拉框过滤逻辑

在 `pages.py` 中添加了过滤函数：

```python
_SCOPE_KW = re.compile(r"[至界路街道巷大道区社区苑村]")
_SCOPE_NOISE = re.compile(r"招生|报名|年满|条件|政策|电脑随机|录取|简章|户籍.*残疾|少年|儿童.*少年")

def _is_dropdown_scope(text: str) -> bool:
    if not text or len(text) < 8 or len(text) > 120:
        return False
    if _SCOPE_NOISE.search(text):
        return False
    return bool(_SCOPE_KW.search(text))
```

**过滤规则**：
- 文本为空 / 长度 < 8 / 长度 > 120 → 排除
- 包含噪音关键词（招生/报名/年满/条件/政策/电脑随机/录取/简章/户籍残疾/少年） → 排除
- 不包含地理关键词（至/界/路/街/道/巷/大道/区/社区/苑/村） → 排除

**浏览器验证结果**：
- 划片下拉框共 124 项，全部为有效划片文本
- 成功过滤了"九年一贯制学校，小学部直升初中部"、"武侯区户籍智力残疾儿童、少年"等非划片文本

---

## 四、学校下拉框分组实现

**后端**：查询时 JOIN District 表获取区县名，按 `District.name, School.name` 排序

**前端**：使用 Jinja2 `namespace` + `<optgroup label="区县名">` 实现分组

**浏览器验证结果**：
- 学校按 7 个区县分组显示（天府新区、成华区、武侯区、金牛区、锦江区、青羊区、高新区）
- HTMX 搜索行为保持不变

---

## 五、verify_district_parity.py 加严后的规则

新增 `_load_file_counts()` 函数，从文件系统读取每区的 `file_schools` 和 `file_scopes`。

**7条加严验证规则**：

| 编号 | 规则 | 触发条件 |
|------|------|----------|
| 1 | DB学校数 vs 文件学校数 | 差异 > ±2 |
| 2 | DB已映射 >= 文件划片数×80% | mapped < file_scopes × 0.8 |
| 3 | DB划片总数 >= MIN_SCOPES | total < MIN_SCOPES[code] |
| 4 | enrollment >= DB学校数×80% | enrollment < schools × 0.8 |
| 5 | intel_mapping >= 1 | 无情报源记录 |
| 6 | gov_policy >= 1 | 无政策文件 |
| 7 | mapped/total >= 90% | 空划片记录占比过大 |

**输出格式**：`{区}: PASS | schools(file=X/db=Y) scopes(file=A/mapped=B/C) enroll=D ...`

---

## 六、验证命令完整结果

### 命令1：文件系统验证

```
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

### 命令2：文件系统 + 数据库验证

```
$ .venv/bin/python scripts/verify_district_parity.py --db

=== verify_district_parity ===
jinjiang: PASS | schools(file=28/db=28) scopes(file=25/mapped=25/26) enroll=28 intel_map=1 intel_mirror=0 gov=1
qingyang: PASS | schools(file=36/db=36) scopes(file=32/mapped=32/34) enroll=36 intel_map=1 intel_mirror=0 gov=1
wuhou: PASS | schools(file=101/db=101) scopes(file=47/mapped=56/61) enroll=101 intel_map=3 intel_mirror=73 gov=1
chenghua: PASS | schools(file=41/db=41) scopes(file=36/mapped=36/38) enroll=41 intel_map=1 intel_mirror=0 gov=1
jinniu: PASS | schools(file=63/db=63) scopes(file=59/mapped=59/63) enroll=63 intel_map=1 intel_mirror=0 gov=1
gaoxin: PASS | schools(file=43/db=43) scopes(file=40/mapped=41/41) enroll=43 intel_map=3 intel_mirror=0 gov=1
tianfu: PASS | schools(file=41/db=41) scopes(file=38/mapped=38/38) enroll=41 intel_map=1 intel_mirror=0 gov=1
ALL DISTRICTS PARITY PASS
```

### 命令3：测试套件

```
$ .venv/bin/pytest packages/storage/tests packages/api/tests -q

..........                                                               [100%]
10 passed in 0.58s
```

---

## 七、待 Codex 确认

1. **高新36条 reference 数据**：保持 `reference` 状态不变，等官方2026数据后替换
2. **官方数据发布**：预计6月15日，届时爬取 edu.chengdu.gov.cn 保存为 `mapping_official_YYYY.json`
3. **前端截图**：已保存 `school-dropdown-screenshot.png` 和 `schoolarea-dropdown-screenshot.png`

---

**报告时间**: 2026-06-14 23:58  
**状态**: Phase 2 全部完成，等待 Codex 审核
