# Functional & Technical Specification: Wave 2 — API Layer (Middleware)

**Project:** Weekly Stock Screener  
**Wave:** 2  
**Document Type:** Functional & Technical Specification  
**Date:** 2026-06-04  
**Status:** Draft  
**Source Documents:** business-requirements.md, development-roadmap.md, wave1-feature-specifications.md, wave2-feature-specifications.md

---

## 1. Purpose

Wave 2 introduces the HTTP middleware layer that bridges the PostgreSQL data store (built in Wave 1) and the Angular client (built in Wave 3). Its sole responsibility is to expose the screener's current results as a stable, structured REST API.

The Wave 2 API layer must:

- Provide a reliable, machine-readable endpoint that reflects the latest-version semantics defined in Wave 1 (BR-4, F-04).
- Return structured JSON in all cases — including error conditions — so the Angular client never receives unstructured HTML or Python tracebacks.
- Run identically in both a local development environment and a Dockerised container.
- Be independently testable, with a clear health-check signal so dependent systems can confirm availability.

Without Wave 2, the Angular client has no data source. Wave 2 is the prerequisite for Wave 3 and is the first externally observable surface of the system.

---

## 2. Scope

### 2.1 In Scope

| Feature | Description |
|---------|-------------|
| F-05 — FastAPI Project Scaffold | Project layout, dependency management, configuration, database wiring, and health-check route |
| F-06 — Current Results Endpoint | `GET /api/screener/bmsb/current` returning the latest-version passing stocks |
| F-07 — Error Handling & Response Contract | Structured JSON error responses for all failure modes; consistent `Content-Type` |
| F-08 — Docker Integration for API Service | Dockerfile for the API service; API service added to `docker-compose.yaml` |

### 2.2 Out of Scope

The following are explicitly excluded from Wave 2:

- Authentication, authorisation, and any security hardening (v1 scope, BRS Section 4)
- Caching or response memoisation at the API layer
- Write endpoints (the API is read-only in Wave 2)
- Endpoints for any screener other than BMSB
- Historical version queries (Wave 2 exposes only the latest version)
- Angular client code (Wave 3)
- Scheduling or automated run triggering (Wave 4)
- Rate limiting or request throttling
- API versioning (beyond the `/api/` path prefix)

---

## 3. Inputs

### 3.1 Database State (prerequisite)

Wave 2 requires a fully operational Wave 1 data layer. The following preconditions must be satisfied before any Wave 2 endpoint can return meaningful data:

| Precondition | Source | Notes |
|---|---|---|
| `quant.watchlists` row with `name = 'BMSB_ABOVE'` exists | Wave 1 schema | Required for version scoping |
| `quant.watchlist_versions` table exists and is populated | Wave 1 F-02 | At least one version must exist to return data |
| `quant.watchlist_items` table exists | Wave 1 schema | May be empty; empty result is valid |
| `quant.tickers` table exists with non-null `exchange` for active rows | Wave 1 F-03 | Required for the `exchange` field in the response |
| `quant.v_current_bmsb` view exists and is correct | Wave 1 F-04 | The API queries this view; if the view is absent, the query must replicate its logic directly |

If any precondition is not met, the endpoint may return an empty array or a `503` error depending on the nature of the failure — see Section 7.

### 3.2 HTTP Request

The API accepts HTTP GET requests. No request body is expected. No query parameters are defined for Wave 2 endpoints.

**Health-check endpoint:**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/health` |
| Request body | None |
| Authentication | None |

**Current results endpoint:**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/screener/bmsb/current` |
| Request body | None |
| Authentication | None |

### 3.3 Configuration Inputs

The API service resolves all runtime configuration from environment variables, with fallback to local-development defaults. The following values are required:

| Variable | Description | Default (local dev) |
|---|---|---|
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | (project-specific) |
| `DB_USER` | Database username | (project-specific) |
| `DB_PASSWORD` | Database password | (project-specific) |
| `API_PORT` | Port on which the API listens | `8000` |

Configuration is managed by a dedicated file within the `api/` directory. This file is the single source of truth for the API service and must not import from or depend on the screener's root-level `config.py`.

---

## 4. Outputs

### 4.1 Health-Check Response

**Success (database reachable, service running):**

- HTTP status: `200 OK`
- `Content-Type`: `application/json`
- Body:

```json
{ "status": "ok" }
```

### 4.2 Current Results Response — Happy Path

**Request:** `GET /api/screener/bmsb/current`

**Success — stocks present:**

- HTTP status: `200 OK`
- `Content-Type`: `application/json`
- Body: a JSON array of stock objects

