# 成都学区招生情报系统 — 设计规格

**日期：** 2026-06-05  
**状态：** 已批准  
**项目代号：** chengdu-edu-intel

---

## 1. 背景与目标

### 1.1 问题

大成都范围内中小学的招生要求、升学路径、政府招生政策分散在教育局官网、学校网站、PDF 公告、微信公众号等渠道，信息格式不统一、更新无规律，家长难以系统查阅和追踪变更。

### 1.2 目标

构建一个可自动采集、结构化存储、支持版本追踪的招生情报工具，MVP 优先服务家长查询，长期作为数据引擎支撑研究者分析和多前端产品。

### 1.3 成功标准（MVP）

- 覆盖 7 个核心区域（锦江、青羊、武侯、成华、金牛、高新、天府新区）的公办 + 民办小学/初中
- 每条结构化记录可追溯到原始来源文档
- 支持按日/周/月可配置调度，默认策略开箱可用
- 政策变更可查看字段级历史
- 提供轻量 Web 查询页（按区域/学校名搜索）
- 本地 Docker Compose 一键启动，架构预留云端迁移

---

## 2. 需求决策记录

| 维度 | 决策 |
|------|------|
| 目标用户 | 长期：家长 + 研究者 + 内部团队；MVP 优先家长 |
| 地理范围 | MVP 7 区：锦江、青羊、武侯、成华、金牛、高新、天府新区 |
| 学校覆盖 | 公办 + 民办，小学 + 初中（含九年一贯制） |
| 内容类型 | 招生要求、升学要求、政府招生政策 |
| 交付形态 | 数据引擎 + 轻量查询 Web 页 |
| 更新机制 | 可配置调度 + 默认频率 + 版本历史 + 字段级变更 |
| 采集解析 | 固定格式用规则，非结构化用 LLM（混合模式） |
| 部署 | 本地先验证，Docker Compose，配置外置，预留云端迁移 |
| 架构方案 | 模块化单体（方案 A） |

---

## 3. 整体架构

### 3.1 架构选型

采用**模块化单体**：单仓库、按职责分包、Docker Compose 部署。MVP 阶段不引入消息队列，模块间通过 Python 接口直接调用。后续可按模块边界拆分为独立服务。

### 3.2 项目结构

```
chengdu-edu-intel/
├── docker-compose.yml
├── .env.example
├── packages/
│   ├── core/               # 共享：领域模型、枚举、工具
│   ├── collectors/         # 数据采集器（按数据源插件化）
│   ├── parsers/            # 解析器（RuleParser / LLMParser）
│   ├── storage/            # 数据库访问、版本管理、changelog
│   ├── scheduler/          # 调度任务注册与执行
│   ├── api/                # FastAPI REST 接口
│   └── web/                # 轻量查询前端
├── configs/
│   ├── districts.yaml      # 7 区配置
│   ├── sources.yaml        # 数据源注册
│   ├── schedules.yaml      # 默认更新频率
│   └── source_rules/       # RuleParser 规则文件（按数据源）
└── docs/
```

### 3.3 模块职责

| 模块 | 单一职责 | 对外接口 |
|------|----------|----------|
| collectors | 从指定 URL/渠道抓取原始内容 | `collect(source_id) → RawDocument` |
| parsers | 将原始内容结构化为标准字段 | `parse(raw, strategy) → ParsedRecord` |
| storage | 持久化、版本快照、字段 diff、查询 | `upsert()`, `get_history()`, `search()` |
| scheduler | 按配置触发采集任务，记录运行日志 | cron 表达式 + 手动 trigger API |
| api | 对外 HTTP 接口 | REST JSON |
| web | 家长查询页 | 调用 api |

### 3.4 数据流

```
触发（定时 / 手动）
    → Scheduler 读取 sources.yaml
    → Collector 抓取 → RawDocument（含 content_hash）
    → hash 相同 → skipped
    → hash 不同 → Parser（rule / llm / hybrid）
    → Storage upsert + 版本 diff + field_changes
```

### 3.5 技术选型

| 层 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| 数据库 | PostgreSQL 16 |
| API | FastAPI |
| 爬虫 | Playwright + httpx |
| PDF 提取 | pdfplumber |
| 调度 | APScheduler（MVP） |
| LLM | 可配置 Provider（OpenAI 兼容 API） |
| 前端 | HTMX + Alpine.js + Tailwind |
| 容器 | Docker Compose |

### 3.6 扩展点

- **新区域**：`districts.yaml` 加条目 + 注册 sources
- **新数据源**：实现 `BaseCollector` 子类 + `sources.yaml` 注册
- **新内容类型**：扩展 `ParsedRecord` schema 和 JSONB fields，不改表结构
- **新前端产品**：只依赖 api，与 web 平行
- **拆微服务**：scheduler + collectors 可独立为 worker 服务

---

## 4. 数据模型

### 4.1 实体关系

- District 1:N School
- School 1:N EnrollmentPolicy, PromotionPolicy
- GovernmentPolicy N:1 District
- DataSource 1:N RawDocument
- RawDocument 1:1 ParsedRecord（解析产出）
- ParsedRecord 1:N RecordVersion
- RecordVersion 1:N FieldChange

