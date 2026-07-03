# Cursor Result: Phase 3B DB Verification Fixed By Codex

Status: COMPLETE

## Files Changed

- `scripts/verify_district_parity.py`
- `scripts/import_district_mapping_policies.py`
- `packages/storage/tests/test_verify_district_parity.py`
- `packages/storage/tests/test_import_district_mapping_policies.py`

## What Was Done

- Added 2026-specific DB validation rules with explicit mapping status accounting.
- Added DB status counts for `verified`, `reference`, `pending_review`, `pending_official`, and unknown statuses.
- Kept 2025 strict `mapped/total >= 90%` behavior.
- Allowed 2026 OCR rows to remain `pending_review` without being treated as failed mapped coverage.
- Allowed Tianfu 2026 all-`pending_official` as a transitional reform state, while exposing it clearly in output.
- Fixed import script behavior so explicitly requested years use scraped files instead of stale `intel_entries`.
- Made `--year 2026` fail loudly if `mapping_scraped_2026.json` is missing.
- Re-imported Gaoxin 2025 mapping into the local test DB after discovering it had regressed to `5/41`.

## 2026 Verification Rule Explanation

- 2026 is not judged by the 2025 single `mapped/total >= 90%` rule.
- `pending_review` is accepted as imported OCR data needing human review.
- `pending_official` is accepted for Tianfu because the 2026 school-district reform changes the mapping unit.
- Non-Tianfu districts still fail if `pending_official` exceeds 40% of district mapping rows.
- Unknown mapping statuses fail immediately.

## 2026 District Status Breakdown

```text
jinjiang: status(v=24 ref=0 review=0 pending=3 unknown=0)
qingyang: status(v=31 ref=0 review=0 pending=4 unknown=0)
wuhou: status(v=0 ref=9 review=29 pending=23 unknown=0)
chenghua: status(v=36 ref=0 review=0 pending=2 unknown=0)
jinniu: status(v=0 ref=0 review=46 pending=17 unknown=0)
gaoxin: status(v=0 ref=5 review=30 pending=6 unknown=0)
tianfu: status(v=0 ref=0 review=0 pending=38 unknown=0)
```

## Verification

```text
.venv/bin/python scripts/verify_district_parity.py --year 2026
=== verify_district_parity (year=2026) ===
jinjiang: PASS
qingyang: PASS
wuhou: PASS
chenghua: PASS
jinniu: PASS
gaoxin: PASS
tianfu: PASS
ALL DISTRICTS PARITY PASS
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
=== verify_district_parity (year=2026) ===
jinjiang: PASS | schools(file=28/db=28) scopes(file=35/mapped=24/27) enroll=28 status(v=24 ref=0 review=0 pending=3 unknown=0) intel_map=1 intel_mirror=0 gov=1
qingyang: PASS | schools(file=36/db=36) scopes(file=37/mapped=31/35) enroll=36 status(v=31 ref=0 review=0 pending=4 unknown=0) intel_map=1 intel_mirror=0 gov=1
wuhou: PASS | schools(file=101/db=101) scopes(file=30/mapped=38/61) enroll=101 status(v=0 ref=9 review=29 pending=23 unknown=0) intel_map=3 intel_mirror=73 gov=1
chenghua: PASS | schools(file=41/db=41) scopes(file=44/mapped=36/38) enroll=41 status(v=36 ref=0 review=0 pending=2 unknown=0) intel_map=1 intel_mirror=0 gov=1
jinniu: PASS | schools(file=63/db=63) scopes(file=54/mapped=46/63) enroll=63 status(v=0 ref=0 review=46 pending=17 unknown=0) intel_map=1 intel_mirror=0 gov=1
gaoxin: PASS | schools(file=43/db=43) scopes(file=46/mapped=35/41) enroll=43 status(v=0 ref=5 review=30 pending=6 unknown=0) intel_map=3 intel_mirror=0 gov=1
tianfu: PASS | schools(file=41/db=41) scopes(file=12/mapped=0/38) enroll=41 status(v=0 ref=0 review=0 pending=38 unknown=0) intel_map=1 intel_mirror=0 gov=1
ALL DISTRICTS PARITY PASS
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
=== verify_district_parity (year=2025) ===
jinjiang: PASS | schools(file=28/db=28) scopes(file=25/mapped=25/26) enroll=28 intel_map=1 intel_mirror=0 gov=1
qingyang: PASS | schools(file=36/db=36) scopes(file=32/mapped=32/34) enroll=36 intel_map=1 intel_mirror=0 gov=1
wuhou: PASS | schools(file=101/db=101) scopes(file=47/mapped=56/61) enroll=101 intel_map=3 intel_mirror=73 gov=1
chenghua: PASS | schools(file=41/db=41) scopes(file=36/mapped=36/38) enroll=41 intel_map=1 intel_mirror=0 gov=1
jinniu: PASS | schools(file=63/db=63) scopes(file=59/mapped=59/63) enroll=63 intel_map=1 intel_mirror=0 gov=1
gaoxin: PASS | schools(file=43/db=43) scopes(file=40/mapped=40/41) enroll=43 intel_map=3 intel_mirror=0 gov=1
tianfu: PASS | schools(file=41/db=41) scopes(file=38/mapped=38/38) enroll=41 intel_map=1 intel_mirror=0 gov=1
ALL DISTRICTS PARITY PASS
```

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
.................                                                        [100%]
17 passed in 0.95s
```

## OCR / Tianfu Notes

- OCR rows remain `pending_review`.
- Tianfu 2026 remains all `pending_official` and is accepted only as a transitional reform state.
- Tianfu should be handled through a human review / school-district reform mapping workflow before any user-facing "verified" claim.

## Recommendation For Next Phase

- Prefer Phase 3D next: build the human review workflow for OCR and Tianfu reform mapping.
- Phase 3C frontend year switching can start after Phase 3D defines how `verified`, `reference`, `pending_review`, and `pending_official` should be displayed.

## Risks / Blockers

- No current P0 blocker for DB verification.
- Remaining risk is data quality, not import isolation: OCR and Tianfu reform rows still need human review before verification.

---

# Codex Continuation: Phase 3D Read-Only Review Queue

Status: COMPLETE

## Files Changed

- `packages/api/src/chengdu_edu_api/mapping_display.py`
- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/templates/base.html`
- `packages/api/src/chengdu_edu_api/templates/mapping_review.html`
- `packages/api/tests/test_mapping_review_page.py`

