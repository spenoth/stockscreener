# Plan: SuperTrend + BMSB Analysis Feature (API + Angular)

> Research & implementation plan for replicating `analyzers/supertrend_bmsb_analyzer_dbprices.py` in the Angular client, driven by a new FastAPI endpoint instead of a CLI invocation.

---

## 1. Summary

Expose `analyzers/supertrend_bmsb_analyzer_dbprices.py`'s functionality through a new FastAPI endpoint that the Angular client can call from a dedicated page. The endpoint runs `build_all_supertrend_paths_bmsb_filtered` + `TradeAnalyzer.analyze()/.summary()` on demand for a user-supplied ticker and returns `all_paths`, `stats`, and `summary` as JSON. The Angular client renders the two matplotlib subplots as interactive charts (colored by endpoint sign / mean sign) plus a summary metrics table.

This requires:
- **Refactoring** the analyzer script to be side-effect-free and importable.
- **Bundling** `analyzers/` into the API Docker image and adding `pandas`/`pandas_ta` to `api/requirements.txt`.
- **Adding** a charting library and a router to the Angular app.

---

## 2. Open Questions for the User

Recommended defaults are marked with **★**.

1. **Endpoint parameters** — Should `timeframe`, `weekly_timeframe`, `max_hours`, `max_paths` be query params (**★ yes, with defaults `1h` / `1w` / `40` / `200`**) or hardcoded?
2. **Angular navigation** — Which of these?
   - A: Replace stock-list.
   - **★ B: New page/route** `/analysis/:symbol`, launched via an "Analyze" button next to each stock in the existing list.
   - C: Modal launched from stock-list.
3. **Charting library** — **★ Plotly.js** (closest to matplotlib, handles hundreds of thin semi-transparent lines well), Chart.js, ECharts, or D3?
4. **Signal timestamp in response** — the current script's `timestamp` field is actually a positional integer index. Do you want us to also send the **★ real signal datetime (ISO-8601)** so tooltips can show "Signal fired at 2024-06-12T14:00:00Z"?
5. **Empty-signal ticker** — Return **★ 200 OK with `paths: []`** and let the UI show an empty state, or return 404?
6. **Unknown-ticker semantics** — Return **★ 404** with `detail: "No price data for TSLA/1h"`?
7. **Caching / rate limiting** — **★ None in v1**, add later if latency becomes an issue?
8. **Auth** — **★ Keep it open (no auth)** consistent with the rest of the API?
9. **`inf` / `NaN` handling** — `TradeAnalyzer` can emit `np.inf` (recovery_factor when mae==0) and `np.nan`. Both produce invalid JSON. **★ Normalize to `null`** before returning? (Alternative: send strings like `"Infinity"`.)

---

## 3. Backend Refactor (`analyzers/`)

Goal: make `analyzers/` importable from `api/main.py` with **zero side effects at import time**.

### 3.1 Turn `analyzers/` into a proper Python package
- Add `analyzers/__init__.py` (empty or re-exporting the public API).
- Change the sibling import `from trademetrics import TradeAnalyzer` in `supertrend_bmsb_analyzer_dbprices.py` to a relative import `from .trademetrics import TradeAnalyzer`.

### 3.2 Split module: pure library vs. CLI script
In `supertrend_bmsb_analyzer_dbprices.py`:
- **Keep at module top level (pure, no side effects):** `calculate_supertrend`, `find_supertrend_starts`, `extract_supertrend_path`, `normalize_path`, `classify_path`, `calculate_bmsb`, `attach_bmsb_to_hourly`, `build_all_supertrend_paths_bmsb_filtered`, `fetch_prices`, `print_summary`.
- **Move everything below `# CLI ARGUMENTS`** (argparse, `DB_CONFIG`, `psycopg2.connect`, the `df_hourly` fetch, the matplotlib block, the `plt.show()`) **into a `if __name__ == "__main__":` block** or, cleaner, into a new `analyzers/cli/supertrend_bmsb_cli.py`.
- Guard the `matplotlib.pyplot` import so it stays out of the API import path (only import it inside the CLI entry point).