### 4.2 核心表

#### districts

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | text | 区域名称 |
| code | text | 内部编码，如 `jinjiang` |
| level | enum | `core` / `extended` |

#### schools

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | text | 学校全称 |
| short_name | text | 简称（搜索用） |
| district_id | FK | 所属区域 |
| type | enum | `public` / `private` |
| level | enum | `primary` / `middle` / `nine_year` |
| address | text | 地址 |
| source_urls | jsonb | 官网、公众号等链接 |
| metadata | jsonb | 扩展字段 |

#### data_sources

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | text | 数据源名称 |
| source_type | enum | `gov_website` / `school_website` / `wechat` / `pdf` |
| url | text | 采集入口 |
| parser_strategy | enum | `rule` / `llm` / `hybrid` |
| schedule | text | cron 表达式 |
| district_id | FK | 可选 |
| school_id | FK | 可选 |
| is_active | bool | 是否启用 |

#### raw_documents

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| source_id | FK | 来源 |
| content_hash | text | SHA256，变更检测 |
| raw_content | text | 正文 |
| raw_file_path | text | PDF/附件路径 |
| fetched_at | timestamptz | 采集时间 |
| http_status | int | HTTP 状态 |

#### enrollment_policies

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| school_id | FK | 关联学校（政府政策可为 null） |
| district_id | FK | 关联区域 |
| policy_type | enum | `school_enrollment` / `gov_policy` / `district_mapping` |
| year | int | 招生年份 |
| fields | jsonb | 结构化内容 |
| source_doc_id | FK | 原始文档 |
| confidence | float | LLM 置信度 0–1 |
| current_version | int | 当前版本号 |

**fields JSONB schema（MVP）：**

```json
{
  "enrollment_scope": "招生范围描述",
  "registration_time": "2026-03-01 ~ 2026-03-15",
  "requirements": ["户籍要求", "房产要求"],
  "quota": 300,
  "lottery_rule": "摇号规则（民办）",
  "contact": "咨询电话",
  "notes": "补充说明"
}
```

#### promotion_policies

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| school_id | FK | 来源校 |
| target_school_id | FK | 目标校 |
| district_id | FK | 区域 |
| year | int | 年份 |
| fields | jsonb | 结构化内容 |
| source_doc_id | FK | 原始文档 |
| current_version | int | 版本号 |

**fields JSONB schema：**

```json
{
  "promotion_type": "对口直升 / 摇号 / 指标到校",
  "target_schools": ["XX中学"],
  "conditions": ["学籍要求"],
  "ratio": "50%直升",
  "notes": ""
}
```

#### record_versions

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| record_type | enum | `enrollment` / `promotion` |
| record_id | UUID | 政策 ID |
| version | int | 版本序号 |
| fields_snapshot | jsonb | 该版本完整字段 |
| source_doc_id | FK | 依据的原始文档 |
| created_at | timestamptz | 创建时间 |

#### field_changes

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| record_type | enum | `enrollment` / `promotion` |
| record_id | UUID | 政策 ID |
| from_version | int | 旧版本 |
| to_version | int | 新版本 |
| field_path | text | 如 `fields.enrollment_scope` |
| old_value | text | 变更前 |
| new_value | text | 变更后 |
| detected_at | timestamptz | 检测时间 |

#### job_runs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| source_id | FK | 数据源 |
| status | enum | `success` / `failed` / `skipped` |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz | 结束时间 |
| error_message | text | 失败原因 |
| docs_fetched | int | 采集数量 |
| changes_detected | int | 变更数 |

### 4.3 变更检测逻辑

1. 采集新文档，计算 `content_hash`
2. hash 相同 → `job_runs.status = skipped`，结束
3. hash 不同 → 解析 → 与当前 fields 做 diff
4. 无字段变化 → 仅存档 raw_document
5. 有字段变化 → `current_version + 1`，写入 record_versions 和 field_changes

---

## 5. 采集与解析

### 5.1 采集器

```python
class BaseCollector(Protocol):
    source_type: str
    async def collect(self, source: DataSource) -> RawDocument: ...
```

| 采集器 | 场景 | 实现 |
|--------|------|------|
| HttpCollector | 静态 HTML | httpx |
| PlaywrightCollector | JS 渲染页 | 无头浏览器 |
| PdfCollector | PDF 公告 | 下载 + pdfplumber |
| WechatCollector | 公众号（预留） | MVP 手动录入 URL |

### 5.2 MVP 数据源优先级

| 优先级 | 来源 | 解析策略 |
|--------|------|----------|
| P0 | 7 区教育局官网招生政策 | rule |
| P0 | 各区划片/学区公告 PDF | rule + LLM 辅助 |
| P1 | 公办学校官网招生简章 | rule |
| P1 | 民办学校官网招生页 | llm |
| P2 | 公众号推文（人工种子 URL） | llm |

### 5.3 解析器