```json
[
  { "symbol": "AAPL", "exchange": "NASDAQ" },
  { "symbol": "JPM",  "exchange": "NYSE"   }
]
```

**Success — no stocks in latest version:**

- HTTP status: `200 OK`
- `Content-Type`: `application/json`
- Body: empty JSON array

```json
[]
```

> **Rule:** An empty result is a valid business outcome (BRS BR-4, BR-6). The endpoint must never return `404` or any error status when the latest version simply has no passing stocks.

### 4.3 Response Object Schema

Each element in the results array conforms to the following schema:

| Field | Type | Nullable | Source |
|---|---|---|---|
| `symbol` | `string` | No | `quant.watchlist_items.ticker` |
| `exchange` | `string` | No | `quant.tickers.exchange` (joined at query time) |

No additional fields are included in Wave 2. The schema is intentionally minimal to match the Angular client's data contract (BRS BR-5).

### 4.4 Error Responses

All error responses use a consistent JSON envelope:

```json
{ "detail": "<human-readable message>" }
```

| Condition | HTTP Status | `detail` value |
|---|---|---|
| Database unreachable | `503 Service Unavailable` | `"Database unavailable"` |
| Unexpected server error | `500 Internal Server Error` | `"Internal server error"` |
| Path not found | `404 Not Found` | `"Not Found"` (framework default) |

Full stack traces are written to server-side logs only. They must never appear in the response body.

---

## 5. Business Rules

### BR-W2-1 — Latest-Version Semantics Must Be Preserved

The endpoint must always reflect the most recently created `watchlist_versions` row for the `BMSB_ABOVE` watchlist. It must not fall back to a prior version if the latest version has zero items. This is a direct enforcement of BRS BR-4 and Wave 1 F-04.

### BR-W2-2 — Empty Result Is Not an Error

When the latest version has zero passing stocks, the endpoint returns `200` with an empty array. This is the correct business response, not a failure mode. It is the API's responsibility to signal this distinction clearly to the Angular client (BRS BR-6).

### BR-W2-3 — No Response Caching

Each request to `GET /api/screener/bmsb/current` must trigger a live database query. No in-process caching, HTTP-level cache headers that permit stale reads, or memoisation of results is permitted in Wave 2. This ensures the client always receives data consistent with the most recent screener run (BRS BR-4, NFR-4).

### BR-W2-4 — Exchange Is Sourced from Master Data

The `exchange` field in the response must be derived from `quant.tickers.exchange` at query time. It must not be hardcoded, derived algorithmically, or sourced from any field other than the `tickers` master data table (Wave 1 BR-5, F-03).

### BR-W2-5 — BMSB Scoping

The endpoint is scoped exclusively to the `BMSB_ABOVE` watchlist. Data from other watchlists, should they exist, must never appear in the response.

### BR-W2-6 — Structured Errors in All Code Paths

No Python exception, traceback, or unstructured error may reach the HTTP response. Every error path — including database connectivity failures and unexpected runtime exceptions — must be caught and translated to the standard JSON error envelope defined in Section 4.4.

### BR-W2-7 — Health-Check Independence

The `GET /health` endpoint must remain operational regardless of screener-specific errors. Its availability must not be affected by a database outage or a malformed screener query. It is the only endpoint whose behaviour under a database-unavailable condition may differ from the main results endpoint (i.e. it may still return `200` if the service process itself is running, even when the database is down — this is acceptable for Wave 2).

### BR-W2-8 — Consistent Content-Type

Every response, including all error responses, must carry the `Content-Type: application/json` header.

---

## 6. Data Requirements

### 6.1 Query Contract

The API's current results endpoint must produce data equivalent to the following logical query, regardless of whether it uses the `quant.v_current_bmsb` view directly or replicates the logic inline:

```
For the BMSB_ABOVE watchlist:
  1. Identify the single watchlist_versions row with the most recent created_at.
  2. Return all watchlist_items rows linked to that version.
  3. For each item, join quant.tickers on symbol to retrieve exchange.
  4. Return symbol and exchange for each row.
  5. If no rows exist, return an empty set.
```

The canonical view from Wave 1 (`quant.v_current_bmsb`) is the preferred data source if it exists and is correct. The API must not duplicate the "latest version" selection logic unless the view is absent.

### 6.2 Database Access Pattern

| Property | Value |
|---|---|
| Access type | Read-only (`SELECT` only) |
| Transactions | Not required (single `SELECT`) |
| Connection management | One connection opened on startup; reused per request |
| Failure handling | On connection failure, return `503`; log the error server-side |

### 6.3 Database Tables and Views Consumed

