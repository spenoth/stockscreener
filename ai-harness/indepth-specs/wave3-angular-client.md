# Wave 3 — Detailed Functional & Technical Specification: Angular Client (Frontend)

**Project:** Weekly Stock Screener  
**Wave:** 3  
**Date:** 2026-06-04  
**Based on:** Business Requirements v1.0, Development Roadmap v1.0, Wave 3 Feature Specifications  
**Milestones:** M4 (Stock List + Empty State), M5 (TradingView Links)

---

## 1. Purpose

Provide a browser-based Angular application that displays the current list of stocks passing the BMSB screener. The client consumes the Wave 2 REST API, presents results in a readable format, links each stock to its TradingView chart, and handles empty and error states gracefully. The application must be deployable as a Docker container alongside the existing API and database services.

---

## 2. Scope

### In Scope

- Angular CLI project scaffolding with proxy configuration for local API access
- Angular service encapsulating HTTP calls to the screener API
- Stock list component displaying symbol and exchange for each passing stock
- Loading state while awaiting API response
- Error state for network/server failures
- Empty-state messaging when the latest screener version has zero results
- TradingView redirect links per stock row (new tab)
- Graceful degradation when exchange data is missing
- Dockerfile for multi-stage build (Node → Nginx)
- Integration into existing `docker-compose.yaml`
- Unit tests for service and components

### Out of Scope

- Authentication / authorisation
- Sorting, filtering, or pagination of results
- Historical version browsing
- Any write operations to the API
- Styling beyond basic readability (no design system required in v1)
- End-to-end (E2E) tests
- Server-side rendering (SSR)

---

## 3. Inputs

| Input | Source | Format | Description |
|---|---|---|---|
| Current screener results | `GET /api/screener/bmsb/current` (Wave 2 API) | JSON array of `{ symbol: string, exchange: string }` | Latest-version passed stocks |
| API base URL | Environment configuration (`environment.ts` / `environment.prod.ts`) | String | Base URL for all API calls; defaults to `http://localhost:8000` in dev |
| Proxy configuration | `proxy.conf.json` (dev only) | JSON | Forwards `/api/*` to the API service during `ng serve` |

---

## 4. Outputs

| Output | Consumer | Format | Description |
|---|---|---|---|
| Rendered stock list | Browser / end user | HTML | Table or card layout showing symbol and exchange per stock |
| Loading indicator | Browser / end user | HTML | Displayed while the API call is in flight |
| Error message | Browser / end user | HTML | Displayed when the API call fails (network error, 5xx) |
| Empty-state message | Browser / end user | HTML | Displayed when the API returns an empty array |
| TradingView link | Browser / end user | Anchor tag (`<a>`) | Opens `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}` in a new tab |
| Production build artefact | Nginx container | Static files (`dist/`) | Served by Nginx inside the Docker image |

---

## 5. Business Rules

| ID | Rule | Source |
|---|---|---|
| BR-4 | The UI displays only stocks from the latest watchlist version. There is no fallback to prior versions. | BRS §6 |
| BR-5 | Each displayed stock includes `symbol` and `exchange`, where exchange originates from `tickers` master data. | BRS §6 |
| BR-6 | When the latest version has zero passing stocks, the UI displays an informational empty-state message — not an error. | BRS §6 |
| BR-TV-1 | TradingView URL format: `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}`. | Wave 3 F-13, BRS §14 OI-2 |
| BR-TV-2 | If a stock's `exchange` is null, empty, or missing, the TradingView link is **not rendered** for that row. The row still displays symbol and exchange text. | Wave 3 F-13 |
| BR-LINK-1 | TradingView links open in a new browser tab with `target="_blank"` and `rel="noopener noreferrer"`. | Wave 3 F-13 |
| BR-NO-AUTH | No authentication or authorisation is required in v1. | BRS §4 Out of Scope |
| BR-READ-ONLY | The Angular client performs read-only operations only. No data is written or mutated. | BRS §3 |

---

## 6. Data Requirements

### 6.1 API Response Contract

**Endpoint:** `GET /api/screener/bmsb/current`  
**Method:** GET  
**Response Status:** `200 OK` (always, including empty results)  
**Response Body:**

```
Stock[] where Stock = { symbol: string, exchange: string }
```

| Field | Type | Nullable | Description |
|---|---|---|---|
| `symbol` | `string` | No | Ticker symbol (e.g. `TSLA`, `AAPL`) |
| `exchange` | `string` | Yes* | Exchange identifier (e.g. `NASDAQ`, `NYSE`). May be null/empty in edge cases. |

*Per BR-TV-2, the client must handle null/empty exchange gracefully.

### 6.2 TypeScript Interface