### 3.3 Extract a pure, DB-agnostic orchestration function
Add a new function (e.g. `run_supertrend_bmsb_analysis`) in `supertrend_bmsb_analyzer_dbprices.py` with signature:
- **Inputs:** `cursor` (psycopg2 cursor injected by the caller), `ticker: str`, `timeframe: str = "1h"`, `weekly_timeframe: str = "1w"`, `max_hours: int = 40`, `max_paths: int | None = 200`.
- **Behavior:**
  1. Call `fetch_prices(cursor, ticker, timeframe)` → hourly df.
  2. Call `fetch_prices(cursor, ticker, weekly_timeframe)` → weekly df.
  3. Run `calculate_supertrend`, `calculate_bmsb`, `attach_bmsb_to_hourly`.
  4. Call `build_all_supertrend_paths_bmsb_filtered`.
  5. Return `(all_paths, stats, df_combined)` — return `df_combined` too so the API can enrich each path with the real signal datetime.
- **Contract change:** replace `raise SystemExit(...)` in `fetch_prices` with `raise ValueError(...)` so the API can translate it to an HTTP 404 (SystemExit would kill uvicorn workers).

### 3.4 Configuration hygiene
- Remove the hardcoded `DB_CONFIG` from module scope in the analyzer — the API supplies its own connection via `main.get_connection()`. The CLI entry point can still build its own from env vars (reuse `analyzers/config.py`, which currently only exposes Alpaca keys — extend it with `DB_HOST/DB_PORT/…` env-var reads mirroring `api/config.py`).

### 3.5 Make the package importable from the API
Two viable layouts — pick one:
- **★ Option A (recommended, no source moves):** ensure the `analyzers/` folder is `COPY`'d into the API image (see §4.6) and add `analyzers/` to `PYTHONPATH` at container start (or add a `sys.path` insertion in a small `api/analyzers_bootstrap.py` — but Docker `COPY` + `PYTHONPATH=/app` is cleaner).
- Option B: physically move `analyzers/` under `api/analyzers/`. Cleaner packaging, but breaks the CLI usage from the repo root.

---

## 4. Backend API Changes (`api/`)

### 4.1 New endpoint
- **Path:** `GET /api/analysis/supertrend-bmsb/{ticker}`
- **Query params:** `timeframe` (default `1h`), `weekly_timeframe` (default `1w`), `max_hours` (default `40`), `max_paths` (default `200`). Validate `timeframe`/`weekly_timeframe` against the existing `SUPPORTED_TIMEFRAMES` set in `api/main.py`.
- **Router:** add `api/routers/analysis.py` with an `APIRouter(prefix="/api/analysis")`; wire it in `main.py` via `app.include_router(...)`. This is the first router in the project, so it also establishes the pattern for future features.

### 4.2 Pydantic response models (in `api/routers/analysis.py` or `api/models/analysis.py`)
- `SupertrendPath`
  - `timestamp_index: int` — positional index in the combined DataFrame.
  - `signal_time: str | None` — ISO-8601 UTC datetime of the signal bar (only if open question 4 = Yes).
  - `path_percent: list[float]` — % change per bar (0.0 for entry bar), length ≤ `max_hours + 1`.
  - `endpoint: float` — final decimal fraction (e.g. 0.05 for +5%).
  - `mean: float` — average decimal fraction across the path.
  - `endpoint_positive: bool`
  - `mean_positive: bool`
- `SupertrendStats`
  - `total_signals: int`
  - `bmsb_above: int`
  - `bmsb_below_or_unknown: int`
- `SupertrendSummary` (mirrors `TradeAnalyzer.summary()` keys)
  - `num_trades: int`
  - `win_rate: float`
  - `avg_win: float`
  - `avg_loss: float`
  - `avg_mfe: float`
  - `avg_drawdown_winners: float`
  - `avg_drawdown_losers: float`
  - `expectancy: float`
- `SupertrendAnalysisResponse`
  - `ticker: str`
  - `timeframe: str`
  - `weekly_timeframe: str`
  - `max_hours: int`
  - `max_paths: int`
  - `paths: list[SupertrendPath]`
  - `stats: SupertrendStats`
  - `summary: SupertrendSummary | None` — `null` when `paths` is empty.

