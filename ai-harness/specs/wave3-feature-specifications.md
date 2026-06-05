# Wave 3 — Feature Specifications: Angular Client (Frontend)

**Project:** Weekly Stock Screener  
**Wave:** 3  
**Date:** 2026-06-04  
**Goal:** Display current trade ideas in a browser with TradingView links.

---

## Overview

Wave 3 contains 6 independently implementable features. Together they satisfy Milestones M4 and M5. The features progress from project scaffolding, through data fetching and display, to TradingView integration and Docker packaging.

| # | Feature | Priority | Depends On | Milestone |
|---|---------|----------|------------|-----------|
| F-09 | Angular Project Scaffold | 1 — Highest | Wave 2 complete | M4 |
| F-10 | Screener API Service | 2 | F-09 | M4 |
| F-11 | Stock List Component | 3 | F-10 | M4 |
| F-12 | Empty-State Handling | 4 | F-11 | M4 |
| F-13 | TradingView Redirect Links | 5 | F-11 | M5 |
| F-14 | Docker Integration for Angular | 6 | F-11 | M4, M5 |

---

## F-09 — Angular Project Scaffold

**Purpose**  
Create the Angular project skeleton so that all subsequent UI features have a runnable foundation. This feature delivers no business logic — only a working shell that builds, serves, and is ready for component development.

**Dependencies**  
- Node.js / npm available in the development environment  
- Angular CLI installed (`@angular/cli`)  
- Wave 2 must be complete (API must be reachable)

**Acceptance Criteria**  
- An `angular-client/` directory (or equivalent) exists at the project root containing a standard Angular CLI-generated project  
- `ng serve` starts the development server without errors and renders a default page in the browser  
- `ng build` produces a production build without errors  
- The project uses a recent stable Angular version (v17+ or v18+)  
- A proxy configuration file (e.g. `proxy.conf.json`) is included that forwards `/api/*` requests to the API service (default `http://localhost:8000`) during local development  
- `ng serve` with the proxy config successfully proxies requests to the running API  
- The project includes a minimal `environment.ts` / `environment.prod.ts` setup with at least an `apiBaseUrl` property  
- Linting (`ng lint`) passes with zero errors on the scaffolded project  
- The default boilerplate content is removed or replaced with a minimal application shell (e.g. a page title "Stock Screener")

**Implementation Priority:** 1 — Must be done first; all other Wave 3 features block on it.

---

## F-10 — Screener API Service

**Purpose**  
Create an Angular service responsible for calling the API endpoint and returning typed data to components. This isolates HTTP concerns from presentation logic, making the codebase testable and maintainable.

**Dependencies**  
- F-09 (Angular project must exist and build)  
- Wave 2 F-06 endpoint `GET /api/screener/bmsb/current` must be deployed and returning data

**Acceptance Criteria**  
- A TypeScript interface (e.g. `Stock`) is defined with properties `symbol: string` and `exchange: string`  
- An injectable Angular service (e.g. `ScreenerService`) exists with a method that calls `GET /api/screener/bmsb/current` and returns an `Observable<Stock[]>`  
- The service uses Angular's `HttpClient`; `HttpClientModule` (or `provideHttpClient()`) is correctly configured  
- The service reads the API base URL from the environment configuration — no hardcoded URLs in the service file  
- A unit test exists that mocks `HttpClient` and verifies:  
  - The correct URL is called  
  - The response is correctly typed as `Stock[]`  
  - An empty array response is handled without error  
- The service compiles and all tests pass (`ng test --watch=false`)

**Implementation Priority:** 2 — Required before any component can display data.

---

## F-11 — Stock List Component

**Purpose**  
Display the list of stocks returned by the screener API in a clean, readable format. This is the primary UI deliverable of the entire project — the component that operators will use to see current trade ideas.

**Dependencies**  
- F-10 (ScreenerService must be available and tested)

