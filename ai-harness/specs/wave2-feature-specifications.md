# Wave 2 — Feature Specifications: API Layer (Middleware)

**Project:** Weekly Stock Screener  
**Wave:** 2  
**Date:** 2026-06-04  
**Goal:** Expose screener results over HTTP so the Angular client can consume them.

---

## Overview

Wave 2 contains 4 independently implementable features. Together they satisfy Milestone M3. Feature F-05 is the primary deliverable; the remaining features harden and operationalise it.

| # | Feature | Priority | Depends On |
|---|---------|----------|------------|
| F-05 | FastAPI Project Scaffold | 1 — Highest | Wave 1 complete |
| F-06 | Current Results Endpoint | 2 | F-05 |
| F-07 | Error Handling & Response Contract | 3 | F-06 |
| F-08 | Docker Integration for API Service | 4 | F-05, F-06 |

---

## F-05 — FastAPI Project Scaffold

**Purpose**  
Before any endpoint can be built, the API service needs a runnable skeleton: project layout, dependency management, application entry point, database connection wiring, and a health-check route. This feature has no business logic; its sole job is to make the foundation ready for feature work.

**Background: what is Uvicorn?**  
Uvicorn is the web server that runs the FastAPI application. It is the equivalent of what Apache or Nginx would be for a traditional web app — it listens on a port, accepts HTTP requests, and hands them to the FastAPI code. It is started from the command line and is listed as a dependency in `requirements.txt`.

**Dependencies**  
- Python environment already used by the screener scripts  
- Wave 1 must be fully merged (schema stable, `quant` schema accessible)

**Acceptance Criteria**  
- A `api/` directory (or equivalent) exists at the project root with its own `requirements.txt` listing at minimum `fastapi` and `uvicorn`  
- The `api/` directory contains its own dedicated configuration file (e.g. `api/config.py` or `api/settings.py`) that holds all values the API service needs: database host, port, name, user, password, and API server port. This file is the single source of truth for the API service — it does not import from or depend on the screener's root-level `config.py`  
- Configuration values are read from environment variables first, falling back to sensible local-development defaults, so the same config file works both locally and inside Docker  
- Running `uvicorn main:app --reload` (or equivalent) from the `api/` directory starts the service without errors  
- `GET /health` returns `200 OK` with a JSON body `{ "status": "ok" }`  
- The application opens a PostgreSQL connection using credentials from its own configuration file on startup; failure to connect logs a clear error and prevents startup  
- No business-logic endpoints are included in this feature  
- The scaffold is importable and testable (i.e. an empty test file passes with `pytest`)

**Implementation Priority:** 1 — Must be done first; all other Wave 2 features block on it.

---

## F-06 — Current Results Endpoint

**Purpose**  
Implement the single endpoint that constitutes the core business contract of Wave 2: return the list of stocks that passed the latest BMSB screener run, including their exchange, ready for the Angular client to display.

**Dependencies**  
- F-05 (scaffold must exist and be runnable)  
- Wave 1 F-04: the canonical latest-version query (or DB view `quant.v_current_bmsb`) must be in place and tested  
- Active tickers must have a non-null `exchange` value (Wave 1 F-03)

**Acceptance Criteria**  
- `GET /api/screener/bmsb/current` returns `200` with a JSON array of objects in the form `{ "symbol": "AAPL", "exchange": "NASDAQ" }`  
- When the latest watchlist version has zero items the endpoint returns `200` with an empty array `[]` — never a `404` or `500`  
- Results are always drawn from the single most recent `watchlist_version` row for `BMSB_ABOVE`; older versions are never returned  
- The endpoint does not cache results between requests (each call queries the database)  
- A manual test (e.g. `curl` or a browser request) against a running local instance with seeded data returns the expected payload  
- An automated test (pytest + `httpx` or `TestClient`) covering the happy path and the empty-result case exists and passes

**Implementation Priority:** 2 — Core deliverable of Wave 2; unblocks Wave 3.

---

## F-07 — Error Handling & Response Contract

**Purpose**  
Define and enforce how the API behaves when something goes wrong (database unreachable, unexpected query error, unknown screener name). Without this, the Angular client receives unstructured 500 HTML error pages and has no way to handle failures gracefully.

**Dependencies**  
- F-06 (endpoint must exist before error paths can be hardened)

**Acceptance Criteria**  
- If the database is unreachable at request time, the endpoint returns `503 Service Unavailable` with a JSON body `{ "detail": "Database unavailable" }` — never an unhandled Python traceback  
- If an unexpected server-side error occurs, the endpoint returns `500` with a JSON body `{ "detail": "Internal server error" }` — stack trace is written to server logs only, not to the response body  
- All error responses use the same JSON structure `{ "detail": "<message>" }` (consistent with FastAPI's default error format)  
- The `Content-Type` header is `application/json` for every response, including errors  
- Automated tests cover the database-unavailable scenario (mock/patch the DB call) and assert the `503` response shape  
- The health-check endpoint (`GET /health`) is unaffected by screener-specific errors

**Implementation Priority:** 3 — Required before the API is handed off to the Angular team; prevents silent failures in the UI.

---

## F-08 — Docker Integration for API Service

**Purpose**  
The API must run inside Docker alongside the existing PostgreSQL container so that the full stack (DB + screener + API) can be started with a single `docker-compose up` command. This is required for consistent local development and is the prerequisite for any future deployment or scheduling work.

**Dependencies**  
- F-05 (scaffold must be complete and the app must start cleanly)  
- F-06 (at least one real endpoint must exist to validate end-to-end connectivity inside Docker)  
- Existing `docker-compose.yaml` in `quant-db/`

**Acceptance Criteria**  
- A `Dockerfile` for the API service exists and builds successfully (`docker build` exits 0)  
- The API service is added to `docker-compose.yaml` as a named service (e.g. `api`)  
- The `api` service declares a dependency on the `db` service (`depends_on`) so startup order is correct  
- `docker-compose up` starts both the database and the API without manual intervention  
- `GET /health` is reachable from the host machine on the mapped port (e.g. `http://localhost:8000/health`) after `docker-compose up`  
- `GET /api/screener/bmsb/current` returns valid JSON when called from the host against the Dockerised stack  
- Environment variables for DB credentials are passed via `docker-compose.yaml` (or a `.env` file) — no credentials are hardcoded in the `Dockerfile`  
- The existing `db` service behaviour is unchanged (no regressions to screener or ticker-loader)

**Implementation Priority:** 4 — Required before Wave 3 begins; the Angular client needs a stable, containerised API to call.

---

## Summary Table

| # | Feature | Priority | Depends On | Milestone |
|---|---------|----------|------------|-----------|
| F-05 | FastAPI Project Scaffold | 1 — Highest | Wave 1 | M3 |
| F-06 | Current Results Endpoint | 2 | F-05, Wave 1 F-04 | M3 |
| F-07 | Error Handling & Response Contract | 3 | F-06 | M3 |
| F-08 | Docker Integration for API Service | 4 | F-05, F-06 | M3 |

---

## Definition of Done for Wave 2

Wave 2 is complete when all of the following are true:

- `GET /api/screener/bmsb/current` returns the correct payload from both a local `uvicorn` process and a Dockerised container  
- The empty-result case returns `[]` (not an error)  
- All error paths return structured JSON responses  
- Automated tests for F-06 and F-07 pass in CI / local `pytest` run  
- `docker-compose up` starts the full stack without manual steps  
- Wave 3 (Angular) team can point the client at the containerised API and receive data

