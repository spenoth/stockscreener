# Functional Specification: Wave 1 — Solid Foundation (Backend Data Layer)

**Project:** Weekly Stock Screener  
**Wave:** 1  
**Document Type:** Functional Specification  
**Date:** 2026-06-03  
**Status:** Draft  
**Source Documents:** business-requirements.md, development-roadmap.md, wave1-feature-specifications.md

---

## 1. Purpose

Wave 1 establishes the reliable data foundation on which all subsequent waves depend. The purpose of this wave is to ensure:

- The BMSB screener runs end-to-end without silent failures and produces a complete, auditable record of every ticker it processes.
- Each screener run is classified by outcome so the operator can assess data reliability at a glance.
- Exchange master data is complete and consistent in the `tickers` table, enabling accurate TradingView link construction in a future wave.
- A single, authoritative, versioned query exists that defines "current passing stocks" — the core data contract consumed by middleware in Wave 2.

Without Wave 1, the screener produces unreliable and undiagnosable output, exchange data is incomplete, and no safe contract exists for downstream consumers.

---

## 2. Scope

### In Scope

| Feature | Description |
|---------|-------------|
| F-01 — Per-Ticker Scan Logging | Structured log output for every ticker processed in a screener run |
| F-02 — Run Outcome Classification | Per-run outcome (`success` / `warning` / `error`) persisted to `watchlist_versions` |
| F-03 — Exchange Data Completeness | All active tickers in `tickers` have a valid, non-null `exchange` value |
| F-04 — Latest-Version Canonical Query | A database view (`quant.v_current_bmsb`) returning the current passing stocks for the most recent version |

### Out of Scope

See Section 9.

---

## 3. Inputs

### 3.1 Ticker Universe

- **Source:** `quant.tickers` table
- **Filter:** `active = true`
- **Fields used:** `symbol`, `exchange`
- **Precondition:** All rows where `active = true` must have a non-null, non-empty `exchange` value before a run is considered valid (enforced by F-03).

### 3.2 Market Data

- **Source:** Alpaca Markets Historical Data API
- **Credentials:** API key and secret stored in `config.py`
- **Data type:** Weekly OHLCV bar data for each ticker
- **Lookback window:** Approximately 55 weeks prior to the run date
- **Delivery format:** Time-series bars per symbol, consumed directly in the screener script

### 3.3 Screener Run Trigger

- **Trigger type:** Manual execution (no scheduler in Wave 1)
- **Execution environment:** Local IDE terminal or Docker container
- **Entry point:** `bmsb_above_screener.py`

### 3.4 Database State

- **Preconditions:**
  - A `quant.watchlists` row with `name = 'BMSB_ABOVE'` must exist.
  - `quant.watchlist_versions`, `quant.watchlist_items`, and `quant.tickers` tables must be present and accessible.
  - Database connection parameters are resolved via `config.py` or environment variables.

---

## 4. Outputs

### 4.1 Per-Ticker Log Entries (F-01)

For every ticker in the active universe, exactly one structured log line is emitted per run. Each log entry contains:

| Field | Description |
|-------|-------------|
| `run_timestamp` | UTC timestamp of the run start |
| `symbol` | Ticker symbol being processed |
| `scan_status` | One of: `attempted`, `succeeded`, `failed` |
| `pass_result` | One of: `pass`, `fail`, or absent if `scan_status = failed` |
| `error_message` | Exception message, populated only when `scan_status = failed` |

Log output is written to stdout and is visible in both local IDE terminal and Docker container logs.

### 4.2 Watchlist Version Row (F-02)

A new row is inserted into `quant.watchlist_versions` for every run, regardless of outcome. The row includes:

| Field | Description |
|-------|-------------|
| `watchlist_id` | FK to `quant.watchlists` (`BMSB_ABOVE`) |
| `version` | Auto-incremented version number |
| `created_at` | UTC timestamp of version creation |
| `run_outcome` | One of: `success`, `warning`, `error` (new column — F-02) |
| `total_tickers` | Count of tickers in input universe (new column or log — F-02) |
| `scanned_count` | Count of tickers successfully scanned (new column or log — F-02) |
| `failed_count` | Count of tickers that failed to scan (new column or log — F-02) |

### 4.3 Watchlist Item Rows

For each ticker that passes the BMSB criteria in a given run, one row is inserted into `quant.watchlist_items`:

| Field | Description |
|-------|-------------|
| `watchlist_version_id` | FK to the version row for this run |
| `ticker` | Passing stock symbol |

No `exchange` column is added to `watchlist_items`; exchange is sourced from `quant.tickers` at query time.

### 4.4 Current BMSB View (`quant.v_current_bmsb`) (F-04)

A database view that returns the current list of passing stocks. Output columns:

| Column | Source |
|--------|--------|
| `symbol` | `quant.watchlist_items.ticker` |
| `exchange` | `quant.tickers.exchange` (joined via `symbol`) |

The view always reflects the most recently created `watchlist_version` for the `BMSB_ABOVE` watchlist.

---

## 5. Business Rules

