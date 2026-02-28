# KH Rights Finder — Project Status

Last updated: 2026-02-27 (commit `145ec4a`)

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
    scoring.py           — compute_score() — weights evidence into a 0-100 score
    routers/
      search.py          — POST /api/search, GET /api/search/{mark_id}, POST /api/search/{mark_id}/retry
      evidence.py        — GET /api/evidence?mark_id=...
      watchlist.py       — CRUD for watchlist entries
    scrapers/
      base.py            — BaseScraper ABC + ScraperResult dataclass + registry
      dip_trademark.py   — DIP trademark search (ASP.NET WebForms: GET form → extract hidden fields → POST)
      dip_exclusive.py   — DIP exclusive rights search
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
- **Worker stability**: loop runs continuously, job idempotency prevents duplicates, stale-job reaper auto-fails jobs stuck >10 min.
- **UI**: search → results page with polling → evidence cards + score breakdown + watchlist.
- **EvidenceCard**: filters malformed scraper data (clean vs raw), progressive disclosure via `<details>`, no horizontal overflow.

## Known Issues / Technical Debt

### Scraper data quality (backend — `dip_trademark.py`)
The DIP site's HTML table structure causes the row parser (`_extract_table_rows`) to produce malformed key/value pairs:
- Some keys are data values (e.g., `"unilever n.v."` as a key instead of `"owner name"`)
- Some values are labels (e.g., `"Owner Address:"` as a value)
- Some keys are giant concatenated strings (160+ chars of merged field data)

**Current mitigation**: frontend `EvidenceCard` uses heuristics (`isCleanEntry()`) to filter clean fields from junk. The junk is hidden behind a "Show raw data" toggle.

**Proper fix would be**: improve `_extract_table_rows` to correctly parse the DIP table headers/rows. The issue is likely that the table has nested elements or `colspan` that the simple `<tr>/<td>` iteration doesn't handle.

### Evidence title always "Unknown mark"
The scraper can't find the mark name in the parsed table data (headers don't match expected keys like `"mark"` or `"mark name"`). Frontend works around this by passing `markName` prop (the searched brand name) to `EvidenceCard` as a fallback title.

### Score always shows "15 Weak"
Only DIP trademark returns results currently. Scoring may need tuning once more sources produce data.

### No pagination
180 evidence cards render at once for Unilever. Should paginate or virtualize.

## Git History

```
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