- **RuleParser**：`configs/source_rules/` 下 YAML 规则（XPath / 正则 / 表格映射）
- **LLMParser**：原始文本 + JSON schema → 结构化 fields + confidence
- **confidence < 0.7** → 标记 `needs_review = true`（MVP 仅标记，审核 UI 后置）

### 5.4 默认调度策略

```yaml
defaults:
  gov_policy: "0 0 1 * *"        # 每月 1 号
  school_info: "0 0 * * 1"       # 每周一
  enrollment_season: "0 6 * * *"   # 招生季每日 6:00

season_override:
  months: [3, 4, 5, 6]
  enrollment_brochure: "0 6 * * *"
```

### 5.5 错误处理

| 场景 | 处理 |
|------|------|
| 404 / 超时 | 重试 3 次（指数退避），失败不覆盖现有数据 |
| PDF 解析失败 | 保留 raw_file，标记 parse_error |
| LLM 格式错误 | 重试 1 次，仍失败则仅存 raw_document |
| 网站结构变更 | 标记 source `needs_rule_update = true` |
| 并发 | MVP 串行，同一 source 不并行 |

---

## 6. API 设计

### 6.1 查询接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/districts` | 区域列表 |
| GET | `/api/schools` | 学校搜索（district, type, level, q, 分页） |
| GET | `/api/schools/{id}` | 学校详情 + 当前政策 |
| GET | `/api/schools/{id}/history` | 变更历史 |
| GET | `/api/policies/enrollment` | 招生政策搜索 |
| GET | `/api/policies/enrollment/{id}` | 政策详情 + 来源 |
| GET | `/api/policies/enrollment/{id}/changes` | 字段级变更 |
| GET | `/api/policies/promotion` | 升学政策搜索 |
| GET | `/api/policies/government` | 政府政策（按区域） |

### 6.2 管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs/trigger` | 手动触发 `{scope, target_id?}` |
| GET | `/api/jobs/runs` | 运行日志 |
| GET | `/api/sources` | 数据源列表 |
| PATCH | `/api/sources/{id}` | 启用/禁用 |
| GET | `/api/stats` | 概览统计 |

### 6.3 响应要求

每条政策记录必须包含：结构化 fields、来源 URL、最后更新时间、confidence（LLM 时）、has_recent_changes 标志。

---

## 7. 查询 Web 页

### 7.1 MVP 页面

1. **首页/搜索** — 学校名搜索 + 区域/类型/学段筛选 + 结果列表（含「近期有变更」标记）
2. **学校详情** — 招生政策、升学信息、变更历史、原文链接
3. **政府政策列表** — 按区域浏览教育局政策

### 7.2 前端栈

HTMX + Alpine.js + Tailwind，由 FastAPI 提供页面或 API 驱动渲染。

---

## 8. 部署

### 8.1 Docker Compose 服务

- `db` — PostgreSQL 16
- `api` — FastAPI（端口 8000）
- `scheduler` — APScheduler worker
- `web` — 查询前端（端口 3000）

### 8.2 环境变量（.env）

- `DATABASE_URL`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- `SCHEDULER_ENABLED`（本地调试可关闭自动调度）

### 8.3 迁移路径

本地 `docker compose up` 验证 → 同 compose 部署云服务器 → 仅改 `.env`，代码无变更。

---

## 9. 测试策略

| 层级 | 覆盖 |
|------|------|
| Parser 单元测试 | RuleParser 固定样本；LLMParser mock 响应 |
| Storage 集成测试 | 版本 diff 与 field_changes |
| API 集成测试 | pytest + TestClient |
| Collector | 手动 trigger + 日志检查（不自动化，依赖外部站点） |

---

## 10. MVP 范围边界

### 10.1 包含

- 7 区数据源注册与 P0/P1 采集
- 规则 + LLM 混合解析
- 版本追踪与变更日志
- 查询 API + 3 页 Web
- 调度框架 + 手动触发
- Docker Compose 本地部署

### 10.2 不包含（后续迭代）

- 用户登录 / 付费层级
- LLM 低置信度审核 UI
- 公众号自动发现
- 学区地图可视化
- 学校对比、订阅通知
- 高中 / 幼儿园覆盖
- 成都都市圈扩展

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 政府网站反爬 / 结构频繁变更 | Playwright 模拟浏览器；RuleParser 异常标记 needs_rule_update |
| LLM 提取不准确 | confidence 标记 + 原文链接供用户核实；MVP 不自动发布低置信度变更 |
| 数据源 URL 失效 | job_runs 失败日志；sources 可禁用；不覆盖已有数据 |
| 招生季流量 / 更新频率高 | season_override 自动提速；手动 trigger 补充 |

---

## 12. 后续拆分方向

1. **chengdu-edu-collector** — 独立采集 worker（scheduler + collectors）
2. **chengdu-edu-api** — 纯 API 服务（供多个前端消费）
3. **chengdu-edu-parent-app** — 家长端完整产品（地图、对比、通知）
4. **chengdu-edu-research** — 研究者分析工具（趋势、对比、导出）

各子项目通过 API 和共享 schema 契约解耦，MVP 单体中的模块边界即拆分边界。
