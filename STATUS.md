# KH Rights Finder — Project Status

Last updated: 2026-02-28 (commit `0453912`)

## What This Project Does

A tool for searching Cambodian IP registries to find trademark/exclusive-right evidence for a given brand name. Users enter a brand, the system scrapes official government databases, scores the results, and displays evidence cards.

## Architecture

```
docker compose up  →  4 services
```

| Service | Stack | Port | Source mount |
|---------|-------|------|-------------|
| **db** | Postgres 16 | 5432 | volume `pgdata` |
| **api** | FastAPI + SQLAlchemy (async) | 8000 | `backend/app/` |
| **worker** | Python async loop (same image as api) | — | `backend/app/` |
| **web** | Next.js 14 (App Router) | 3000 | `frontend/src/` |

### Data flow

1. **User submits brand** → `POST /api/search` → upserts `Mark`, creates `IngestionJob` per source (idempotent).
2. **Worker loop** picks up pending jobs, runs the matching scraper, stores `Evidence` + `Snapshot` rows, marks job done.
3. **Frontend polls** `GET /api/search/{mark_id}` every 3s until all jobs finish. Renders evidence cards + score.

### Key files

```
backend/
  app/
    main.py              — FastAPI app + lifespan (runs Alembic migrations)
    models.py            — SQLAlchemy models: Mark, Evidence, Snapshot, IngestionJob, WatchlistEntry
    schemas.py           — Pydantic response models (EvidenceOut, SearchResultOut, etc.)
    db.py                — async engine + session factory
    config.py            — Settings (DATABASE_URL, SCRAPER_DEBUG)
    worker.py            — Worker loop: poll jobs → run scraper → store evidence
    evidence_schemas.py  — TrademarkEvidenceV1, ExclusiveRightsEvidenceV1, parse_evidence(), FIELD_MAPs
    scoring.py           — compute_score() — weights evidence into a 0-100 score
    routers/
      search.py          — POST /api/search, GET /api/search/{mark_id}, POST /api/search/{mark_id}/retry
      evidence.py        — GET /api/evidence?mark_id=...
      watchlist.py       — CRUD for watchlist entries
    scrapers/
      base.py            — BaseScraper ABC + ScraperResult dataclass + registry
      dip_trademark.py   — DIP trademark search (ASP.NET WebForms: GET form → extract hidden fields → POST)
      dip_exclusive.py   — DIP exclusive rights listing + PDF OCR (extract_pdf_text, extract_exclusive_rights_fields)
      secondary.py       — Secondary/informational sources

frontend/
  src/
    lib/api.ts           — API client + TypeScript interfaces (EvidenceItem, SearchResult, etc.)
    app/
      page.tsx           — Home / search form
      layout.tsx         — Root layout
      results/[markId]/page.tsx — Results page (polls, renders evidence cards + score)
      watchlist/page.tsx — Watchlist page
    components/
      EvidenceCard.tsx   — Evidence card with field filtering + progressive disclosure
      ScoreBadge.tsx     — Score display badge
      SearchForm.tsx     — Brand name search input
      WatchlistTable.tsx — Watchlist table
```

## What Works

