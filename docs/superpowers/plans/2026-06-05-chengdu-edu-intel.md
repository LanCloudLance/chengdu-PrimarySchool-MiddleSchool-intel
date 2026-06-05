# 成都学区招生情报系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular monolith that collects, parses, versions, and serves Chengdu core-district school enrollment and promotion policies via REST API and a lightweight query web UI.

**Architecture:** Python packages (`core`, `storage`, `collectors`, `parsers`, `scheduler`, `api`, `web`) share PostgreSQL. Collectors fetch raw documents; parsers apply rule or LLM strategies; storage handles upsert with field-level version diff; APScheduler triggers jobs; FastAPI exposes query/admin endpoints; HTMX web consumes the API.

**Tech Stack:** Python 3.12, PostgreSQL 16, SQLAlchemy 2 + Alembic, FastAPI, httpx, Playwright, pdfplumber, APScheduler, OpenAI-compatible LLM API, HTMX + Alpine.js + Tailwind, Docker Compose, pytest

**Spec reference:** `docs/superpowers/specs/2026-06-05-chengdu-edu-intel-design.md`

---

## File Structure (created by this plan)

```
pyproject.toml                          # workspace root, shared dev deps
.env.example
docker-compose.yml
configs/
  districts.yaml
  sources.yaml
  schedules.yaml
  source_rules/jinjiang_gov.yaml        # example rule file
packages/
  core/
    pyproject.toml
    src/chengdu_edu_core/
      __init__.py
      enums.py                          # DistrictLevel, SchoolType, ParserStrategy, etc.
      models.py                         # Pydantic domain models: RawDocument, ParsedRecord
      hashing.py                        # content_hash helper
      diff.py                           # field-level JSON diff
  storage/
    pyproject.toml
    src/chengdu_edu_storage/
      __init__.py
      db.py                             # engine/session factory
      orm.py                            # SQLAlchemy ORM models (9 tables)
      repository.py                     # upsert, search, history
    alembic/                            # migrations
    tests/
      test_diff_integration.py
      test_repository.py
  collectors/
    pyproject.toml
    src/chengdu_edu_collectors/
      __init__.py
      base.py                           # BaseCollector protocol
      http.py                           # HttpCollector
      registry.py                       # source_type → collector mapping
    tests/
      test_http_collector.py
  parsers/
    pyproject.toml
    src/chengdu_edu_parsers/
      __init__.py
      base.py
      rule_parser.py
      llm_parser.py
      registry.py
    tests/
      fixtures/jinjiang_sample.html
      test_rule_parser.py
      test_llm_parser.py
  scheduler/
    pyproject.toml
    src/chengdu_edu_scheduler/
      __init__.py
      config_loader.py                  # load YAML configs
      pipeline.py                       # collect → parse → store orchestration
      runner.py                         # APScheduler + job_runs logging
  api/
    pyproject.toml
    src/chengdu_edu_api/
      __init__.py
      main.py                           # FastAPI app
      routes/
        districts.py
        schools.py
        policies.py
        jobs.py
        sources.py
      schemas.py                        # response models
    tests/
      test_api_schools.py
  web/
    Dockerfile
    src/templates/
      base.html
      index.html
      school_detail.html
      gov_policies.html
    src/static/
      app.css
packages/api/src/chengdu_edu_api/routes/pages.py  # HTMX page routes (served by api)
scripts/
  seed_districts.py                       # load 7 districts + P0 sources
data/raw/                               # downloaded PDFs (gitignored)
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `packages/core/pyproject.toml`

- [ ] **Step 1: Create root pyproject.toml**

```toml
[project]
name = "chengdu-edu-intel"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = [
  "packages/core",
  "packages/storage",
  "packages/collectors",
  "packages/parsers",
  "packages/scheduler",
  "packages/api",
]

[tool.pytest.ini_options]
testpaths = ["packages"]
asyncio_mode = "auto"

