# Codex Checkpoint - 2026-06-18

## Status

This checkpoint freezes the current MVP state after Phase 3B/3C/3D work:

- 2025 and 2026 district parity checks pass against the local DB.
- Search, school detail, mapping review queue, CSV review round-trip, and in-browser review capture are implemented.
- In-browser review writes are protected by `ENABLE_REVIEW_WRITE`; the default runtime is read-only.
- Browser QA has covered the core search/detail/review flows.

## Verification

```bash
.venv/bin/pytest packages/storage/tests packages/api/tests -q
# 34 passed

.venv/bin/python scripts/verify_district_parity.py --year 2026
# ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
# ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
# ALL DISTRICTS PARITY PASS
```

Browser QA summary:

- Home page loads with year/school/search controls.
- Searching for `四川天府新区元音小学` returns one result.
- Search result detail links preserve `?year=2026`.
- School detail page opens with the selected year, mapping section, status badge text, and year-preserving back link.
- Review queue `year=2026&district=jinniu&status=pending_review` shows 46 records, CSV export, read-only notice, and no save buttons.
- Jinniu 2025 and 2026 search pages both show 63 schools and preserve year-specific detail links.
- Browser console had no errors during the QA path.

## Feature Boundary

### Data / Import

- 7 districts have `mapping_scraped_2026.json`.
- 7 districts have `mapping_official_2025.json`.
- `scripts/import_district_mapping_policies.py` supports explicit `--year` import and prevents 2026 imports from being overwritten by stale intel rows.
- OCR rows are imported as `pending_review`.
- Tianfu 2026 reform placeholders remain `pending_official`.

### Validation

- `scripts/verify_district_parity.py` supports `--year`.
- 2025 remains strict.
- 2026 uses status-aware validation:
  - `verified`
  - `reference`
  - `pending_review`
  - `pending_official`
  - unknown statuses fail.

### Frontend / API

- Home page has a mapping year selector.
- School search and scope search respect selected year.
- School result links preserve selected year.
- School detail filters mapping/enrollment/promotion display by selected year.
- `/api/schools?year=...` filters mapping summaries and scope search by year.
- Blank select values (`type=`, `level=`) no longer cause 422.

### Review Workflow

- `/review/mappings` lists mapping rows by year, district, and status.
- `pending_review` has a first-class badge.
- `/review/mappings.csv` exports review rows with `review_decision` and `review_notes`.
- `scripts/import_mapping_review_decisions.py` imports reviewed CSV rows with dry-run and stale-status protection.
- In-browser review capture can write updates, audit versions, and field changes.
- In-browser write is disabled unless `ENABLE_REVIEW_WRITE=true`.
- Optional `REVIEW_WRITE_TOKEN` protects write forms.

## Suggested Commit Groups

### Commit 1: Data Parity And 2026 Sources

Include:

- `configs/districts/*/mapping_scraped_2026.json`
- `configs/districts/*/mapping_official_2025.json`
- `configs/district_2026_changes.json`
- district inventory updates under `configs/districts/*/schools.yaml`
- `configs/schools.yaml`
- data docs such as OCR and 2025/2026 diff reports

Purpose:

- Freeze the 2025/2026 source-data baseline.

Risk:

- This is a large data commit. Review separately from application code.

### Commit 2: Import And Verification Tooling

Include:

- `scripts/import_district_mapping_policies.py`
- `scripts/import_mapping_review_decisions.py`
- `scripts/diff_mapping_years.py`
- `scripts/verify_district_parity.py`
- storage tests for import and parity scripts

Purpose:

- Make year-specific import, review import, and parity verification reproducible.

### Commit 3: Frontend/API Year Switching And Review UI

Include:

- `packages/api/src/chengdu_edu_api/enrichment.py`
- `packages/api/src/chengdu_edu_api/mapping_display.py`
- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/routes/schools.py`
- `packages/api/src/chengdu_edu_api/templates/*`
- API tests for search, year switching, and mapping review

Purpose:

- Freeze the user-facing MVP experience.

### Commit 4: Project Process Artifacts

Include:

- `.openprd/`
- `AGENTS.md`
- `CODEX_REVIEW_README.md`
- `docs/codex-checkpoint-2026-06-18.md`

Purpose:

- Preserve the Cursor/Codex operating loop and checkpoint documentation.

## Do Not Mix Without Review

These files appear in the dirty tree but should be reviewed carefully before grouping:

- `docker-compose.yml`
- `packages/parsers/src/chengdu_edu_parsers/mapping_ocr.py`
- `scripts/import_schools.py`
- `packages/storage/tests/test_import_schools.py`

Reason:

- They may belong to earlier Cursor work or support changes. Do not bury them inside the frontend/review checkpoint without confirming intent.

## Current Known Risks

### P0

- None after write protection, assuming the service is run with default read-only review mode.

### P1

- OCR-derived rows still need human review before being promoted to `verified`.
- Tianfu 2026 remains `pending_official` because the reform changes the mapping unit.
- Official 2026 source replacement is still the main data-quality path.

### P2

- High-school data, admission numbers, score lines, and quota-to-school data need a separate schema design. Do not continue stuffing these into generic JSONB fields as the primary model.
- The UI is functionally validated but not polished for dense repeated review work.

## Next Recommended Work

1. Create a clean checkpoint boundary using the commit groups above.
2. Run a small manual review batch:
   - Start with 5-10 Jinniu `pending_review` rows.
   - Use read-only page first.
   - Enable write only when ready:
     ```bash
     ENABLE_REVIEW_WRITE=true REVIEW_WRITE_TOKEN=<token> \
       .venv/bin/python -m uvicorn chengdu_edu_api.main:app --host 127.0.0.1 --port 8000
     ```
   - Confirm status changes, audit rows, and school-detail badges.
3. Replace OCR/reference rows district by district with official 2026 sources.
4. Design the next schema expansion for high-school and enrollment-plan data after the primary/middle mapping MVP is stable.

