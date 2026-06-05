# Development Roadmap
**Project:** Weekly Stock Screener  
**Version:** 1.0  
**Date:** 2026-06-03  
**Based on:** Business Requirements Specification v1.0

---

## Current State Assessment

| Area | Status | Notes |
|---|---|---|
| PostgreSQL schema | ✅ Exists | `tickers`, `watchlists`, `watchlist_versions`, `watchlist_items` tables present |
| BMSB screener script | ⚠️ Partial | Core logic works; no logging, no run-outcome classification, no exchange in output |
| `tickers` table | ⚠️ Partial | `exchange` column defined in `init.sql`; most tickers seeded as `active = false` |
| Middleware / API | ❌ Missing | No REST layer exists |
| Angular client | ❌ Missing | No frontend exists |
| Scheduling | ❌ Missing | Manual script execution only |

---

## Implementation Waves

### Wave 1 — Solid Foundation (Backend Data Layer)
> Goal: Make the screener run reliably end-to-end and persist clean, queryable data.

### Wave 2 — API Layer (Middleware)
> Goal: Expose screener results over HTTP so Angular can consume them.

### Wave 3 — Angular Client (Frontend)
> Goal: Display current trade ideas in a browser with TradingView links.

### Wave 4 — Operations & Scheduling
> Goal: Automate weekly runs, add observability, support future screeners.

---

## Milestones

| Milestone | Wave | Description |
|---|---|---|
| M1 | 1 | Screener runs reliably and logs per-ticker outcomes |
| M2 | 1 | Exchange included in watchlist items; query for latest-version results works |
| M3 | 2 | REST endpoint returns latest-version passed stocks with symbol + exchange |
| M4 | 3 | Angular displays current stock list with empty-state handling |
| M5 | 3 | TradingView redirect links functional per stock |
| M6 | 4 | Weekly run trigger in place (manual → scheduled) |
| M7 | 4 | Run outcome classification (success/warning/error) observable from logs/DB |

---

## Feature Breakdown

---

### FEATURE-01 — Screener Per-Ticker Logging
**Wave:** 1  
**Milestone:** M1

**Business Goal:**  
BR-7: Log per-ticker scan attempt, success/failure, and pass/fail outcome so the operator can debug missing symbols.

**Dependencies:**  
- Existing `bmsb_above_screener.py`  
- Existing DB connection

**Acceptance Criteria:**  
- Each ticker produces a log entry with: symbol, scan status (`attempted` / `succeeded` / `failed`), pass/fail result  
- Exceptions are caught and logged with error message  
- No ticker silently skipped without a log entry

**Estimated Complexity:** Low (1–2 hours)  
**Implementation Order:** 1

---

### FEATURE-02 — Run Outcome Classification
**Wave:** 1  
**Milestone:** M1, M7

**Business Goal:**  
BR-7 / Section 7: Each run must be classifiable as `success`, `warning`, or `error` based on how many tickers were scanned.

**Dependencies:**  
- FEATURE-01 (logging must track scan counts)

**Acceptance Criteria:**  
- After each run: total tickers, scanned count, and failed count are recorded  
- Run classified as: `success` (all scanned), `warning` (partial), `error` (0 scanned)  
- Outcome stored on `watchlist_versions` row (add `run_outcome` column) or written to log

**Estimated Complexity:** Low (1–2 hours)  
**Implementation Order:** 2

---

### FEATURE-03 — Exchange Propagation to Watchlist Items
**Wave:** 1  
**Milestone:** M2

**Business Goal:**  
BR-5 / Master Data Rule: The exchange displayed to the user must come from `tickers` master data, not hardcoded or derived elsewhere. Needed for correct TradingView link construction.

**Dependencies:**  
- `tickers.exchange` column populated correctly for all active tickers  
- `watchlist_items` table — may need `exchange` column added, OR exchange is joined at query time from `tickers`

**Acceptance Criteria:**  
- For every passing symbol, exchange is available and traceable to `tickers.exchange`  
- Preference: join at API query time (no duplication), not stored in `watchlist_items`  
- Seed data: all active tickers have a non-null `exchange` value

**Estimated Complexity:** Low (1–3 hours)  
**Implementation Order:** 3

---

### FEATURE-04 — Latest-Version Query (DB View or Query)
**Wave:** 1  
**Milestone:** M2

**Business Goal:**  
BR-4 / BR-5: Define and test the canonical query that returns only passed stocks from the most recently created version. This is the core data contract.

**Dependencies:**  
- FEATURE-03 (exchange must be joinable)

**Acceptance Criteria:**  
- Query returns: `symbol`, `exchange` for all items in the latest `watchlist_version` for `BMSB_ABOVE`  
- If latest version has 0 items, query returns empty result set (no fallback to older version)  
- Query is correct when multiple screeners/watchlists exist (scoped by watchlist name)  
- Optionally encapsulated as a DB view `quant.v_current_bmsb` for reuse

**Estimated Complexity:** Low (1–2 hours)  
**Implementation Order:** 4

---

### FEATURE-05 — Middleware REST API — Current Results Endpoint
**Wave:** 2  
**Milestone:** M3

**Business Goal:**  
BR-5: Provide a single HTTP endpoint that Angular consumes to get the current list of passing stocks.

**Dependencies:**  
- FEATURE-04 (latest-version query must exist and be tested)  
- Technology choice: FastAPI (Python, consistent with existing stack) recommended