- **Search + ingestion pipeline**: brand search → job creation → worker picks up → scraper runs → evidence stored → UI displays results.
- **DIP trademark scraper**: correctly submits ASP.NET WebForms (auto-discovers textbox, submit button, includes all hidden fields like `__VIEWSTATE`, `__PREVIOUSPAGE`). Returns real results (e.g., Unilever: 144 records, Coca-Cola: records with owner/address/application #).
- **Structured evidence fields**: scraper now correctly parses the nested DIP GridView HTML (`<h5>` mark name + `<table class="info-list-detail">` label/value rows). `TrademarkEvidenceV1` fields (`mark_name`, `owner_name`, `application_number`, `filing_date`, etc.) populate correctly. Missing fields stay `null` (never inferred).
- **Evidence `raw_text`**: each record gets a clean, human-readable `raw_text` (stored in `evidence.detail->>'raw_text'`), not a JSON blob. Full HTML snapshots are preserved separately in the `snapshots` table.
- **Idempotent Alembic migrations**: migrations 001 and 002 use `IF NOT EXISTS` / `pg_indexes` checks so `alembic upgrade head` never crashes on a DB where `create_all()` already ran.
- **Worker stability**: loop runs continuously, job idempotency prevents duplicates, stale-job reaper auto-fails jobs stuck >10 min.
- **UI**: search → results page with polling → evidence cards + score breakdown + watchlist.
- **EvidenceCard**: filters malformed scraper data (clean vs raw), progressive disclosure via `<details>`, no horizontal overflow.
- **Exclusive rights (Task 3)**:
  - **Listing scraper**: `dip_exclusive` fetches the DIP exclusive-rights page, matches brand names to PDF links, returns `ScraperResult` with `brand`, `pdf_url`, `href`, `page`.
  - **PDF text extraction**: `extract_pdf_text(pdf_bytes)` in `dip_exclusive.py` — pypdf text-layer first; if &lt;200 chars, OCR fallback via PyMuPDF + pytesseract at 300 DPI (max 3 pages). Returns `(text, warnings)`; never raises. Dockerfile installs `tesseract-ocr`.
  - **Evidence mapping**: `extract_exclusive_rights_fields(text)` extracts from certificate text: `rights_holder` (company regex), `scope` (import/distribution/both), `reference_number` (KH/…), `valid_from_raw` / `valid_to_raw` (contextual date regexes). Listing values take precedence; no inference — missing fields stay `null` with `parse_warnings`.
  - **parse_evidence**: For `dip_exclusive` with `_raw_text` &gt;200 chars, `_enrich_from_pdf_text()` merges extracted fields; `_pdf_warnings` flow into `parse_warnings`. Schema: `ExclusiveRightsEvidenceV1` includes `reference_number`.
  - **Tests**: `tests/test_dip_exclusive_rights_pdf_extraction.py` (20 tests) + fixtures `fixtures/dip_exclusive_rights/listing_example.html`, `certificate_example.pdf` (real Ford certificate, scanned). Tests cover OCR, extraction, ambiguous-dates warning, listing precedence.

## Known Issues / Technical Debt

### ~~Scraper data quality~~ (FIXED)
Previously, `_extract_table_rows` assumed a flat header-row + data-rows table, but the DIP GridView uses nested layout tables. This produced garbled key/value pairs. **Fixed in commit `0453912`**: parser now walks each outer `<tr>`, finds `<h5>` (mark name) and `<table class="info-list-detail">` (label/value rows), normalises labels (strip colons, collapse whitespace, lowercase), and maps them via `_TRADEMARK_FIELD_MAP` so `TrademarkEvidenceV1` fields populate.

### ~~Evidence title always "Unknown mark"~~ (FIXED)
The scraper now extracts the mark name from the `<h5>` element and sets `ScraperResult.title` correctly.

### Score display
DIP trademark and DIP exclusive both feed into scoring (trademark 0–60 pts, exclusive 0–40 pts). Score label may need tuning as more sources produce data.

### No pagination
180 evidence cards render at once for Unilever. Should paginate or virtualize.

## Git History

```
(working)  Task 3: Exclusive rights — PDF OCR, extract_exclusive_rights_fields, evidence mapping
0453912 Fix dip_trademark extraction and structured evidence fields (Task 2)
ecf83c4 Fix dip_trademark parsing and evidence mapping (Task 2)
491008c Add evidence schemas, validation pipeline, and Alembic migration
145ec4a Fix EvidenceCard overflow, title fallback, and field rendering
7c10bbe Ignore local scraper snapshots
3d6437c Checkpoint: worker stability + trademark WebForms submission
```

## Running Locally

```bash
docker compose up --build
# web:    http://localhost:3000
# api:    http://localhost:8000/docs
# debug:  SCRAPER_DEBUG=1 docker compose up worker
```

### Running tests

```bash
# All backend tests (inside Docker):
docker compose exec api python -m pytest tests/ -v

# Trademark + evidence schema tests:
docker compose exec api python -m pytest tests/test_dip_trademark_parser.py tests/test_evidence_schemas.py -v

# Exclusive rights PDF extraction + mapping tests (requires tesseract-ocr in image):
docker compose exec api python -m pytest tests/test_dip_exclusive_rights_pdf_extraction.py -v
```

### Applying database migrations

```bash
# Run all pending Alembic migrations inside the api container:
docker compose exec api alembic upgrade head

# Verify the latest columns exist:
docker compose exec db psql -U khrights -d khrights \
  -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'evidence' AND column_name IN ('evidence_kind', 'schema_version');"

# Verify structured evidence fields are populated (raw_text lives inside detail JSONB):
docker compose exec db psql -U khrights -d khrights -c "
  SELECT id, source, evidence_kind,
         detail->>'mark_name'           AS mark_name,
         detail->>'application_number'  AS app_no,
         detail->>'owner_name'          AS owner,
         left(detail->>'raw_text', 80)  AS raw_text_preview,
         (detail ? 'raw_text')            AS has_raw_text,
         confidence
  FROM evidence
  ORDER BY found_at DESC LIMIT 5;"
```

### Dev DB recovery (migration drift)

If `alembic upgrade head` fails because schema objects already exist (e.g.
`DuplicateTableError` or `DuplicateColumnError`), the DB schema was likely
created by `Base.metadata.create_all()` at startup while `alembic_version`
is out of sync.

```bash
# 1. Check what Alembic thinks the current revision is:
docker compose exec api alembic current

# 2. If the output is empty or behind, but the actual schema already
#    matches head, stamp the DB to the latest revision without running
#    the migrations again:
docker compose exec api alembic stamp head

# 3. Verify:
docker compose exec api alembic current
#    Should print: 002 (head)

# 4. Future migrations will now apply cleanly:
docker compose exec api alembic upgrade head
```

> **Note:** Migrations 001 and 002 are idempotent — they check for
> existing indexes/columns before creating them, so `upgrade head` is
> safe to run even if the schema already exists.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PASSWORD` | `localdev` | Postgres password |
| `DATABASE_URL` | (composed in docker-compose) | Async SQLAlchemy connection string |
| `SCRAPER_DEBUG` | `0` | Set to `1` for verbose scraper logging + HTML snapshots |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API URL for frontend |