## What Was Done

- Added first-class `pending_review` display metadata with a `待复核` badge.
- Added `/review/mappings` page for 2026 mapping review.
- Default review queue shows `pending_review` and `pending_official` records.
- Added filters for year, district, and mapping status.
- Added status count summary cards for `verified`, `reference`, `pending_review`, `pending_official`, and unknown statuses.
- Added `/review/mappings.csv` export with `review_decision` and `review_notes` columns for offline human review.
- Added tests covering default review queue filtering, verified-status filtering, and `pending_review` badge behavior.

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
21 passed
```

```text
.venv/bin/ruff check <touched python files>
All checks passed!
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

```text
GET /review/mappings
200 OK

GET /review/mappings.csv?status=pending_review&district=jinniu&year=2026
200 OK, returns CSV rows
```

## Next Recommended Step

- Add reviewer decision import/capture for `pending_review` and `pending_official` rows.
- Then start Phase 3C frontend year switching with clear status display rules.

---

# Codex Continuation: Phase 3D CSV Decision Import

Status: COMPLETE

## Files Changed

- `scripts/import_mapping_review_decisions.py`
- `packages/storage/tests/test_import_mapping_review_decisions.py`

## What Was Done

- Added CLI import for CSV review decisions exported from `/review/mappings.csv`.
- Blank `review_decision` rows are skipped.
- Valid decisions are `verified`, `reference`, `pending_review`, and `pending_official`.
- Stale CSV rows are skipped if exported `mapping_status` no longer matches the DB row.
- Successful updates write:
  - `fields.mapping_status`
  - `fields.review_notes`
  - `fields.reviewed_by`
  - `fields.reviewed_at`
  - `fields.review_source`
  - `fields.previous_mapping_status` when status changes
- Successful updates increment `current_version` and add `record_versions` / `field_changes` audit rows.
- Added tests for dry-run, successful audited update, and stale CSV protection.

## Usage

```bash
.venv/bin/python scripts/import_mapping_review_decisions.py /path/to/review.csv --dry-run --reviewed-by reviewer-name
.venv/bin/python scripts/import_mapping_review_decisions.py /path/to/review.csv --reviewed-by reviewer-name
```

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
24 passed
```

```text
.venv/bin/ruff check <touched python files>
All checks passed!
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

```text
.venv/bin/python scripts/import_mapping_review_decisions.py /tmp/mapping-review-jinniu.csv --dry-run --reviewed-by codex-smoke
DRY RUN: updated=0 blank=46 unchanged=0 stale=0 missing=0 invalid=0
```

## Next Recommended Step

- Phase 3C year switching can start.
- Optional: add in-browser reviewer capture if CSV round-trip is too slow for the team.

---

# Codex Continuation: Phase 3C Year Switching

Status: COMPLETE

## Files Changed

- `packages/api/src/chengdu_edu_api/mapping_display.py`
- `packages/api/src/chengdu_edu_api/enrichment.py`
- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/routes/schools.py`
- `packages/api/src/chengdu_edu_api/templates/index.html`
- `packages/api/src/chengdu_edu_api/templates/school_results.html`
- `packages/api/src/chengdu_edu_api/templates/school_detail.html`
- `packages/api/tests/test_mapping_year_switch.py`

## What Was Done

- Added explicit mapping year selection to the search page.
- Filtered homepage scope dropdown by selected `district_mapping` year.
- Made search result mapping badges/summaries use the selected year.
- Preserved selected year in school detail links.
- Added a year selector to school detail pages.
- Filtered school detail mapping, enrollment, and promotion policy display by selected year.
- Added `/api/schools?year=...` support and applied it to scope search + mapping summaries.
- Added tests proving same-school 2025/2026 records do not leak across API search, scope search, homepage links, or detail pages.

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
28 passed
```

