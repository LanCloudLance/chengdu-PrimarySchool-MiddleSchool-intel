# Loop State

Status: PAUSED

Goal:

Run the Cursor execution / Codex review loop until these are true:

- `scripts/verify_district_parity.py` passes.
- `scripts/verify_district_parity.py --db` passes.
- `packages/storage/tests packages/api/tests` pass.
- `configs/schools.yaml` no longer contains legacy district duplicates that can pollute DB imports.
- Gaoxin 2024-derived data remains `reference` until official 2026 data is reviewed.
- Codex gives final PASS or conditional PASS with no P0 blockers.

Last Codex action:

- Paused loop by user request on 2026-06-17.
- Codex fixed Phase 3B DB verification on 2026-06-17.
- Codex added Phase 3D read-only mapping review page on 2026-06-17:
  - `/review/mappings` defaults to 2026 `pending_review` + `pending_official`.
  - `pending_review` now has a first-class frontend badge.
  - `/review/mappings.csv` exports the filtered review queue with reviewer fill-in columns.
  - Added API page tests for review queue filtering.
- Codex added Phase 3D CSV decision import on 2026-06-17:
  - `scripts/import_mapping_review_decisions.py` imports `review_decision` / `review_notes`.
  - Supports `--dry-run`.
  - Guards against stale CSV by comparing exported `mapping_status` with DB status.
  - Writes `record_versions` and `field_changes` audit rows on update.
- Codex added Phase 3C frontend/API year switching on 2026-06-17:
  - Search page has a `划片年份` selector.
  - School result links preserve `?year=...`.
  - School detail page has a year selector and filters mapping/enrollment/promotion display by year.
  - `/api/schools` supports `year` and uses it for scope search + mapping summaries.
- Codex added in-browser mapping review capture on 2026-06-17:
  - Each `/review/mappings` record has a review decision select, notes field, and save action.
  - POST writes `mapping_status`, review metadata, `record_versions`, and `field_changes`.
  - POST rejects stale form submissions when the DB status has changed.
- Codex fixed homepage search blank-select 422 on 2026-06-17:
  - Empty `type=` and `level=` form values are normalized to `None`.
  - `/` and `/api/schools` both accept blank select values.
- Codex added review write protection on 2026-06-18:
  - `ENABLE_REVIEW_WRITE=true` is required before review POST writes are accepted.
  - Optional `REVIEW_WRITE_TOKEN` requires a matching form token.
  - Review page defaults to read-only mode and hides save forms when disabled.
- Codex completed browser QA checkpoint on 2026-06-18:
  - Home page loads with year/school/search controls.
  - Selecting `四川天府新区元音小学` and clicking search returns one result.
  - Detail page opens with `year=2026`, shows mapping section/status, and back link preserves year.
  - Review page `jinniu + pending_review + 2026` shows 46 records, CSV export, read-only notice, and no save buttons.
  - Jinniu 2025/2026 search pages both show 63 schools and preserve year-specific detail links.
  - Browser console has no errors during the QA path.
- Codex created checkpoint documentation on 2026-06-18:
  - `docs/codex-checkpoint-2026-06-18.md`
  - Includes verification status, feature boundary, suggested commit groups, known risks, and next recommended work.
- Verified `.venv/bin/python scripts/verify_district_parity.py --year 2026`: PASS.
- Verified `.venv/bin/python scripts/verify_district_parity.py --year 2026 --db`: PASS.
- Verified `.venv/bin/python scripts/verify_district_parity.py --year 2025 --db`: PASS.
- Verified `.venv/bin/pytest packages/storage/tests packages/api/tests -q`: 34 passed.
- Verified touched-file ruff check: PASS.
- Verified local FastAPI smoke test:
  - `GET /review/mappings`: 200.
  - `GET /review/mappings.csv?status=pending_review&district=jinniu&year=2026`: returns CSV rows.
  - `GET /?year=2025&district=jinniu`: 200, year selector selected, school links preserve `?year=2025`.
  - `GET /review/mappings?year=2026&district=&status=verified`: 200.
  - `GET /api/schools?district=jinniu&year=2025&limit=1`: returns `framework_year=2025`.
  - `GET /review/mappings?year=2026&district=jinniu&status=pending_review`: 200, renders review forms.
  - `GET /review/mappings?year=2026&district=jinniu&status=pending_review&message=updated`: 200, renders success message.
  - `GET /?year=2026&q=&scope_q=&district=&type=&level=`: 200.
  - `GET /?year=2026&q=<school>&scope_q=&district=&type=&level=`: 200.
  - `GET /api/schools?year=2026&q=&scope_q=&district=&type=&level=`: 200.
  - `GET /review/mappings?year=2026&district=jinniu&status=pending_review`: 200, read-only message shown.
  - `POST /review/mappings/<id>/decision` with writes disabled: 403.
- Verified CSV import dry-run against real DB export:
  - `DRY RUN: updated=0 blank=46 unchanged=0 stale=0 missing=0 invalid=0`.

Remaining non-blocking follow-up:

- Phase 3B is conditionally accepted.
- OCR rows may remain `pending_review`.
- Tianfu `pending_official` is accepted only as a transitional reform state.
- Phase 3C year switching is implemented and smoke-tested.
- Phase 3D supports CSV export/import and in-browser review capture.
- Checkpoint documentation is ready.
- Next extension is creating a clean commit/patch boundary, then small-batch manual review or official-source replacement.
- Phase 3C frontend year switching can start after status display rules are accepted.

Resume condition:

- Do not continue the loop until the user explicitly asks to resume.