### BR-1 — Every Ticker Must Be Logged (F-01)

Every ticker returned by the active ticker query must produce exactly one log entry per run. No ticker may be silently skipped. If a ticker is not scanned for any reason, a `failed` log entry with an explanatory message is required.

### BR-2 — Exception Isolation (F-01)

A scan failure for one ticker must not halt the run. The exception is caught, logged with its message, and the run proceeds to the next ticker.

### BR-3 — Version Row Always Created (F-02)

A `watchlist_versions` row must be created at the start of every run, before any ticker is scanned. Even a run classified as `error` (0 tickers scanned) must produce a version row.

### BR-4 — Run Outcome Classification (F-02)

Run outcome is determined after all tickers have been processed:

| Condition | Outcome |
|-----------|---------|
| `scanned_count == total_tickers` | `success` |
| `0 < scanned_count < total_tickers` | `warning` |
| `scanned_count == 0` | `error` |

### BR-5 — Exchange Is Master Data (F-03)

Exchange is owned exclusively by `quant.tickers`. It must not be duplicated into `watchlist_items`. Any consumer needing exchange must join `quant.tickers` at query time.

### BR-6 — Active Tickers Must Have Exchange (F-03)

Before a run is considered valid, all rows in `quant.tickers` where `active = true` must have a non-null, non-empty `exchange` value. The valid exchange values in v1 are: `NYSE`, `NASDAQ`.

### BR-7 — Latest-Version Semantics (F-04)

"Latest version" is defined strictly as the `watchlist_versions` row with the most recent `created_at` timestamp (or highest `id` as surrogate) for the `BMSB_ABOVE` watchlist. There is no fallback to prior versions under any circumstances.

### BR-8 — Empty Result Is Valid (F-04)

If the latest version contains zero watchlist items, the canonical view must return an empty result set. Returning rows from a prior version is a correctness violation.

### BR-9 — Watchlist Scoping (F-04)

The canonical view is scoped exclusively to `BMSB_ABOVE`. Data from other watchlists must not appear in the view, regardless of how many watchlists exist in the database.

---

## 6. Data Requirements

### 6.1 Schema: `quant.tickers`

| Column | Type | Constraint | Notes |
|--------|------|-----------|-------|
| `id` | BIGSERIAL | PK | — |
| `symbol` | TEXT | NOT NULL, UNIQUE | Ticker symbol |
| `name` | TEXT | — | Company name |
| `active` | BOOLEAN | DEFAULT TRUE | Only `active = true` tickers are scanned |
| `exchange` | TEXT | Must be non-null for active rows | `NYSE` or `NASDAQ` in v1 |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | — |

### 6.2 Schema: `quant.watchlists`

| Column | Type | Constraint | Notes |
|--------|------|-----------|-------|
| `id` | BIGSERIAL | PK | — |
| `name` | TEXT | NOT NULL, UNIQUE | `BMSB_ABOVE` must exist |

### 6.3 Schema: `quant.watchlist_versions` (with Wave 1 additions)

| Column | Type | Constraint | Notes |
|--------|------|-----------|-------|
| `id` | BIGSERIAL | PK | — |
| `watchlist_id` | BIGINT | FK → watchlists | — |
| `version` | BIGINT | NOT NULL | Auto-incremented per watchlist |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Determines "latest" |
| `run_outcome` | TEXT | — | **New — F-02:** `success` / `warning` / `error` |
| `total_tickers` | INTEGER | — | **New — F-02:** Input universe size |
| `scanned_count` | INTEGER | — | **New — F-02:** Tickers successfully scanned |
| `failed_count` | INTEGER | — | **New — F-02:** Tickers that failed |

### 6.4 Schema: `quant.watchlist_items`

| Column | Type | Constraint | Notes |
|--------|------|-----------|-------|
| `id` | BIGSERIAL | PK | — |
| `watchlist_version_id` | BIGINT | FK → watchlist_versions | — |
| `ticker` | TEXT | NOT NULL | Passing symbol |

> **Note:** No `exchange` column is added to this table (BR-5).

### 6.5 View: `quant.v_current_bmsb` (F-04)

Defined in `init.sql` (the single source of truth for schema). Returns `symbol` and `exchange` for all items in the most recently created `watchlist_version` for `BMSB_ABOVE`.

### 6.6 Exchange Reference Values

The following exchange values are valid in v1:

| Value | Description |
|-------|-------------|
| `NYSE` | New York Stock Exchange |
| `NASDAQ` | NASDAQ Stock Market |

---

## 7. Error Handling

### 7.1 Ticker-Level Scan Failure (F-01)

| Scenario | Handling |
|----------|----------|
| Alpaca API call raises an exception | Catch exception; log `scan_status = failed` with `error_message`; continue to next ticker |
| Market data returned is empty or insufficient | Treat as a failed scan; log reason; continue |
| Indicator calculation fails | Catch exception; log `scan_status = failed`; continue |

### 7.2 Database Errors