| Object | Access Type | Purpose |
|---|---|---|
| `quant.v_current_bmsb` | `SELECT` | Primary data source for results endpoint |
| `quant.tickers` | `SELECT` (fallback join) | Exchange master data if not already in view |
| `quant.watchlist_versions` | `SELECT` (fallback) | Latest-version resolution if view absent |
| `quant.watchlist_items` | `SELECT` (fallback) | Items for latest version if view absent |

### 6.4 Connection Configuration

All database connection parameters are sourced from the API service's own configuration file (see Section 3.3). The database user used by the API service requires only `SELECT` privileges on the `quant` schema objects listed in Section 6.3.

---

## 7. Error Handling

### 7.1 Error Taxonomy

| Error Class | Trigger | Response | Log Level |
|---|---|---|---|
| Database connectivity failure | Cannot establish or use DB connection at request time | `503` with `{ "detail": "Database unavailable" }` | `ERROR` |
| Query execution failure | SQL error during the `SELECT` (e.g. view missing, schema mismatch) | `500` with `{ "detail": "Internal server error" }` | `ERROR` |
| Unexpected runtime exception | Any unhandled Python exception during request processing | `500` with `{ "detail": "Internal server error" }` | `ERROR` |
| Unknown route | Request to an undefined path | `404` with `{ "detail": "Not Found" }` | `WARNING` |
| Method not allowed | Non-GET request to a defined path | `405` with `{ "detail": "Method Not Allowed" }` | `WARNING` |

### 7.2 Startup Failure

If the application cannot open a database connection on startup, it must:

1. Log a clear, human-readable error message identifying the connection failure and the configured host/port.
2. Prevent the service from accepting requests (i.e. not start the HTTP listener in a silently broken state).

This ensures that a misconfigured or unreachable database does not result in a running service that silently returns empty or malformed data.

### 7.3 Request-Time Database Failure

If the database was reachable at startup but becomes unreachable during a request:

1. The exception is caught at the endpoint handler level.
2. A `503 Service Unavailable` response is returned with the standard JSON envelope.
3. The exception message and stack trace are written to server logs at `ERROR` level.
4. The service continues running and accepts subsequent requests (it does not crash or restart).

### 7.4 Log Requirements

Every error logged at request time must include:

| Field | Description |
|---|---|
| Timestamp | UTC timestamp of the error |
| Endpoint | The request path that triggered the error |
| Error class | Exception type or category |
| Error message | Human-readable description |
| Stack trace | Full Python traceback (server logs only, not in response) |

---

## 8. Acceptance Criteria

The following acceptance criteria define the complete, verifiable definition of done for Wave 2. All criteria must pass before Wave 2 is considered complete and Wave 3 may begin.

### F-05 — FastAPI Project Scaffold

| # | Criterion |
|---|---|
| AC-05-1 | An `api/` directory exists at the project root containing at minimum `main.py`, `requirements.txt`, and a dedicated configuration file (`config.py` or `settings.py`). |
| AC-05-2 | `requirements.txt` lists at minimum `fastapi` and `uvicorn` as dependencies. |
| AC-05-3 | The configuration file reads all DB and API port values from environment variables, with fallback defaults for local development. It does not import from the root-level `config.py`. |
| AC-05-4 | Running `uvicorn main:app --reload` from the `api/` directory starts the service without errors. |
| AC-05-5 | `GET /health` returns `200 OK` with body `{ "status": "ok" }`. |
| AC-05-6 | The application attempts a PostgreSQL connection on startup using the values from its configuration file. |
| AC-05-7 | A startup failure due to an unreachable database logs a clear error message and prevents request handling. |
| AC-05-8 | An empty test file in the `api/` directory passes with `pytest` (the project is importable and testable). |

### F-06 — Current Results Endpoint

| # | Criterion |
|---|---|
| AC-06-1 | `GET /api/screener/bmsb/current` returns `200 OK` with a JSON array when the latest version contains passing stocks. |
| AC-06-2 | Each object in the array contains exactly `symbol` (string) and `exchange` (string). |
| AC-06-3 | When the latest version has zero items, the endpoint returns `200 OK` with an empty array `[]`. |
| AC-06-4 | The endpoint never returns `404` or any `5xx` status as a result of an empty latest version. |
| AC-06-5 | Results are always drawn from the single most recent `watchlist_version` row for `BMSB_ABOVE`; older versions are never included. |
| AC-06-6 | Each call to the endpoint triggers a live database query; no stale cached result is returned. |
| AC-06-7 | A manual test (e.g. `curl` or browser) against a running local instance with seeded data returns the expected payload. |
| AC-06-8 | An automated test (pytest + `httpx` or `TestClient`) covers the happy path (stocks present) and the empty-result case, and both pass. |