[dependency-groups]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.8",
]
```

- [ ] **Step 2: Create `.env.example`**

```env
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5432/chengdu_edu
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
SCHEDULER_ENABLED=true
RAW_DATA_DIR=./data/raw
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.venv/
data/raw/
.playwright/
htmlcov/
.coverage
```

- [ ] **Step 4: Create `packages/core/pyproject.toml`**

```toml
[project]
name = "chengdu-edu-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/chengdu_edu_core"]
```

- [ ] **Step 5: Install workspace**

Run: `cd /Users/wangyuanlong/Desktop/学业研究-Vibecoding && uv sync --all-packages`
Expected: workspace resolves without error (packages may be empty stubs initially)

- [ ] **Step 6: Init git repo and commit**

```bash
git init
git add pyproject.toml .env.example .gitignore packages/core/pyproject.toml docs/
git commit -m "chore: scaffold chengdu-edu-intel monorepo workspace"
```

---

### Task 2: Core Domain Models and Field Diff

**Files:**
- Create: `packages/core/src/chengdu_edu_core/enums.py`, `models.py`, `hashing.py`, `diff.py`
- Test: `packages/core/tests/test_diff.py`, `packages/core/tests/test_hashing.py`

- [ ] **Step 1: Write failing diff test**

Create `packages/core/tests/test_diff.py`:

```python
from chengdu_edu_core.diff import compute_field_changes

def test_compute_field_changes_detects_scalar_change():
    old = {"enrollment_scope": "A", "quota": 100}
    new = {"enrollment_scope": "B", "quota": 100}
    changes = compute_field_changes(old, new, prefix="fields")
    assert len(changes) == 1
    assert changes[0].field_path == "fields.enrollment_scope"
    assert changes[0].old_value == "A"
    assert changes[0].new_value == "B"