### 4.3 Handler flow
1. Validate `timeframe`/`weekly_timeframe` against the supported set → 400 on failure.
2. `conn = get_connection()` (reuse existing helper; 503 on connectivity failure — same pattern as `/api/screener/bmsb/current`).
3. Inside a `with conn: with conn.cursor() as cur:` block, call `run_supertrend_bmsb_analysis(cur, ticker.upper(), …)`.
   - Catch `ValueError` from `fetch_prices` → 404 with `{"detail": "No price data for <ticker>/<timeframe>"}`.
4. Instantiate `TradeAnalyzer(all_paths)`, call `.analyze()` and `.summary()`.
5. Build the response dict, applying the serialization normalizer (§4.4).
6. Return the Pydantic model instance.

### 4.4 JSON serialization concerns (implement once as a helper `_to_json_safe`)
- `pandas.Timestamp` → `.isoformat()` (make sure to convert to UTC).
- `numpy.float64` / `numpy.int64` → Python `float` / `int` (`.item()`).
- `numpy.inf`, `numpy.nan` → `None` (JSON standards don't allow `Infinity`/`NaN`; FastAPI's default encoder produces invalid JSON for these). Especially applies to `recovery_factor` in `TradeMetrics` (though not exposed in v1) and any of the `summary()` values when `winners`/`losers` is empty.
- `numpy.bool_` → plain `bool`.

### 4.5 Error mapping recap
| Condition | HTTP | Body |
|---|---|---|
| Invalid timeframe param | 400 | `{"detail": "Unsupported timeframe '<x>'. Use one of: …"}` |
| No rows in `quant.prices` for ticker+timeframe | 404 | `{"detail": "No price data for TSLA/1h"}` |
| No qualifying signals above BMSB | 200 | full body with `paths: []`, `summary: null` |
| DB connect fails | 503 | `{"detail": "Database unavailable"}` |
| Unexpected exception during compute | 500 | `{"detail": "Internal server error"}` (also logged by the existing global handler) |

### 4.6 `requirements.txt` and Dockerfile
- `api/requirements.txt`: add `pandas>=2.2.0`, `pandas_ta>=0.3.14b0`, `numpy>=1.26,<2.0` (pandas_ta is not compatible with numpy 2 yet — `np.NaN` was removed).
- `api/Dockerfile`: the build context needs to include `analyzers/`. Two options:
  - **★** Change build to run from repo root: `docker build -f api/Dockerfile .` and update `COPY` lines to `COPY api/requirements.txt .`, `COPY api/ /app/`, `COPY analyzers/ /app/analyzers/`. Set `ENV PYTHONPATH=/app`.
  - Or add a pre-build step that copies `analyzers/` into `api/` before `docker build` — simpler Dockerfile, dirtier workflow.