### F-07 — Error Handling & Response Contract

| # | Criterion |
|---|---|
| AC-07-1 | When the database is unreachable at request time, `GET /api/screener/bmsb/current` returns `503` with body `{ "detail": "Database unavailable" }`. |
| AC-07-2 | When an unexpected server-side exception occurs, the endpoint returns `500` with body `{ "detail": "Internal server error" }`. |
| AC-07-3 | No Python stack trace or unstructured text appears in any HTTP response body. |
| AC-07-4 | Every response (success and error) carries the `Content-Type: application/json` header. |
| AC-07-5 | All error responses use the uniform JSON shape `{ "detail": "<message>" }`. |
| AC-07-6 | An automated test covering the database-unavailable scenario (DB call mocked/patched) asserts the `503` response shape and passes. |
| AC-07-7 | `GET /health` continues to return `200 OK` and is unaffected by screener-specific failures. |

### F-08 — Docker Integration for API Service

| # | Criterion |
|---|---|
| AC-08-1 | A `Dockerfile` for the API service exists within or alongside the `api/` directory and builds successfully (`docker build` exits `0`). |
| AC-08-2 | No credentials or environment-specific values are hardcoded in the `Dockerfile`. |
| AC-08-3 | The API service is added to `docker-compose.yaml` as a named service (e.g. `api`). |
| AC-08-4 | The `api` service declares `depends_on: db` in `docker-compose.yaml`. |
| AC-08-5 | All DB credentials and the API port are supplied to the `api` service via environment variables in `docker-compose.yaml` (or a `.env` file). |
| AC-08-6 | `docker-compose up` starts both the `db` and `api` services without manual intervention. |
| AC-08-7 | `GET /health` is reachable from the host at `http://localhost:{API_PORT}/health` after `docker-compose up`. |
| AC-08-8 | `GET /api/screener/bmsb/current` returns valid JSON when called from the host against the Dockerised stack. |
| AC-08-9 | The existing `db` service behaviour and the screener/ticker-loader scripts are unaffected by the addition of the `api` service. |

---

## 9. Out of Scope (Detailed)

The following items are explicitly excluded and must not be introduced in Wave 2:

| Item | Rationale |
|---|---|
| Authentication / API keys | Out of v1 scope (BRS Section 4) |
| HTTPS / TLS termination | Out of v1 scope |
| Write endpoints (POST, PUT, DELETE) | API is read-only; screener writes directly to DB |
| Query parameters / filters on results endpoint | Not required by Angular client in Wave 2 |
| Pagination | Ticker universe is small; not needed in v1 |
| Response caching (Redis, in-memory) | Violates BR-W2-3 / BRS NFR-4 |
| Historical version endpoint | Current-only contract is Wave 2's data contract |
| Multiple screener endpoints | Only BMSB is in scope for v1 |
| Swagger / OpenAPI UI customisation | Default FastAPI docs are acceptable |
| CI/CD pipeline setup | Wave 4 concern |

---

## 10. Dependencies and Prerequisites

| Dependency | Type | Status Required Before |
|---|---|---|
| Wave 1 fully merged (schema stable, all F-01 through F-04 complete) | Hard prerequisite | F-05 can begin |
| `quant.v_current_bmsb` view created and tested (Wave 1 F-04) | Hard prerequisite | F-06 can begin |
| All active tickers have non-null `exchange` (Wave 1 F-03) | Hard prerequisite | F-06 can be validated with real data |
| F-05 scaffold complete and runnable | Hard prerequisite | F-06, F-07, F-08 can begin |
| F-06 endpoint complete | Hard prerequisite | F-07 can begin |
| F-05 and F-06 complete | Hard prerequisite | F-08 can begin |

---

## 11. Definition of Done for Wave 2

Wave 2 is complete when all of the following are simultaneously true:

1. `GET /api/screener/bmsb/current` returns the correct payload from a local `uvicorn` process.
2. `GET /api/screener/bmsb/current` returns the correct payload from a Dockerised container.
3. The empty-result case returns `200` with `[]` — not an error — from both environments.
4. All error paths return `{ "detail": "..." }` JSON with the correct HTTP status code.
5. Automated tests for F-06 (happy path + empty result) and F-07 (DB-unavailable) pass locally with `pytest`.
6. `docker-compose up` starts the full stack (DB + API) without manual steps.
7. The existing `db` service and screener scripts are unaffected.
8. The Wave 3 (Angular) team can point their HTTP client at the containerised API and receive a valid JSON array.

