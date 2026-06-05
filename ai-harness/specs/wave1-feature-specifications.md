# Wave 1 — Feature Specifications: Solid Foundation (Backend Data Layer)

**Project:** Weekly Stock Screener  
**Wave:** 1  
**Date:** 2026-06-03  
**Goal:** Make the screener run reliably end-to-end and persist clean, queryable data.

---

## Overview

Wave 1 contains 4 independently implementable features. Together they satisfy Milestones M1 and M2. They must be delivered in order because each feature builds on the previous one.

| # | Feature | Priority | Depends On |
|---|---------|----------|------------|
| F-01 | Per-Ticker Scan Logging | 1 — Highest | None |
| F-02 | Run Outcome Classification | 2 | F-01 |
| F-03 | Exchange Data Completeness & Propagation | 3 | None (parallel to F-01/F-02) |
| F-04 | Latest-Version Canonical Query | 4 | F-03 |

---

## F-01 — Per-Ticker Scan Logging

**Purpose**  
Every ticker processed by the BMSB screener must produce a log record so the operator can diagnose why a symbol is missing from results. Currently the screener silently skips or swallows errors, making debugging impossible.

**Dependencies**  
- `bmsb_above_screener.py` (existing)  
- `config.py` — single configuration module holding both Alpaca Markets API credentials and PostgreSQL connection parameters  
- No schema changes required

**Acceptance Criteria**  
1. For every ticker in the input universe, exactly one log line is produced per run.  
2. Each log line contains: run timestamp, symbol, scan status (`attempted` / `succeeded` / `failed`), and pass/fail result (when status is `succeeded`).  
3. When a ticker scan raises an exception, the exception message is captured and logged; the run continues to the next ticker.  
4. No ticker is silently skipped — if a ticker is not scanned, a `failed` entry must be logged with a reason.  
5. Log output is visible in both IDE terminal and Docker container stdout.

**Implementation Priority:** 1 — Implement first; all other Wave 1 features depend on scan reliability.

---

## F-02 — Run Outcome Classification

**Purpose**  
Each screener run must be classifiable as `success`, `warning`, or `error` based on how many tickers were actually scanned versus attempted. This enables the operator to quickly understand the reliability of a given run without inspecting individual ticker logs.

**Dependencies**  
- F-01 must be in place (scan counts are derived from F-01 log counters)  
- `watchlist_versions` table (existing)

**Acceptance Criteria**  
1. After every run, the following counts are available: `total_tickers`, `scanned_count`, `failed_count`.  
2. Run outcome is determined by the following rules:  
   - `success`: `scanned_count == total_tickers`  
   - `warning`: `0 < scanned_count < total_tickers`  
   - `error`: `scanned_count == 0`  
3. The outcome value (`success` / `warning` / `error`) is persisted on the `watchlist_versions` row for that run (requires adding a `run_outcome` column to `watchlist_versions`).  
4. The counts (`total_tickers`, `scanned_count`, `failed_count`) are also persisted on or alongside the version row, or written to structured log output.  
5. A run classified as `error` still creates a version row (no silent abort).

**Implementation Priority:** 2 — Implement after F-01.

---

## F-03 — Exchange Data Completeness & Propagation

**Purpose**  
The Angular UI must display the exchange for each passing stock (required for TradingView link construction). Exchange is master data owned by the `tickers` table. This feature ensures all active tickers have a valid `exchange` value before the screener runs, and confirms the data is correctly joinable at query time — no duplication into `watchlist_items` is needed.

**Dependencies**  
- `tickers` table with `exchange` column (column already exists per roadmap)  
- Access to seed/fixture data or a one-time data fix script  
- No dependency on F-01 or F-02 (can be worked in parallel)

**Acceptance Criteria**  
1. All rows in `tickers` where `active = true` have a non-null, non-empty `exchange` value.  
2. The set of valid exchange values is defined and documented (at minimum: `NYSE`, `NASDAQ`).  
3. A verification query exists that returns a count of active tickers with null or empty exchange; that count must be 0 before Wave 1 is considered done.  
4. `exchange` is NOT duplicated into `watchlist_items`; it is sourced exclusively from `tickers` at query time via join.  
5. Any data-fix or seed script used to populate exchanges is committed to the repository.

**Implementation Priority:** 3 — Can be done in parallel with F-01/F-02, but must be complete before F-04.

---

## F-04 — Latest-Version Canonical Query

**Purpose**  
Define, test, and encapsulate the single authoritative query that returns the current list of passing stocks. This query is the core data contract of the entire system — it will be called by the middleware (Wave 2) and must behave correctly under all edge cases including empty runs and multi-screener scenarios.

**Dependencies**  
- F-03 (exchange must be populated and joinable from `tickers`)  
- `watchlist_versions` and `watchlist_items` tables (existing)  
- `watchlists` table with at least one `BMSB_ABOVE` watchlist row

**Acceptance Criteria**  
1. The query returns columns: `symbol`, `exchange` for all items belonging to the most recently created `watchlist_version` for watchlist `BMSB_ABOVE`.  
2. "Most recently created" is defined strictly by `watchlist_versions.created_at` descending (or equivalent surrogate key); no fallback to prior versions is permitted.  
3. When the latest version contains zero items, the query returns an empty result set — not an error, not a row from a prior version.  
4. When multiple watchlists exist (future extensibility), the query is correctly scoped to `BMSB_ABOVE` only and does not bleed data across screeners.  
5. The query is encapsulated as a database view named `quant.v_current_bmsb` defined in `init.sql` (the single source of truth for all schema objects).  
6. The view is validated by running it against the live database after at least one full screener run; results are manually verified to match expected passing symbols.

**Implementation Priority:** 4 — Implement last in Wave 1; depends on F-03 and benefits from F-01/F-02 run data.

---

## Wave 1 Definition of Done

Wave 1 is complete when all of the following are true:

- [ ] Every screener run produces a per-ticker log entry with symbol, status, and pass/fail.
- [ ] Every screener run persists a `run_outcome` value (`success` / `warning` / `error`) on its version row.
- [ ] All active tickers in `tickers` have a non-null `exchange` value.
- [ ] `quant.v_current_bmsb` view exists, returns `symbol` + `exchange` from latest version only, and returns empty set when latest version has no items.
- [ ] A full end-to-end run can be executed locally and in Docker, producing verifiable output in the database.