- Confirm `pandas_ta` installs cleanly under Zscaler cert (it's a pure-Python wheel, should be fine).

### 4.7 Wire the router into `main.py`
- Add `from routers.analysis import router as analysis_router` and `app.include_router(analysis_router)` in `api/main.py` after existing routes.
- Preserve existing global `@app.exception_handler(Exception)`.

### 4.8 New tests in `api/tests/test_api.py` (or new `test_analysis.py`)
- `test_analysis_happy_path` — patch `main.get_connection` and `run_supertrend_bmsb_analysis` to return fixture `(paths, stats, df)`. Assert 200 + response shape.
- `test_analysis_unknown_ticker` — patch analyzer to raise `ValueError("No price data")`. Assert 404.
- `test_analysis_no_qualifying_signals` — analyzer returns `([], {"total_signals": 0, ...}, df)`. Assert 200 with `paths: []` and `summary: null`.
- `test_analysis_invalid_timeframe` — assert 400.
- `test_analysis_db_unavailable` — patch `get_connection` to raise `psycopg2.OperationalError`. Assert 503.
- `test_analysis_serialization_inf_nan` — feed a fake `.summary()` returning `np.inf` and `np.nan`, assert the JSON body contains `null` not `Infinity`.

---

## 5. Angular Client Changes (`angular-client/`)

### 5.1 New TypeScript interfaces — `src/app/models/analysis.model.ts`
- `SupertrendPath { timestampIndex: number; signalTime: string | null; pathPercent: number[]; endpoint: number; mean: number; endpointPositive: boolean; meanPositive: boolean; }`
- `SupertrendStats { totalSignals: number; bmsbAbove: number; bmsbBelowOrUnknown: number; }`
- `SupertrendSummary { numTrades: number; winRate: number; avgWin: number; avgLoss: number; avgMfe: number; avgDrawdownWinners: number; avgDrawdownLosers: number; expectancy: number; }`
- `SupertrendAnalysisResponse { ticker: string; timeframe: string; weeklyTimeframe: string; maxHours: number; maxPaths: number; paths: SupertrendPath[]; stats: SupertrendStats; summary: SupertrendSummary | null; }`
- Note the naming mismatch with the API (snake_case → camelCase). Two options: (a) match snake_case in TS (simpler), or **★ (b) keep camelCase and add a small mapper** in the service so the UI is idiomatic.

### 5.2 Service — new `src/app/services/analysis.service.ts`
- Method: `getSupertrendBmsbAnalysis(ticker: string, opts?: { timeframe?: string; weeklyTimeframe?: string; maxHours?: number; maxPaths?: number }): Observable<SupertrendAnalysisResponse>`.
- Base URL uses `environment.apiBaseUrl + '/api/analysis/supertrend-bmsb/'`. Query params via `HttpParams`.
- Mirror the existing test pattern in `screener.service.spec.ts` using `HttpClientTestingModule`.

### 5.3 New component — `src/app/components/supertrend-analysis/`
Files: `supertrend-analysis.component.ts`, `.html`, `.css`, `.spec.ts`.
- **Selector:** `app-supertrend-analysis`, `standalone: true`.
- **Inputs / state:**
  - `ticker` bound to an `<input>` (or `@Input() initialTicker` if opened from a route param).
  - Optional dropdowns for `timeframe`, `weeklyTimeframe`, and number inputs for `maxHours`, `maxPaths`.
  - `loading: boolean`, `error: string | null`, `response: SupertrendAnalysisResponse | null`.
- **Template outline (mirror the layout of matplotlib):**
  - Header row: ticker input + timeframe controls + "Analyze" button.
  - Loading spinner (reuse `.spinner` CSS from `stock-list.component.css`).
  - Error banner (reuse `.notification--error`).
  - Empty state: "No SuperTrend signals occurred above the BMSB — nothing to plot" (matches script's message).
  - **Summary metrics table**: 8-row 2-column table listing the 8 fields from `SupertrendSummary` formatted as percentages (`winRate` etc.) or counts (`numTrades`).
  - **Stats line**: "SuperTrend signals — total: X, above BMSB: Y, below/unknown BMSB: Z" (matches script's `print(...)`).
  - **Two charts side-by-side** inside a flex container (`display: flex; gap: 16px`) with a shared Y-axis feel:
    - Left: title "By Endpoint (last value)".
    - Right: title "By Mean (mostly above or below entry)".
- Legend below each chart: green count / red count derived from `endpointPositive` / `meanPositive`.

### 5.4 Charting
- **Library:** Plotly.js (`plotly.js-dist-min`) via a thin standalone wrapper component or `angular-plotly.js` (`^5`).
- **Install:** `npm install plotly.js-dist-min angular-plotly.js` (or just `plotly.js-dist-min` and call `Plotly.newPlot` directly in `ngAfterViewInit`).
- **Import location:** in the standalone component's `imports: [PlotlyModule]` after `PlotlyModule.plotlyjs = PlotlyJS` bootstrap.
- **Data mapping:** for each `path` in `response.paths`, produce one Plotly trace `{ x: [0..pathPercent.length-1], y: pathPercent, mode: 'lines', line: { color, width: 0.8 }, opacity: 0.3, hoverinfo: 'skip' }`.
  - Left chart: `color = endpointPositive ? 'green' : 'red'`.
  - Right chart: `color = meanPositive ? 'green' : 'red'`.
- **Layout:** `xaxis.title = 'Hours since signal'`, `yaxis.title = '% change'` (left only), `shapes: [{ type: 'line', x0: 0, x1: maxLen, y0: 0, y1: 0, line: { color: 'gray', dash: 'dash' } }]` for the horizontal zero line, `showlegend: false` (draw a custom legend in HTML to match matplotlib's "Positive endpoint (N)" style).
- **Performance:** with `max_paths: 200` and up to 41 points each, this is ~8k points per chart — Plotly's SVG mode is fine. If the user raises `max_paths` above ~1000, switch to `scattergl` (WebGL) for hardware acceleration.

### 5.5 Routing
- Currently there is no `RouterModule` wired in — `main.ts` only calls `provideHttpClient()` and `app.component.ts` inlines `<app-stock-list>`.
- **Add** `provideRouter(routes)` in `main.ts` and a `routes` array (e.g. `src/app/app.routes.ts`):
  - `{ path: '', component: StockListComponent }`
  - `{ path: 'analysis', component: SupertrendAnalysisComponent }`
  - `{ path: 'analysis/:symbol', component: SupertrendAnalysisComponent }` — for deep-linking from the stock list.
- Replace `<app-stock-list>` in `app.component.ts` with a minimal nav + `<router-outlet>`.
- Add an "Analyze" link/button per row in `stock-list.component.html` that navigates via `[routerLink]="['/analysis', stock.symbol]"`.

### 5.6 Proxy / environment
- No changes required to `proxy.conf.json` — `/api/*` already forwards to `http://localhost:8000`.
- No changes to `environment.ts` / `.prod.ts` — same `apiBaseUrl` reused.
- No changes to `nginx.conf` — `/api/` proxy already covers the new endpoint.

### 5.7 New tests
- `analysis.service.spec.ts` — mirrors `screener.service.spec.ts`: assert URL, query params, response typing, empty-array handling.
- `supertrend-analysis.component.spec.ts`: loading state, error state, empty-paths state, summary table renders correct fields, correct number of Plotly traces created (spy the Plotly wrapper), routing param picked up.

---

## 6. Step-by-Step Implementation Order

### Phase A — Backend refactor
1. Add `analyzers/__init__.py`.
2. Change sibling import in `supertrend_bmsb_analyzer_dbprices.py` to relative (`from .trademetrics import TradeAnalyzer`).
3. Move argparse / matplotlib / DB-connection lines out of module scope into `if __name__ == "__main__":` or a new `analyzers/cli/supertrend_bmsb_cli.py`.
4. Replace `raise SystemExit` in `fetch_prices` with `raise ValueError`.
5. Add `run_supertrend_bmsb_analysis(cur, ticker, timeframe, weekly_timeframe, max_hours, max_paths)` function returning `(all_paths, stats, df_combined)`.
6. Verify CLI still runs: `python -m analyzers.cli.supertrend_bmsb_cli TSLA` (or the old command per whichever refactor path is chosen).

### Phase B — API endpoint + tests
7. Extend `api/requirements.txt` with `pandas`, `pandas_ta`, `numpy<2`.
8. Update `api/Dockerfile` to also `COPY analyzers/` and set `PYTHONPATH=/app`; change docker build context in any compose file if applicable.
9. Create `api/routers/analysis.py` with Pydantic models + endpoint handler + `_to_json_safe` helper.
10. Register the router in `api/main.py`.
11. Write tests in `api/tests/test_analysis.py` covering the six cases in §4.8.
12. Run `pytest` locally against the API.

### Phase C — Angular models + service
13. Create `src/app/models/analysis.model.ts` with the four interfaces.
14. Create `src/app/services/analysis.service.ts` with `getSupertrendBmsbAnalysis(...)` and camelCase mapper.
15. Add `analysis.service.spec.ts` mirroring the existing screener service test.

### Phase D — Angular component + charts
16. `npm install plotly.js-dist-min angular-plotly.js` from `angular-client/`.
17. Create the `SupertrendAnalysisComponent` files (ts/html/css/spec).
18. Wire routing: create `src/app/app.routes.ts`, update `main.ts` with `provideRouter`, refactor `app.component.ts` to use `<router-outlet>` + nav.
19. Add "Analyze" links in `stock-list.component.html`.
20. Run `ng test` and `ng build --configuration=production` to verify bundle size stays under the 500KB warning / 1MB error budget from `angular.json`. Plotly is ~1.2MB — may need to bump budget or lazy-load the route.

### Phase E — End-to-end verification
21. Start the API (`uvicorn main:app --reload`) and Angular (`npm start`) locally against a populated DB.
22. Load `TSLA` (already seeded in `init.sql`) at both `1h` and `1w` timeframes if not already present via `/api/retriever/prices/TSLA/1h` and `.../1w`.
23. Navigate to `/analysis/TSLA` in the browser and confirm the two charts visually match the matplotlib output from `python analyzers/supertrend_bmsb_analyzer_dbprices.py TSLA`.
24. Test unknown ticker, empty-signal ticker (short history), invalid timeframe.
25. Confirm 500 handler swallows tracebacks and browser console shows a clean error banner.

---

## 7. Risks / Gotchas

1. **`pandas_ta` + `numpy 2.x` incompatibility** — `pandas_ta` still imports `numpy.NaN` which was removed in numpy 2. Pin `numpy<2` in `api/requirements.txt`.
2. **Docker build context** — the API `Dockerfile` currently builds from the `api/` folder and cannot see `analyzers/`. Must change build context to repo root and adjust `COPY` paths, or physically colocate `analyzers/`.
3. **JSON invalid values** — `np.inf` (from `recovery_factor` when `mae == 0`) and `np.nan` (from `.summary()` when there are zero winners/losers) will silently produce invalid JSON via FastAPI's default encoder. Client will fail to parse. Must be normalized to `null` before returning.
4. **`fetch_prices` calls `SystemExit`** — that would kill uvicorn workers. Must be replaced with a normal exception.
5. **Look-ahead bias** — already documented in `attach_bmsb_to_hourly`'s docstring: the still-forming weekly bar's close is used to decide BMSB. This is intentional to match the live screener but should be surfaced in the Angular UI as a small info note under the charts to avoid users mis-reading historical backtest numbers as tradable.
6. **Payload size** — 200 paths × 41 floats × ~15 bytes each ≈ 120KB per response. Gzip in nginx keeps it small; still, consider `path_percent` precision truncation (e.g. 4 decimals) if profiles show it's a bottleneck.
7. **Chart performance** — SVG Plotly slows visibly beyond ~1000 traces. If `max_paths` is ever exposed to end users, cap the UI selector at 500 and switch to `scattergl` above that.
8. **Angular bundle budget** — Plotly.js-dist-min adds ~1.2MB. Either raise the `production.budgets.maximumError` in `angular.json` or lazy-load the analysis route so the main bundle stays under budget.
9. **CORS / proxy** — dev works via `proxy.conf.json`; prod works via `nginx.conf` `/api/` block. Both are already correct for `/api/analysis/...`. No changes needed, but flag as a check.
10. **No router today** — introducing `provideRouter` is a small but non-trivial refactor of `main.ts` and `app.component.ts`. Existing `stock-list.component.spec.ts` may need updates if it relied on `AppComponent` directly rendering it.
11. **Repeated compute cost** — a first-time run for a ticker with years of hourly bars can take multiple seconds. No caching in v1 (see open question 7) — set frontend request timeout accordingly (e.g. 30s) and show the spinner.
12. **CLI regression risk** — after moving matplotlib code, ensure `python analyzers/supertrend_bmsb_analyzer_dbprices.py TSLA` still works (or migrate the CLI docs to the new invocation).

---

## 8. Status / Next Actions

- [ ] User answers the 9 open questions in §2 (or accepts all ★ defaults).
- [ ] Kick off Phase A (backend refactor).
- [ ] Kick off Phase B (API endpoint + tests).
- [ ] Kick off Phase C (Angular models + service).
- [ ] Kick off Phase D (Angular component + charts).
- [ ] Kick off Phase E (end-to-end verification).