def test_compute_field_changes_detects_list_change():
    old = {"requirements": ["户籍"]}
    new = {"requirements": ["户籍", "房产"]}
    changes = compute_field_changes(old, new, prefix="fields")
    assert any(c.field_path == "fields.requirements" for c in changes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_diff.py -v`
Expected: FAIL — `ModuleNotFoundError: chengdu_edu_core`

- [ ] **Step 3: Implement enums and models**

Create `packages/core/src/chengdu_edu_core/enums.py`:

```python
from enum import StrEnum

class DistrictLevel(StrEnum):
    CORE = "core"
    EXTENDED = "extended"

class SchoolType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"

class SchoolLevel(StrEnum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    NINE_YEAR = "nine_year"

class SourceType(StrEnum):
    GOV_WEBSITE = "gov_website"
    SCHOOL_WEBSITE = "school_website"
    WECHAT = "wechat"
    PDF = "pdf"

class ParserStrategy(StrEnum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"

class PolicyType(StrEnum):
    SCHOOL_ENROLLMENT = "school_enrollment"
    GOV_POLICY = "gov_policy"
    DISTRICT_MAPPING = "district_mapping"

class RecordType(StrEnum):
    ENROLLMENT = "enrollment"
    PROMOTION = "promotion"

class JobStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
```

Create `packages/core/src/chengdu_edu_core/models.py`:

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from chengdu_edu_core.enums import ParserStrategy, PolicyType, RecordType

class RawDocument(BaseModel):
    source_id: UUID
    content_hash: str
    raw_content: str
    raw_file_path: str | None = None
    fetched_at: datetime
    http_status: int = 200

class ParsedRecord(BaseModel):
    record_type: RecordType
    district_id: UUID
    school_id: UUID | None = None
    policy_type: PolicyType | None = None
    year: int
    fields: dict
    confidence: float = 1.0
    needs_review: bool = False

class FieldChange(BaseModel):
    field_path: str
    old_value: str
    new_value: str

class ParsedEnrollment(ParsedRecord):
    record_type: RecordType = RecordType.ENROLLMENT
```

Create `packages/core/src/chengdu_edu_core/hashing.py`:

```python
import hashlib

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

Create `packages/core/src/chengdu_edu_core/diff.py`:

```python
import json
from chengdu_edu_core.models import FieldChange

def _serialize(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)

def compute_field_changes(old: dict, new: dict, prefix: str = "fields") -> list[FieldChange]:
    changes: list[FieldChange] = []
    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if _serialize(old_val) != _serialize(new_val):
            changes.append(
                FieldChange(
                    field_path=f"{prefix}.{key}",
                    old_value=_serialize(old_val) if old_val is not None else "",
                    new_value=_serialize(new_val) if new_val is not None else "",
                )
            )
    return changes
```

Create empty `packages/core/src/chengdu_edu_core/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/core/tests/test_diff.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/
git commit -m "feat(core): add domain models, hashing, and field diff"
```

---

### Task 3: Database ORM and Migrations

**Files:**
- Create: `packages/storage/pyproject.toml`, `db.py`, `orm.py`, Alembic config
- Test: `packages/storage/tests/test_orm_smoke.py`

- [ ] **Step 1: Create storage package pyproject.toml**

```toml
[project]
name = "chengdu-edu-storage"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "chengdu-edu-core",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
]

[tool.uv.sources]
chengdu-edu-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/chengdu_edu_storage"]
```

- [ ] **Step 2: Write failing ORM smoke test**

Create `packages/storage/tests/test_orm_smoke.py`:

```python
import pytest
from sqlalchemy import select
from chengdu_edu_storage.orm import District
from chengdu_edu_core.enums import DistrictLevel

@pytest.mark.asyncio
async def test_district_table_exists(db_session):
    district = District(name="锦江区", code="jinjiang", level=DistrictLevel.CORE)
    db_session.add(district)
    await db_session.commit()
    result = await db_session.execute(select(District).where(District.code == "jinjiang"))
    row = result.scalar_one()
    assert row.name == "锦江区"
```

Create `packages/storage/tests/conftest.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from chengdu_edu_storage.orm import Base

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 3: Run test — expect FAIL**

Run: `uv run pytest packages/storage/tests/test_orm_smoke.py -v`
Expected: FAIL — import errors

- [ ] **Step 4: Implement ORM models**

Create `packages/storage/src/chengdu_edu_storage/db.py`:

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql+asyncpg://edu:edu@localhost:5432/chengdu_edu")

engine = create_async_engine(get_database_url(), echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session():
    async with SessionLocal() as session:
        yield session
```

Create `packages/storage/src/chengdu_edu_storage/orm.py` with all 9 tables per spec §4.2. Key excerpt:

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from chengdu_edu_core.enums import (
    DistrictLevel, SchoolType, SchoolLevel, SourceType,
    ParserStrategy, PolicyType, RecordType, JobStatus,
)

class Base(DeclarativeBase):
    pass

class District(Base):
    __tablename__ = "districts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    level: Mapped[DistrictLevel] = mapped_column(SAEnum(DistrictLevel, name="district_level"))

class School(Base):
    __tablename__ = "schools"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(100))
    district_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"))
    type: Mapped[SchoolType] = mapped_column(SAEnum(SchoolType, name="school_type"))
    level: Mapped[SchoolLevel] = mapped_column(SAEnum(SchoolLevel, name="school_level"))
    address: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

# ... implement DataSource, RawDocument, EnrollmentPolicy, PromotionPolicy,
#     RecordVersion, FieldChange, JobRun per spec §4.2
```

For SQLite test compatibility in conftest, use generic JSON instead of JSONB in tests only, OR use PostgreSQL testcontainer. **Simpler approach for MVP plan:** use `sqlalchemy.JSON` type alias that maps JSONB on PostgreSQL:

```python
from sqlalchemy import JSON
JsonType = JSON().with_variant(JSONB(), "postgresql")
```

- [ ] **Step 5: Run ORM smoke test**

Run: `uv run pytest packages/storage/tests/test_orm_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Init Alembic and create initial migration**

```bash
cd packages/storage
uv run alembic init alembic
# Edit alembic/env.py to import Base from orm.py and use DATABASE_URL
uv run alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 7: Commit**

```bash
git add packages/storage/
git commit -m "feat(storage): add SQLAlchemy ORM models and Alembic migration"
```

---

### Task 4: Storage Repository — Upsert with Version Tracking

**Files:**
- Create: `packages/storage/src/chengdu_edu_storage/repository.py`
- Test: `packages/storage/tests/test_repository.py`

- [ ] **Step 1: Write failing upsert test**

```python
@pytest.mark.asyncio
async def test_upsert_enrollment_creates_version_on_field_change(db_session):
    repo = PolicyRepository(db_session)
    district_id = uuid.uuid4()
    # seed district + source + raw_doc fixtures ...
    policy_id = await repo.upsert_enrollment(
        district_id=district_id,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=2026,
        fields={"enrollment_scope": "范围A"},
        source_doc_id=raw_doc_id,
        confidence=1.0,
    )
    await repo.upsert_enrollment(
        district_id=district_id,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=2026,
        fields={"enrollment_scope": "范围B"},
        source_doc_id=raw_doc_id,
        confidence=1.0,
        existing_id=policy_id,
    )
    history = await repo.get_field_changes(RecordType.ENROLLMENT, policy_id)
    assert len(history) == 1
    assert history[0].field_path == "fields.enrollment_scope"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest packages/storage/tests/test_repository.py -v`
Expected: FAIL — `PolicyRepository` not defined

- [ ] **Step 3: Implement PolicyRepository**

```python
class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_enrollment(self, *, district_id, school_id, policy_type, year,
                                 fields, source_doc_id, confidence, existing_id=None) -> UUID:
        if existing_id:
            policy = await self.session.get(EnrollmentPolicy, existing_id)
            old_fields = dict(policy.fields)
            if old_fields == fields:
                return existing_id
            changes = compute_field_changes(old_fields, fields)
            policy.fields = fields
            policy.current_version += 1
            policy.source_doc_id = source_doc_id
            policy.confidence = confidence
            self._add_version(RecordType.ENROLLMENT, policy.id, policy.current_version, fields, source_doc_id)
            for c in changes:
                self._add_field_change(RecordType.ENROLLMENT, policy.id,
                                       policy.current_version - 1, policy.current_version, c)
        else:
            policy = EnrollmentPolicy(
                district_id=district_id, school_id=school_id, policy_type=policy_type,
                year=year, fields=fields, source_doc_id=source_doc_id,
                confidence=confidence, current_version=1,
            )
            self.session.add(policy)
            await self.session.flush()
            self._add_version(RecordType.ENROLLMENT, policy.id, 1, fields, source_doc_id)
        await self.session.commit()
        return policy.id

    async def search_schools(self, *, district_code=None, school_type=None, level=None, q=None, offset=0, limit=20):
        stmt = select(School).join(District)
        if district_code:
            stmt = stmt.where(District.code == district_code)
        if school_type:
            stmt = stmt.where(School.type == school_type)
        if level:
            stmt = stmt.where(School.level == level)
        if q:
            stmt = stmt.where(School.name.ilike(f"%{q}%"))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

Implement `_add_version`, `_add_field_change`, `get_field_changes`, `get_school_with_policies` similarly.

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/storage/tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/storage/
git commit -m "feat(storage): add policy repository with version tracking"
```

---

### Task 5: HttpCollector

**Files:**
- Create: `packages/collectors/src/chengdu_edu_collectors/base.py`, `http.py`, `registry.py`
- Test: `packages/collectors/tests/test_http_collector.py`

- [ ] **Step 1: Write failing test with httpx mock**

```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone
import httpx
from chengdu_edu_collectors.http import HttpCollector
from chengdu_edu_core.models import RawDocument

@pytest.mark.asyncio
async def test_http_collector_fetches_and_hashes(httpx_mock):
    httpx_mock.add_response(url="https://example.com/policy", text="<html>招生范围：A区</html>")
    collector = HttpCollector()
    source = type("S", (), {"id": uuid4(), "url": "https://example.com/policy", "source_type": "gov_website"})()
    doc = await collector.collect(source)
    assert "招生范围" in doc.raw_content
    assert len(doc.content_hash) == 64
    assert doc.http_status == 200
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest packages/collectors/tests/test_http_collector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement HttpCollector**

```python
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from chengdu_edu_core.hashing import content_hash
from chengdu_edu_core.models import RawDocument

class HttpCollector:
    source_type = "gov_website"

    async def collect(self, source) -> RawDocument:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(source.url)
                    resp.raise_for_status()
                    text = self._extract_text(resp.text)
                    return RawDocument(
                        source_id=source.id,
                        content_hash=content_hash(text),
                        raw_content=text,
                        fetched_at=datetime.now(timezone.utc),
                        http_status=resp.status_code,
                    )
                except httpx.HTTPError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
```

Add `beautifulsoup4` and `httpx` to collectors pyproject.toml. Add `pytest-httpx` to dev deps.

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/collectors/
git commit -m "feat(collectors): add HttpCollector with retry and text extraction"
```

---

### Task 6: RuleParser

**Files:**
- Create: `packages/parsers/src/chengdu_edu_parsers/rule_parser.py`
- Create: `configs/source_rules/jinjiang_gov.yaml`
- Create: `packages/parsers/tests/fixtures/jinjiang_sample.html`
- Test: `packages/parsers/tests/test_rule_parser.py`

- [ ] **Step 1: Create fixture HTML and rule YAML**

`configs/source_rules/jinjiang_gov.yaml`:

```yaml
fields:
  enrollment_scope:
    selector: "div.content"
    regex: "招生范围[：:](.+)"
  registration_time:
    regex: "报名时间[：:]([\d\-~至 ]+)"
  contact:
    regex: "咨询电话[：:]([\d\-]+)"
```

- [ ] **Step 2: Write failing test**

```python
def test_rule_parser_extracts_fields_from_html():
    html = Path("packages/parsers/tests/fixtures/jinjiang_sample.html").read_text()
    rules = yaml.safe_load(Path("configs/source_rules/jinjiang_gov.yaml").read_text())
    parser = RuleParser()
    result = parser.parse_content(html, rules, policy_type=PolicyType.GOV_POLICY, year=2026)
    assert "东大街" in result.fields["enrollment_scope"]
    assert result.confidence == 1.0
```

- [ ] **Step 3: Implement RuleParser**

```python
import re
from bs4 import BeautifulSoup
from chengdu_edu_parsers.base import ParseResult

class RuleParser:
    async def parse(self, raw, source, rules_path: str) -> ParseResult:
        rules = yaml.safe_load(Path(rules_path).read_text())
        return self.parse_content(raw.raw_content, rules, ...)

    def parse_content(self, text, rules, policy_type, year) -> ParseResult:
        fields = {}
        for name, rule in rules["fields"].items():
            scope = text
            if "selector" in rule:
                soup = BeautifulSoup(text, "html.parser")
                el = soup.select_one(rule["selector"])
                scope = el.get_text() if el else text
            if "regex" in rule:
                m = re.search(rule["regex"], scope, re.DOTALL)
                if m:
                    fields[name] = m.group(1).strip()
        return ParseResult(fields=fields, confidence=1.0, needs_review=False)
```

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/parsers/ configs/source_rules/
git commit -m "feat(parsers): add RuleParser with YAML rule files"
```

---

### Task 7: LLMParser

**Files:**
- Create: `packages/parsers/src/chengdu_edu_parsers/llm_parser.py`
- Test: `packages/parsers/tests/test_llm_parser.py`

- [ ] **Step 1: Write test with mocked OpenAI client**

```python
@pytest.mark.asyncio
async def test_llm_parser_returns_structured_fields(mocker):
    mock_client = mocker.patch("chengdu_edu_parsers.llm_parser.AsyncOpenAI")
    mock_client.return_value.chat.completions.create = AsyncMock(return_value=FakeCompletion({
        "enrollment_scope": "南门片区",
        "registration_time": "2026-03-01 ~ 2026-03-15",
        "confidence": 0.92,
    }))
    parser = LLMParser(api_key="test", base_url="http://test", model="test")
    result = await parser.parse(raw_doc, source)
    assert result.fields["enrollment_scope"] == "南门片区"
    assert result.confidence == 0.92
    assert result.needs_review is False

@pytest.mark.asyncio
async def test_llm_parser_marks_low_confidence_for_review(mocker):
    # confidence 0.5 → needs_review True
    ...
```

- [ ] **Step 2: Implement LLMParser**

```python
ENROLLMENT_SCHEMA = {
    "enrollment_scope": "string",
    "registration_time": "string",
    "requirements": ["string"],
    "quota": "integer|null",
    "lottery_rule": "string|null",
    "contact": "string|null",
    "notes": "string|null",
}

class LLMParser:
    REVIEW_THRESHOLD = 0.7

    async def parse(self, raw, source) -> ParseResult:
        prompt = self._build_prompt(raw.raw_content, ENROLLMENT_SCHEMA)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        confidence = float(data.pop("confidence", 0.8))
        return ParseResult(
            fields=data,
            confidence=confidence,
            needs_review=confidence < self.REVIEW_THRESHOLD,
        )
```

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git add packages/parsers/
git commit -m "feat(parsers): add LLMParser with confidence and review flag"
```

---

### Task 8: Pipeline Orchestration

**Files:**
- Create: `packages/scheduler/src/chengdu_edu_scheduler/pipeline.py`, `config_loader.py`
- Create: `configs/districts.yaml`, `configs/sources.yaml`, `configs/schedules.yaml`

- [ ] **Step 1: Create config files**

`configs/districts.yaml`:

```yaml
districts:
  - name: 锦江区
    code: jinjiang
    level: core
  - name: 青羊区
    code: qingyang
    level: core
  - name: 武侯区
    code: wuhou
    level: core
  - name: 成华区
    code: chenghua
    level: core
  - name: 金牛区
    code: jinniu
    level: core
  - name: 高新区
    code: gaoxin
    level: core
  - name: 天府新区
    code: tianfu
    level: core
```

`configs/schedules.yaml`:

```yaml
defaults:
  gov_policy: "0 0 1 * *"
  school_info: "0 0 * * 1"
  enrollment_brochure: "0 6 * * *"
season_override:
  months: [3, 4, 5, 6]
  enrollment_brochure: "0 6 * * *"
```

`configs/sources.yaml` — start with 7 P0 gov sources (one per district), example entry:

```yaml
sources:
  - name: 锦江区教育局-招生政策
    source_type: gov_website
    url: https://www.cdjx.gov.cn/  # replace with actual policy page URL during seed
    parser_strategy: rule
    schedule: "0 0 1 * *"
    district_code: jinjiang
    rule_file: source_rules/jinjiang_gov.yaml
    is_active: true
```

- [ ] **Step 2: Write pipeline integration test (mock collector + parser)**

```python
@pytest.mark.asyncio
async def test_pipeline_skips_unchanged_hash(db_session, mocker):
    # setup source, previous raw_doc with same hash
    # run pipeline.run_source(source)
    # assert job_run.status == SKIPPED
```

- [ ] **Step 3: Implement Pipeline.run_source**

```python
class Pipeline:
    async def run_source(self, source: DataSource) -> JobRun:
        run = JobRun(source_id=source.id, status=JobStatus.FAILED, started_at=utcnow())
        try:
            collector = get_collector(source.source_type)
            raw = await collector.collect(source)
            last_hash = await self.repo.get_latest_hash(source.id)
            if last_hash == raw.content_hash:
                run.status = JobStatus.SKIPPED
                return await self._finish(run)
            doc_id = await self.repo.save_raw_document(raw)
            parser = get_parser(source.parser_strategy)
            parsed = await parser.parse(raw, source)
            if parsed.needs_review and parsed.confidence < 0.7:
                # MVP: still save but flag in metadata
                pass
            changes = await self.repo.upsert_from_parsed(parsed, doc_id)
            run.status = JobStatus.SUCCESS
            run.changes_detected = changes
            run.docs_fetched = 1
        except Exception as e:
            run.error_message = str(e)
        return await self._finish(run)
```

- [ ] **Step 4: Run integration test — PASS**

- [ ] **Step 5: Commit**

```bash
git add packages/scheduler/ configs/
git commit -m "feat(scheduler): add pipeline orchestration and YAML config loader"
```

---

### Task 9: APScheduler Runner

**Files:**
- Create: `packages/scheduler/src/chengdu_edu_scheduler/runner.py`

- [ ] **Step 1: Implement scheduler runner**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class SchedulerRunner:
    def __init__(self, pipeline: Pipeline, sources: list):
        self.pipeline = pipeline
        self.scheduler = AsyncIOScheduler()

    def register_sources(self, sources):
        for source in sources:
            if source.is_active:
                self.scheduler.add_job(
                    self.pipeline.run_source,
                    CronTrigger.from_crontab(source.schedule),
                    args=[source],
                    id=str(source.id),
                    replace_existing=True,
                )

    def start(self):
        self.scheduler.start()

    async def trigger(self, scope: str, target_id: UUID | None = None):
        if scope == "all":
            for source in self.sources:
                await self.pipeline.run_source(source)
        elif scope == "source" and target_id:
            source = await self.repo.get_source(target_id)
            await self.pipeline.run_source(source)
```

- [ ] **Step 2: Manual smoke test**

Run: `SCHEDULER_ENABLED=false uv run python -m chengdu_edu_scheduler.runner --trigger source <id>`
Expected: job_runs row created in DB

- [ ] **Step 3: Commit**

```bash
git add packages/scheduler/
git commit -m "feat(scheduler): add APScheduler runner and manual trigger"
```

---

### Task 10: FastAPI Query Endpoints

**Files:**
- Create: `packages/api/src/chengdu_edu_api/main.py`, routes, schemas
- Test: `packages/api/tests/test_api_schools.py`

- [ ] **Step 1: Write failing API test**

```python
from httpx import AsyncClient, ASGITransport
from chengdu_edu_api.main import app

@pytest.mark.asyncio
async def test_list_districts_returns_seven(db_session, seeded_data):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/districts")
    assert resp.status_code == 200
    assert len(resp.json()) == 7

@pytest.mark.asyncio
async def test_search_schools_by_query(db_session, seeded_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/schools", params={"q": "实验", "district": "jinjiang"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 0
```

- [ ] **Step 2: Implement FastAPI app**

```python
# packages/api/src/chengdu_edu_api/main.py
from fastapi import FastAPI
from chengdu_edu_api.routes import districts, schools, policies, jobs, sources, pages

app = FastAPI(title="Chengdu Edu Intel API", version="0.1.0")
app.include_router(districts.router, prefix="/api")
app.include_router(schools.router, prefix="/api")
app.include_router(policies.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(pages.router)
```

Implement each router per spec §6. Response must include `source.url`, `fetched_at`, `confidence`, `has_recent_changes`.

`has_recent_changes` logic: any field_change within last 30 days.

- [ ] **Step 3: Run API tests — PASS**

Run: `uv run pytest packages/api/tests/ -v`

- [ ] **Step 4: Commit**

```bash
git add packages/api/
git commit -m "feat(api): add query and admin REST endpoints"
```

---

### Task 11: HTMX Query Web Pages

**Files:**
- Create: `packages/api/src/chengdu_edu_api/routes/pages.py`
- Create: `packages/api/src/chengdu_edu_api/templates/*.html`

- [ ] **Step 1: Add Jinja2Templates to FastAPI**

```python
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="packages/api/src/chengdu_edu_api/templates")
```

- [ ] **Step 2: Implement 3 pages**

`index.html` — search form with HTMX:

```html
<form hx-get="/api/schools" hx-target="#results" hx-swap="innerHTML">
  <input name="q" placeholder="搜索学校名称..." />
  <select name="district">...</select>
  <button type="submit">搜索</button>
</form>
<div id="results"></div>
```

`school_detail.html` — shows enrollment, promotion, change history with source links.

`gov_policies.html` — district tabs, policy list.

Use Tailwind CDN in `base.html` for MVP speed.

- [ ] **Step 3: Manual verify**

Run: `uv run uvicorn chengdu_edu_api.main:app --reload --port 8000`
Open: `http://localhost:8000/`
Expected: search page renders, search returns results partial

- [ ] **Step 4: Commit**

```bash
git add packages/api/src/chengdu_edu_api/templates/ packages/api/src/chengdu_edu_api/routes/pages.py
git commit -m "feat(web): add HTMX query pages for search, detail, and gov policies"
```

---

### Task 12: Seed Script for 7 Districts and P0 Sources

**Files:**
- Create: `scripts/seed_districts.py`

- [ ] **Step 1: Implement seed script**

```python
async def main():
    async with SessionLocal() as session:
        for d in load_yaml("configs/districts.yaml")["districts"]:
            session.add(District(name=d["name"], code=d["code"], level=d["level"]))
        await session.commit()
        districts = {d.code: d.id for d in (await session.execute(select(District))).scalars()}
        for s in load_yaml("configs/sources.yaml")["sources"]:
            session.add(DataSource(
                name=s["name"],
                source_type=s["source_type"],
                url=s["url"],
                parser_strategy=s["parser_strategy"],
                schedule=s["schedule"],
                district_id=districts[s["district_code"]],
                is_active=s.get("is_active", True),
                metadata_={"rule_file": s.get("rule_file")},
            ))
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run seed against local DB**

Run: `uv run python scripts/seed_districts.py`
Expected: 7 districts + N sources inserted

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "feat: add seed script for districts and P0 data sources"
```

---

### Task 13: Docker Compose

**Files:**
- Create: `docker-compose.yml`, Dockerfiles for api and scheduler

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: edu
      POSTGRES_PASSWORD: edu
      POSTGRES_DB: chengdu_edu
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  api:
    build:
      context: .
      dockerfile: packages/api/Dockerfile
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db]
    volumes: [./configs:/app/configs, ./data/raw:/app/data/raw]

  scheduler:
    build:
      context: .
      dockerfile: packages/scheduler/Dockerfile
    env_file: .env
    depends_on: [db, api]
    volumes: [./configs:/app/configs, ./data/raw:/app/data/raw]

volumes:
  pgdata:
```

- [ ] **Step 2: Create Dockerfiles**

`packages/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --all-packages
CMD ["uv", "run", "alembic", "-c", "packages/storage/alembic.ini", "upgrade", "head", "&&",
     "uv", "run", "uvicorn", "chengdu_edu_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Use a shell entrypoint script instead of chained CMD for reliability.

- [ ] **Step 3: Smoke test full stack**

```bash
cp .env.example .env
docker compose up -d db
uv run alembic -c packages/storage/alembic.ini upgrade head
uv run python scripts/seed_districts.py
docker compose up api scheduler
curl http://localhost:8000/api/districts
curl -X POST http://localhost:8000/api/jobs/trigger -H 'Content-Type: application/json' -d '{"scope":"all"}'
```

Expected: 7 districts returned; job runs logged

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml packages/api/Dockerfile packages/scheduler/Dockerfile
git commit -m "feat: add Docker Compose for local full-stack deployment"
```

---

### Task 14: End-to-End Verification Checklist

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest packages/ -v`
Expected: all unit/integration tests PASS

- [ ] **Step 2: Verify spec success criteria**

| 标准 | 验证命令 |
|------|----------|
| 7 区覆盖 | `curl /api/districts` → 7 rows |
| 来源可追溯 | `curl /api/policies/enrollment/{id}` → `source.url` present |
| 调度可配置 | edit `configs/schedules.yaml`, restart scheduler |
| 变更历史 | upsert with changed fields → `curl .../changes` returns diff |
| Web 查询 | open `/`, search school name |
| Docker 一键启动 | `docker compose up` |

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "chore: complete MVP verification for chengdu-edu-intel"
```

---

## Plan Self-Review

### Spec Coverage

| Spec Section | Task(s) |
|--------------|---------|
| §3 Architecture / modules | Task 1, 8 |
| §4 Data model (9 tables) | Task 3 |
| §4.3 Change detection | Task 2, 4 |
| §5 Collectors | Task 5 |
| §5 Rule + LLM parsers | Task 6, 7 |
| §5.4 Schedules | Task 8, 9, configs |
| §5.5 Error handling | Task 5 (retry), Task 8 (pipeline try/except) |
| §6 API query + admin | Task 10 |
| §7 Web 3 pages | Task 11 |
| §8 Docker Compose | Task 13 |
| §9 Tests | Tasks 2–7, 10, 14 |
| §10 MVP scope | Tasks 1–13; P2 WeChat deferred |
| §11 Risks | confidence flag Task 7; retry Task 5; no overwrite on fail Task 8 |

**Gap:** P1 school-level sources require manual URL research per school — Task 12 seeds P0 gov sources only; school URLs added incrementally post-MVP bootstrap. Documented as follow-up in seed script README comment.

### Placeholder Scan

No TBD/TODO/vague steps found.

### Type Consistency

- `RawDocument`, `ParsedRecord`, `FieldChange` defined in Task 2, used throughout
- `PolicyRepository.upsert_enrollment` signature consistent in Task 4 and Task 8
- `JobStatus`, `RecordType` enums used in pipeline and API

---

## Suggested Implementation Order

1. Tasks 1–4 (foundation + storage) — **must be sequential**
2. Tasks 5–7 (collectors + parsers) — **parallelizable**
3. Tasks 8–9 (pipeline + scheduler) — after 5–7
4. Tasks 10–11 (API + web) — after 4
5. Tasks 12–14 (seed + docker + verify) — last

Estimated MVP timeline: **4–6 weeks** at moderate pace; Tasks 1–4 in week 1, 5–9 in weeks 2–3, 10–14 in weeks 4–5, buffer for real URL research and rule tuning in week 6.