**Acceptance Criteria:**  
- `GET /api/screener/bmsb/current` returns `200` with JSON array of `{ symbol, exchange }`  
- Returns empty array `[]` when latest version has no items (not 404, not error)  
- Response always reflects latest-version semantics (no caching that violates BR-4)  
- Runs locally and inside Docker

**Estimated Complexity:** Medium (3–5 hours)  
**Implementation Order:** 5

---

### FEATURE-06 — Angular Project Scaffold + Stock List Component
**Wave:** 3  
**Milestone:** M4

**Business Goal:**  
BR-6 / NFR-1: Provide a minimal, usable UI that shows the current screening results.

**Dependencies:**  
- FEATURE-05 (API endpoint must be callable)  
- Angular CLI scaffolding (new project or add to monorepo)

**Acceptance Criteria:**  
- Angular app starts and calls `GET /api/screener/bmsb/current`  
- Displays a list of passing stocks (symbol + exchange)  
- If API returns `[]`, displays "No stocks to show" informational message (BR-6)  
- No authentication required (v1 scope)

**Estimated Complexity:** Medium (4–6 hours)  
**Implementation Order:** 6

---

### FEATURE-07 — TradingView Redirect Links
**Wave:** 3  
**Milestone:** M5

**Business Goal:**  
BR-5 / Section 14 Open Item: Each stock in the Angular list should link directly to its TradingView chart using exchange + symbol.

**Dependencies:**  
- FEATURE-06 (stock list component must exist)  
- Resolve Open Item: canonical `exchange:SYMBOL` mapping format for TradingView URL  
  - Standard format: `https://www.tradingview.com/chart/?symbol=NASDAQ:TSLA`

**Acceptance Criteria:**  
- Each stock row has a clickable link that opens TradingView in a new tab  
- URL constructed as `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}`  
- Link is correct for both NYSE and NASDAQ exchanges  
- If exchange is null/missing, link is gracefully omitted or shows a fallback

**Estimated Complexity:** Low (1–2 hours)  
**Implementation Order:** 7

---

### FEATURE-08 — Weekly Run Trigger (Manual → Scheduled)
**Wave:** 4  
**Milestone:** M6

**Business Goal:**  
BR-1 / Section 14 Open Item: The screener must run weekly. Start with a manually triggered mechanism, then automate.

**Dependencies:**  
- FEATURE-01, FEATURE-02 (screener must be stable and logged before scheduling)  
- Docker Compose environment

**Acceptance Criteria:**  
- Phase A (Manual): Script can be triggered via a documented CLI command or Docker `exec`  
- Phase B (Scheduled): A cron-based trigger (e.g., Docker + cron, or `pg_cron`, or a simple scheduler container) fires the screener once per week  
- Run creates a new version each time (no deduplication / skipping)

**Estimated Complexity:** Medium (3–5 hours)  
**Implementation Order:** 8

---

### FEATURE-09 — Extensibility: Multi-Screener Support
**Wave:** 4  
**Milestone:** M7

**Business Goal:**  
BR-8 / NFR-5: The system should support adding new weekly screeners without changing the core data model or the Angular client's interpretation model.

**Dependencies:**  
- All Wave 1–3 features complete  
- Design decision: screener name/type encoded in `watchlists.name`

**Acceptance Criteria:**  
- A second screener can be added by: (1) implementing a new script, (2) seeding a new `watchlists` row — no schema changes  
- The API endpoint can be parameterized: `GET /api/screener/{name}/current`  
- Angular can be extended to show results from multiple screeners without redesign  
- Existing BMSB behavior unchanged

**Estimated Complexity:** Medium (3–5 hours)  
**Implementation Order:** 9

---

## Summary Table

| # | Feature | Wave | Complexity | Order | Milestone |
|---|---|---|---|---|---|
| F-01 | Per-Ticker Logging | 1 | Low | 1 | M1 |
| F-02 | Run Outcome Classification | 1 | Low | 2 | M1, M7 |
| F-03 | Exchange Propagation | 1 | Low | 3 | M2 |
| F-04 | Latest-Version Query | 1 | Low | 4 | M2 |
| F-05 | REST API — Current Results | 2 | Medium | 5 | M3 |
| F-06 | Angular Scaffold + Stock List | 3 | Medium | 6 | M4 |
| F-07 | TradingView Links | 3 | Low | 7 | M5 |
| F-08 | Weekly Run Trigger | 4 | Medium | 8 | M6 |
| F-09 | Multi-Screener Extensibility | 4 | Medium | 9 | M7 |

---

## Open Items to Resolve Before Technical Design

These are flagged in BRS Section 14 and must be decided before the related features begin:

| # | Item | Blocks | Decision Needed |
|---|---|---|---|
| OI-1 | Empty-state UI message wording | F-06 | Final text for "No stocks to show" message |
| OI-2 | TradingView symbol format | F-07 | Confirm `EXCHANGE:SYMBOL` URL format (e.g. `NASDAQ:TSLA`) |
| OI-3 | Weekly run trigger mechanism | F-08 | Manual CLI first, then cron vs. scheduler container |

---

## Risk Register

| Risk | Affected Features | Mitigation |
|---|---|---|
| Partial scans produce empty UI (intentional but user-surprising) | F-02, F-06 | Log run outcome clearly; consider UI note showing last run timestamp |
| Missing/incorrect exchange in `tickers` breaks TradingView links | F-03, F-07 | Validate all active tickers have `exchange` before each run |
| No retry policy increases warning runs | F-01, F-02 | Log failures clearly; retry is out of scope for v1 |
| Strict latest-version rule may show empty UI after bad run | F-04, F-06 | Ensure empty-state message is informative; operational review via logs |