| Scenario | Handling |
|----------|----------|
| Cannot connect to PostgreSQL | Run aborts before creating a version row; error written to stdout |
| `watchlist_versions` insert fails | Run aborts; no version row exists; error written to stdout |
| `watchlist_items` insert fails for one ticker | Log the failure; continue; the version row is preserved |

### 7.3 Missing Exchange Data (F-03)

| Scenario | Handling |
|----------|----------|
| Active ticker has null `exchange` | The data-fix script (committed to repo) must resolve this before a production run; a verification query must confirm zero violations |
| Exchange value is outside valid set | Flagged by the verification query; treated as a data quality issue requiring manual correction |

### 7.4 Run Outcome Classification Failures (F-02)

| Scenario | Handling |
|----------|----------|
| `run_outcome` cannot be determined | Default to `error`; counts are still written to log |
| `watchlist_versions` update for outcome fails | Log the error to stdout; the version row and any item rows are preserved |

### 7.5 Empty Latest Version (F-04)

| Scenario | Handling |
|----------|----------|
| Latest version has zero items | `quant.v_current_bmsb` returns an empty result set — not an error condition |
| No version exists at all | View returns an empty result set |

---

## 8. Acceptance Criteria

### F-01 — Per-Ticker Scan Logging

1. For every ticker where `active = true`, exactly one log line is produced per run.
2. Each log line contains: run timestamp, symbol, `scan_status` (`attempted` / `succeeded` / `failed`), and `pass_result` (`pass` / `fail`) when `scan_status = succeeded`.
3. When a ticker scan raises an exception, the exception message is captured in the log and the run continues.
4. No ticker produces zero log lines — a skipped ticker must appear as `failed` with a reason.
5. Log output is visible in local IDE terminal and Docker container stdout.

### F-02 — Run Outcome Classification

1. After every run, `total_tickers`, `scanned_count`, and `failed_count` are available (persisted on version row or written to structured log).
2. `run_outcome` is determined by the rules in BR-4 and persisted on the `watchlist_versions` row.
3. A run with `scanned_count == 0` still creates a version row and is classified as `error`.
4. `run_outcome` column exists on `watchlist_versions` and is populated for every run.

### F-03 — Exchange Data Completeness

1. All rows in `quant.tickers` where `active = true` have a non-null, non-empty `exchange` value.
2. A verification query exists and returns count = 0 for active tickers with null/empty exchange.
3. `exchange` is not present in `quant.watchlist_items`.
4. Any data-fix or seed script used to populate exchanges is committed to the repository.

### F-04 — Latest-Version Canonical Query

1. `quant.v_current_bmsb` exists in the database (defined in `tools.sql` or a migrations file).
2. The view returns `symbol` and `exchange` for all items in the most recently created `watchlist_version` for `BMSB_ABOVE`.
3. When the latest version has zero items, the view returns an empty result set (not rows from a prior version).
4. When multiple watchlists exist, the view returns only `BMSB_ABOVE` data.
5. The view is validated against the live database after at least one full screener run.

---

## 9. Out of Scope

The following items are explicitly excluded from Wave 1:

| Item | Reason / Wave |
|------|---------------|
| REST API / middleware endpoint | Wave 2 (FEATURE-05) |
| Angular frontend | Wave 3 (FEATURE-06, FEATURE-07) |
| TradingView link construction | Wave 3 (FEATURE-07) |
| Scheduled / automated run trigger | Wave 4 |
| Authentication or access control | Out of scope for v1 entirely |
| Retry logic for failed tickers | Out of scope for v1 |
| Multi-user support | Out of scope for v1 |
| Additional screeners beyond `BMSB_ABOVE` | Wave 4 / future |
| Email or push notifications | Out of scope for v1 |
| UI display of `run_outcome` | Wave 3+ (operational/diagnostic only in v1) |
| Historical run comparison or trend analysis | Out of scope for v1 |

---

## 10. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | Should `total_tickers`, `scanned_count`, and `failed_count` be persisted as columns on `watchlist_versions`, or is structured log output sufficient for v1? | Project owner | Open |
| OQ-2 | Is the BMSB formula implementation in the existing `bmsb_above_screener.py` accepted as the definitive business logic baseline for v1, or does it require review? | Project owner | Open |
| OQ-3 | What is the exact weekly run trigger mechanism for Wave 1 — purely manual, or is a simple cron/task scheduler needed sooner than Wave 4? | Project owner | Open |
| OQ-4 | Should the data-fix script for exchange population be idempotent (safe to re-run), and should it replace `init.sql` seed data or exist as a separate one-time migration? | Project owner | Open |
| OQ-5 | Are `NYSE` and `NASDAQ` the complete set of valid exchange values for all active tickers in the initial universe, or are other exchanges (e.g., `AMEX`, `BATS`) possible? | Project owner | Open |
| OQ-6 | If a ticker is present in the input universe but Alpaca returns no data for it (symbol not found), should it be logged as `failed` with a "no data" reason, or removed from `tickers.active`? | Project owner | Open |
| OQ-7 | Should `quant.v_current_bmsb` be defined in `tools.sql` alongside existing tooling SQL, or in a dedicated `migrations/` file for cleaner change tracking? | Project owner | Open |