**Acceptance Criteria**  
- A component (e.g. `StockListComponent`) exists and is rendered as the main content of the application  
- On initialisation, the component calls `ScreenerService` to fetch the current stock list  
- Each stock is displayed showing at minimum: **symbol** and **exchange**  
- The list is presented in a readable layout (table or card list — implementer's choice)  
- While data is loading, a loading indicator or message (e.g. "Loading…") is displayed  
- If the API call fails (network error, 5xx), an error message is displayed to the user (e.g. "Unable to load screener results. Please try again later.")  
- A unit test exists that verifies:  
  - The component renders stock data when the service returns results  
  - The loading state is shown before data arrives  
  - The error state is shown when the service call fails  
- All tests pass (`ng test --watch=false`)

**Implementation Priority:** 3 — Core UI deliverable; satisfies milestone M4.

---

## F-12 — Empty-State Handling

**Purpose**  
When the latest screener run produced zero passing stocks, the UI must show a clear, informational message instead of a blank screen. This prevents user confusion and satisfies the business requirement (BR-6) that the empty state is an expected, communicable outcome.

**Dependencies**  
- F-11 (StockListComponent must exist and handle API responses)

**Acceptance Criteria**  
- When the API returns an empty array `[]`, the stock list component displays an informational message: **"No stocks passed the latest screening. This may indicate market conditions did not meet the screener criteria."** (or similar approved wording — see OI-1)  
- The empty-state message is visually distinct from the error state (e.g. informational icon/colour vs. error icon/colour)  
- The empty state does not trigger a retry or redirect — it is treated as a valid, final state  
- A unit test exists that verifies the empty-state message is rendered when the service returns `[]`  
- The empty-state message is not shown while data is still loading  
- All tests pass (`ng test --watch=false`)

**Implementation Priority:** 4 — Required for M4 completion; ensures the UI is usable even when results are empty.

---

## F-13 — TradingView Redirect Links

**Purpose**  
Each stock in the list should link directly to its TradingView chart page, allowing the operator to quickly review the chart. The link is constructed from the stock's exchange and symbol.

**Dependencies**  
- F-11 (StockListComponent must be rendering stock rows)  
- Open Item OI-2 resolved: TradingView URL format confirmed as `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}`

**Acceptance Criteria**  
- Each stock row includes a clickable link (anchor tag or button) labelled with the symbol or a "View Chart" label  
- Clicking the link opens TradingView in a **new browser tab** (`target="_blank"`, `rel="noopener noreferrer"`)  
- The URL is constructed as `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}` (e.g. `https://www.tradingview.com/chart/?symbol=NASDAQ:TSLA`)  
- The link works correctly for both `NYSE` and `NASDAQ` exchange values  
- If a stock's `exchange` value is `null`, empty, or missing, the TradingView link is **not rendered** for that row; instead, only the symbol and exchange text are shown (graceful degradation, no broken links)  
- A unit test exists that verifies:  
  - The correct URL is generated for a stock with a known exchange  
  - No link is rendered when exchange is null or empty  
- All tests pass (`ng test --watch=false`)

**Implementation Priority:** 5 — Satisfies milestone M5; high user value but not blocking other features.

---

## F-14 — Docker Integration for Angular Client

**Purpose**  
The Angular client must be buildable as a Docker image and runnable alongside the existing API and database containers. This enables the full stack to be started with a single `docker-compose up` command and provides a consistent environment for review and future deployment.

**Dependencies**  
- F-11 (at least the stock list must be functional to validate end-to-end)  
- Existing `docker-compose.yaml` in `quant-db/`

**Acceptance Criteria**  
- A `Dockerfile` exists in the `angular-client/` directory that:  
  - Builds the Angular app in a multi-stage build (Node build stage → Nginx/static-serve production stage)  
  - The resulting image serves the built Angular app on port 80 (or a configured port)  
  - `docker build` completes without errors  
- The Angular service is added to `docker-compose.yaml` as a named service (e.g. `client`)  
- The `client` service declares a dependency on the `api` service (`depends_on`)  
- The Nginx (or equivalent) configuration proxies `/api/*` requests to the `api` service container, so the Angular app can reach the API without CORS issues  
- `docker-compose up` starts the database, API, and Angular client without manual intervention  
- The Angular app is reachable from the host browser on the mapped port (e.g. `http://localhost:4200` or `http://localhost:80`)  
- The stock list loads and displays data when the full Dockerised stack is running  
- The existing `db` and `api` services are unchanged (no regressions)

**Implementation Priority:** 6 — Final integration step; required before Wave 3 is considered complete.

---

## Summary Table

| # | Feature | Priority | Depends On | Milestone |
|---|---------|----------|------------|-----------|
| F-09 | Angular Project Scaffold | 1 — Highest | Wave 2 | M4 |
| F-10 | Screener API Service | 2 | F-09 | M4 |
| F-11 | Stock List Component | 3 | F-10 | M4 |
| F-12 | Empty-State Handling | 4 | F-11 | M4 |
| F-13 | TradingView Redirect Links | 5 | F-11 | M5 |
| F-14 | Docker Integration for Angular | 6 | F-11 | M4, M5 |

---

## Definition of Done for Wave 3

Wave 3 is complete when all of the following are true:

- The Angular app builds and serves without errors  
- The stock list component displays current screener results fetched from the API  
- An empty API response renders an informational empty-state message (not an error)  
- Each stock with a valid exchange has a working TradingView link that opens in a new tab  
- All unit tests pass (`ng test --watch=false`)  
- `docker-compose up` starts the full stack (DB + API + Angular) and the UI is reachable from the host browser  
- Wave 4 (Operations) team can use the running system as the baseline for scheduling and observability work

