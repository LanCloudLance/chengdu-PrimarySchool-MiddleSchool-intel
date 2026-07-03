# Checkpoint Execution Plan - 2026-06-24

## Purpose

This document defines the immediate execution plan after the Codex mini-loop PASS on 2026-06-23.

Goal:

- Freeze the current MVP baseline cleanly.
- Avoid mixing data, tooling, UI, and process artifacts into one unreadable commit.
- Preserve the current verified state before starting manual OCR review or official-source replacement.

## Current State

Status: checkpoint ready.

Verified baseline:

```bash
.venv/bin/python scripts/verify_district_parity.py --year 2026
# ALL DISTRICTS PARITY PASS

.venv/bin/pytest packages/storage/tests packages/api/tests -q
# 34 passed

.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
# ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
# ALL DISTRICTS PARITY PASS
```

Browser QA:

- Home page loads.
- Default year is 2026.
- School dropdown is grouped by 7 districts.
- Search result links preserve `?year=2026`.
- School detail shows the selected year and mapping status.
- 金牛 2026 pending-review queue shows 46 rows.
- Review page is read-only by default.
- Console errors: none.

## Commit Group 1: Data Baseline

Purpose:

- Freeze 2025/2026 district data files and inventory state.

Include:

- `configs/districts/*/mapping_scraped_2026.json`
- `configs/districts/*/mapping_official_2025.json`
- `configs/district_2026_changes.json`
- `configs/districts/*/schools.yaml`
- `configs/schools.yaml`
- data reports under `docs/`, including OCR and 2025/2026 diff reports

Do not include:

- API route/template changes
- import script changes
- review workflow code

Acceptance:

```bash
.venv/bin/python scripts/verify_district_parity.py --year 2026
```

Must pass all 7 districts.

Notes:

- 2026 data is not fully official.
- OCR/reference/pending rows must remain visibly labeled.
- Do not promote OCR-derived rows to `verified` in this commit.

## Commit Group 2: Import And Verification Tooling

Purpose:

- Make year-specific import, review CSV import, and parity validation reproducible.

Include:

- `scripts/import_district_mapping_policies.py`
- `scripts/import_mapping_review_decisions.py`
- `scripts/diff_mapping_years.py`
- `scripts/verify_district_parity.py`
- `packages/storage/tests/test_import_district_mapping_policies.py`
- `packages/storage/tests/test_import_mapping_review_decisions.py`
- `packages/storage/tests/test_verify_district_parity.py`

Acceptance:

```bash
.venv/bin/pytest packages/storage/tests -q
.venv/bin/python scripts/verify_district_parity.py --year 2026
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
```

Must pass.

Key behaviors to preserve:

- `--year 2026` must read `mapping_scraped_2026.json`.
- Explicit 2026 import must not be overwritten by stale `intel_entries`.
- `ocr_image_needs_review` imports as `pending_review`.
- Tianfu 2026 reform placeholders remain `pending_official`.
- Unknown mapping statuses fail parity.

## Commit Group 3: Frontend/API Year Switching And Review UI

Purpose:

- Freeze the MVP customer-facing experience.

Include:

- `packages/api/src/chengdu_edu_api/enrichment.py`
- `packages/api/src/chengdu_edu_api/mapping_display.py`
- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/routes/schools.py`
- `packages/api/src/chengdu_edu_api/templates/base.html`
- `packages/api/src/chengdu_edu_api/templates/index.html`
- `packages/api/src/chengdu_edu_api/templates/school_detail.html`
- `packages/api/src/chengdu_edu_api/templates/school_results.html`
- `packages/api/src/chengdu_edu_api/templates/mapping_review.html`
- `packages/api/tests/test_api_schools.py`
- `packages/api/tests/test_mapping_year_switch.py`
- `packages/api/tests/test_mapping_review_page.py`

Acceptance:

```bash
.venv/bin/pytest packages/api/tests -q
```

Manual browser checks:

- Open `http://127.0.0.1:8000/`.
- Confirm default year is 2026.
- Search `四川天府新区元音小学`.
- Confirm result link includes `?year=2026`.
- Confirm detail page shows `待官方` and `2026 年框架`.
- Open `/review/mappings?year=2026&district=jinniu&status=pending_review`.
- Confirm the page shows 46 records and read-only mode.

Review write safety:

- Default mode must hide save forms.
- POST to review decision must return 403 unless `ENABLE_REVIEW_WRITE=true`.
- If `REVIEW_WRITE_TOKEN` is set, wrong token must return 403.

## Commit Group 4: Process And Handoff Artifacts

Purpose:

- Preserve the Cursor/Codex operating loop, review notes, and checkpoint state.

Include:

- `.openprd/`
- `.codex/` if project-local and intentional
- `AGENTS.md`
- `CODEX_REVIEW_README.md`
- `docs/codex-checkpoint-2026-06-18.md`
- `docs/codex-mini-loop-status-2026-06-23.md`
- `docs/checkpoint-execution-plan-2026-06-24.md`

Acceptance:

- No code behavior expected from this commit.
- Confirm documents do not contain secrets, tokens, or personal credentials.

## Files Requiring Extra Review Before Commit

These files should not be buried in the wrong group:

- `docker-compose.yml`
- `packages/parsers/src/chengdu_edu_parsers/mapping_ocr.py`
- `scripts/import_schools.py`
- `packages/storage/tests/test_import_schools.py`

Suggested handling:

- If they support the verified checkpoint, place them in the closest matching group.
- If intent is unclear, create a separate small commit named `chore: align runtime and school import support`.

## Manual Review Batch Plan

After checkpoint commits are created:

1. Open:

   ```text
   http://127.0.0.1:8000/review/mappings?year=2026&district=jinniu&status=pending_review
   ```

2. Pick 5-10 rows only.
3. Compare each row against source image or official page.
4. Keep decisions conservative:
   - clear official match -> `verified`
   - credible non-official source -> `reference`
   - OCR unclear -> keep `pending_review`
   - missing official context -> `pending_official`

5. Enable write mode only during the actual review session:

   ```bash
   ENABLE_REVIEW_WRITE=true REVIEW_WRITE_TOKEN=<token> \
     DATABASE_URL=postgresql+asyncpg://edu:edu@127.0.0.1:5432/chengdu_edu \
     .venv/bin/python -m uvicorn chengdu_edu_api.main:app --host 127.0.0.1 --port 8000
   ```

6. After saving, rerun:

   ```bash
   .venv/bin/python scripts/verify_district_parity.py --year 2026 --db
   ```

Expected result:

- PASS remains PASS.
- Reviewed rows have audit entries in `record_versions` and `field_changes`.

## Definition Of Done

Checkpoint is complete when:

- All four commit groups are created or explicitly collapsed with a written reason.
- File parity, DB parity, and tests pass.
- Browser smoke test passes.
- 2026 OCR/reference/pending status labels remain visible.
- No one claims the 2026 dataset is fully official or fully verified.

## Next Product Decision

Before public-facing use, decide one of:

- Keep the product as an internal intelligence/review tool.
- Wait for official 2026 source replacement before broader demo.
- Launch read-only demo with prominent `仅供参考，以官方为准` disclaimer and visible status badges.