A `Stock` interface must be defined with at minimum:
- `symbol: string`
- `exchange: string`

### 6.3 Environment Configuration

| Property | Dev Default | Prod Default | Description |
|---|---|---|---|
| `apiBaseUrl` | `""` (proxied via `proxy.conf.json`) | `""` (proxied via Nginx) | Base URL prefix for API calls |

### 6.4 Proxy Configuration (Development)

- File: `proxy.conf.json`
- Rule: `/api/*` → `http://localhost:8000`
- Used during `ng serve` only

### 6.5 Nginx Proxy Configuration (Production / Docker)

- Rule: `/api/*` → `http://api:8000` (Docker service name)
- All other paths serve the Angular `index.html` (SPA fallback)

---

## 7. Error Handling

| Scenario | Condition | Behaviour |
|---|---|---|
| **Loading** | API call in flight | Display a loading indicator or "Loading…" text. No stock list or empty-state message visible. |
| **Success with data** | API returns non-empty `Stock[]` | Render the stock list. Hide loading indicator. |
| **Success with empty data** | API returns `[]` | Display informational empty-state message. Do not display an error. Do not trigger retry or redirect. Message example: *"No stocks passed the latest screening. This may indicate market conditions did not meet the screener criteria."* |
| **Network / server error** | API call fails (timeout, DNS, 5xx, connection refused) | Display user-facing error message. Example: *"Unable to load screener results. Please try again later."* Error state must be visually distinct from empty state. |
| **Missing exchange on a stock** | `exchange` is `null`, `""`, or `undefined` on a returned stock object | Render the stock row with symbol and exchange text, but **omit** the TradingView link for that row. No broken anchor tags. |
| **API returns unexpected shape** | Response is not a valid JSON array | Treat as a server error (same behaviour as 5xx). |

### State Exclusivity

The component has exactly **four mutually exclusive visual states**:

1. **Loading** — data not yet received
2. **Data** — one or more stocks to display
3. **Empty** — zero stocks, informational message
4. **Error** — API call failed, error message

Only one state is rendered at a time.

---

## 8. Acceptance Criteria

### F-09 — Angular Project Scaffold

| # | Criterion |
|---|---|
| AC-09-1 | An `angular-client/` directory exists at the project root containing a standard Angular CLI project (v17+). |
| AC-09-2 | `ng serve` starts the dev server without errors and renders a page with the title "Stock Screener". |
| AC-09-3 | `ng build` produces a production build without errors. |
| AC-09-4 | A `proxy.conf.json` forwards `/api/*` to `http://localhost:8000` during local development. |
| AC-09-5 | `ng serve` with proxy config successfully proxies requests to a running API instance. |
| AC-09-6 | `environment.ts` and `environment.prod.ts` exist with at least an `apiBaseUrl` property. |
| AC-09-7 | `ng lint` passes with zero errors. |
| AC-09-8 | Default Angular boilerplate is removed; the app shell displays "Stock Screener" as a page title. |

### F-10 — Screener API Service

| # | Criterion |
|---|---|
| AC-10-1 | A `Stock` TypeScript interface exists with `symbol: string` and `exchange: string`. |
| AC-10-2 | An injectable `ScreenerService` exists with a method returning `Observable<Stock[]>`. |
| AC-10-3 | The service calls `GET {apiBaseUrl}/api/screener/bmsb/current` using Angular `HttpClient`. |
| AC-10-4 | The API base URL is read from environment configuration; no hardcoded URLs in the service file. |
| AC-10-5 | A unit test mocks `HttpClient` and verifies the correct URL is called. |
| AC-10-6 | A unit test verifies the response is typed as `Stock[]`. |
| AC-10-7 | A unit test verifies an empty array response `[]` is handled without error. |
| AC-10-8 | `ng test --watch=false` passes with all service tests green. |

### F-11 — Stock List Component

| # | Criterion |
|---|---|
| AC-11-1 | A `StockListComponent` is rendered as the main content of the application. |
| AC-11-2 | On initialisation, the component calls `ScreenerService` to fetch the stock list. |
| AC-11-3 | Each stock displays at minimum: symbol and exchange. |
| AC-11-4 | The list uses a readable layout (table or card list). |
| AC-11-5 | A loading indicator is displayed while data is loading. |
| AC-11-6 | An error message is displayed if the API call fails. |
| AC-11-7 | Unit test: component renders stock data when service returns results. |
| AC-11-8 | Unit test: loading state shown before data arrives. |
| AC-11-9 | Unit test: error state shown when service call fails. |
| AC-11-10 | `ng test --watch=false` passes with all component tests green. |

### F-12 — Empty-State Handling