```text
.venv/bin/ruff check <touched python files>
All checks passed!
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

```text
GET /?year=2025&district=jinniu
200 OK, year selector selected, result links include ?year=2025

GET /review/mappings?year=2026&district=&status=verified
200 OK

GET /api/schools?district=jinniu&year=2025&limit=1
200 OK, returns framework_year=2025
```

## Next Recommended Step

- Broader visual QA of search/detail/review pages across 2025 and 2026.
- Optional: in-browser reviewer capture to replace CSV round-trip.

---

# Codex Continuation: In-Browser Review Capture

Status: COMPLETE

## Files Changed

- `packages/api/src/chengdu_edu_api/mapping_display.py`
- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/templates/mapping_review.html`
- `packages/api/tests/test_mapping_review_page.py`

## What Was Done

- Added a review form to each `/review/mappings` record.
- Reviewers can choose `verified`, `reference`, `pending_review`, or `pending_official`.
- Reviewers can add `review_notes`.
- POST handler updates mapping fields and writes audit history:
  - `record_versions`
  - `field_changes`
  - `current_version`
- Added stale-status protection: if the page was loaded with an older `mapping_status`, POST redirects without changing the row.
- Added page messages for updated, stale, and invalid decision states.

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
30 passed
```

```text
.venv/bin/ruff check <touched python files>
All checks passed!
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

```text
GET /review/mappings?year=2026&district=jinniu&status=pending_review
200 OK, renders review forms

GET /review/mappings?year=2026&district=jinniu&status=pending_review&message=updated
200 OK, renders success message
```

## Notes

- Real DB POST smoke was intentionally not run to avoid mutating project data.
- Unit/integration tests cover successful POST update and stale-status rejection.

## Next Recommended Step

- Broader visual QA across search, detail, and review pages.
- Add auth/permission hardening before exposing write actions beyond local trusted use.

---

# Codex Continuation: Review Write Protection

Status: COMPLETE

## Files Changed

- `packages/api/src/chengdu_edu_api/routes/pages.py`
- `packages/api/src/chengdu_edu_api/templates/mapping_review.html`
- `packages/api/tests/test_mapping_review_page.py`

## What Was Done

- Added `ENABLE_REVIEW_WRITE=true` gate for in-browser review writes.
- Added optional `REVIEW_WRITE_TOKEN` check.
- Review page defaults to read-only mode when writes are disabled.
- Save forms are hidden in read-only mode.
- POST write endpoint returns `403` when writes are disabled or token is invalid.

## Usage

```bash
ENABLE_REVIEW_WRITE=true .venv/bin/python -m uvicorn chengdu_edu_api.main:app --host 127.0.0.1 --port 8000
ENABLE_REVIEW_WRITE=true REVIEW_WRITE_TOKEN=secret .venv/bin/python -m uvicorn chengdu_edu_api.main:app --host 127.0.0.1 --port 8000
```

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
34 passed
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

```text
GET /review/mappings?year=2026&district=jinniu&status=pending_review
200 OK, read-only message shown

POST /review/mappings/<id>/decision
403 Forbidden when writes are disabled
```

## Next Recommended Step

- Broader visual QA across search, detail, and review pages.
- Then create a clean checkpoint commit or patch set before more data work.

---

# Codex Continuation: Browser QA Checkpoint

Status: COMPLETE

## What Was Verified

- Home page loads with year selector, school selector, and search button.
- Selecting `四川天府新区元音小学` and clicking search returns exactly one visible result.
- Search result detail link preserves `?year=2026`.
- School detail page opens, shows selected year `2026`, mapping section, status badge text, and back link preserving year.
- Review queue page for `year=2026&district=jinniu&status=pending_review` returns 46 records.
- Review page shows CSV export and read-only warning.
- Review page hides save buttons when `ENABLE_REVIEW_WRITE` is not set.
- Jinniu 2025 search page shows 63 schools and first detail link includes `?year=2025`.
- Jinniu 2026 search page shows 63 schools and first detail link includes `?year=2026`.
- Browser console reported no errors during this QA path.

## Verification

```text
.venv/bin/pytest packages/storage/tests packages/api/tests -q
34 passed
```

```text
.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
ALL DISTRICTS PARITY PASS
```

## Next Recommended Step

- Create a clean checkpoint patch/commit boundary before additional data work.
- Then proceed to small-batch manual review or official-source replacement.

---

# Codex Continuation: Checkpoint Documentation

Status: COMPLETE

## Files Added

- `docs/codex-checkpoint-2026-06-18.md`

## What Was Done

- Captured the current verified MVP baseline.
- Documented verification commands and browser QA results.
- Documented feature boundaries across data/import, validation, frontend/API, and review workflow.
- Proposed four clean commit groups:
  - data parity and 2026 sources
  - import and verification tooling
  - frontend/API year switching and review UI
  - project process artifacts
- Flagged files that should not be buried in broad commits without review.
- Listed current P1/P2 risks and next recommended work.

## Next Recommended Step

- Use the checkpoint document to create a clean commit/patch boundary.
- Then start small-batch manual review or official-source replacement.