| # | Criterion |
|---|---|
| AC-12-1 | When the API returns `[]`, the component displays an informational empty-state message. |
| AC-12-2 | The empty-state message is visually distinct from the error state. |
| AC-12-3 | The empty state does not trigger a retry or redirect. |
| AC-12-4 | Unit test: empty-state message rendered when service returns `[]`. |
| AC-12-5 | The empty-state message is not shown while data is still loading. |
| AC-12-6 | `ng test --watch=false` passes. |

### F-13 — TradingView Redirect Links

| # | Criterion |
|---|---|
| AC-13-1 | Each stock row with a valid exchange includes a clickable link. |
| AC-13-2 | The link opens in a new tab (`target="_blank"`, `rel="noopener noreferrer"`). |
| AC-13-3 | URL format: `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}`. |
| AC-13-4 | Links work for both `NYSE` and `NASDAQ` exchange values. |
| AC-13-5 | When exchange is null or empty, no link is rendered for that row. |
| AC-13-6 | Unit test: correct URL generated for a stock with a known exchange. |
| AC-13-7 | Unit test: no link rendered when exchange is null or empty. |
| AC-13-8 | `ng test --watch=false` passes. |

### F-14 — Docker Integration

| # | Criterion |
|---|---|
| AC-14-1 | A `Dockerfile` in `angular-client/` uses a multi-stage build (Node build → Nginx serve). |
| AC-14-2 | The built image serves the Angular app on port 80. |
| AC-14-3 | `docker build` completes without errors. |
| AC-14-4 | A `client` service is added to `docker-compose.yaml` with `depends_on: api`. |
| AC-14-5 | Nginx proxies `/api/*` to the `api` service container. |
| AC-14-6 | `docker-compose up` starts DB, API, and client without manual intervention. |
| AC-14-7 | The Angular app is reachable from the host browser on the mapped port. |
| AC-14-8 | The stock list loads and displays data in the full Dockerised stack. |
| AC-14-9 | Existing `db` and `api` services are unchanged (no regressions). |

---

## 9. Component & Service Inventory

| Artefact | Type | Responsibility |
|---|---|---|
| `Stock` | TypeScript interface | Data contract for API response items |
| `ScreenerService` | Injectable service | HTTP calls to screener API; returns `Observable<Stock[]>` |
| `StockListComponent` | Component | Fetches and displays stocks; manages loading/error/empty states |
| `environment.ts` | Config file | Dev environment settings (`apiBaseUrl`) |
| `environment.prod.ts` | Config file | Prod environment settings (`apiBaseUrl`) |
| `proxy.conf.json` | Config file | Dev proxy for `/api/*` |
| `nginx.conf` | Config file | Prod proxy for `/api/*` + SPA fallback |
| `Dockerfile` | Docker | Multi-stage build for Angular client |

---

## 10. State Diagram

```
[Init] → [Loading]
[Loading] → [Data]     (API returns non-empty array)
[Loading] → [Empty]    (API returns [])
[Loading] → [Error]    (API call fails)
```

No transitions exist from Data, Empty, or Error back to Loading in v1 (no refresh/retry mechanism specified).

---

## 11. Constraints & Assumptions

| # | Constraint / Assumption |
|---|---|
| C-1 | Angular v17+ or v18+ (recent stable). |
| C-2 | Single-page application; no routing required in v1 (single view). |
| C-3 | No authentication; API is open on the local network. |
| C-4 | The API always returns HTTP 200 with a JSON array, even for empty results. |
| C-5 | Exchange values in the API response are `NASDAQ` or `NYSE` (or null). No other exchanges expected in v1. |
| C-6 | The TradingView URL format `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}` is confirmed. |
| C-7 | The Angular client is read-only; no write endpoints exist or are consumed. |
| C-8 | Nginx is the production static file server and reverse proxy. |

---

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Incorrect/missing exchange in `tickers` master data | Broken or missing TradingView links | BR-TV-2: graceful omission of link when exchange is absent |
| API unavailable during page load | User sees error state | Clear error messaging; user can manually refresh |
| TradingView URL format changes | Links break silently | URL format externalised to environment config or constant for easy update |
| Angular major version upgrade breaks build | Docker build fails | Pin Angular version in `package.json` |

---

## 13. Open Items

| ID | Item | Status | Impact |
|---|---|---|---|
| OI-1 | Final wording of empty-state message | Open — default provided in spec | F-12 display text |
| OI-2 | TradingView URL format confirmation | Resolved — `https://www.tradingview.com/chart/?symbol={EXCHANGE}:{SYMBOL}` | F-13 link construction |
| OI-3 | Host port mapping for Docker client service | Open — `80` or `4200` | F-14 `docker-compose.yaml` port binding |

