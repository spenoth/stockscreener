# Charting Plan: Recreate SuperTrend Matplotlib Plots in Angular with Chart.js

## Goal

Recreate the two matplotlib plots at the end of `analyzers/supertrend_analyzer_dbprices.py` in the Angular client using Chart.js line charts.

The Python script currently renders:

1. **Left chart:** all normalized SuperTrend signal paths colored by final endpoint result.
   - Green = `endpoint_positive === true`
   - Red = `endpoint_positive === false`

2. **Right chart:** the same paths colored by average path result.
   - Green = `mean_positive === true`
   - Red = `mean_positive === false`

Both charts show:

- X-axis: hours since signal
- Y-axis: percent change from entry
- Dashed horizontal zero line
- Grid
- Shared Y-axis range
- Counts of positive/negative classifications
- Overall title: `SuperTrend Signal Paths — {ticker} ({timeframe}) — {count} total`

The Angular version should preserve the same interpretation while using Chart.js via `ng2-charts`.

---

## Recommended Frontend Library

Use:

- `chart.js`
- `ng2-charts`

Install from `angular-client/`:

```powershell
npm install chart.js ng2-charts
```

Why this choice:

- Chart.js has a native line chart matching the desired visual.
- `ng2-charts` integrates cleanly with Angular templates.
- Chart.js handles many simple line datasets well if animations and point markers are disabled.
- The resulting UI remains lightweight compared with heavier scientific plotting libraries.

---

## REST Data Contract

The backend should keep all SuperTrend analytics in Python and return already-normalized paths to Angular.

Angular should not recompute SuperTrend. It should only visualize the result.

Recommended response shape:

```json
{
  "ticker": "TSLA",
  "timeframe": "1h",
  "max_hours": 40,
  "paths": [
    {
      "path": [0.0, 1.2, 2.1, -0.4],
      "endpoint_positive": false,
      "mean_positive": true,
      "endpoint": -0.4,
      "mean": 0.725
    }
  ]
}
```

This matches the structure produced by `build_all_supertrend_paths()` in `supertrend_analyzer_dbprices.py`.

If another analyzer/API returns both raw and percentage paths, prefer percentage values for charting:

- Use `path` when it already contains normalized percent changes.
- Use `path_percent` if the API provides raw returns in `path` and percent values separately.

---

## TypeScript Models

Add interfaces to `angular-client/src/app/models/stock.model.ts` or a dedicated model file.

```ts
export interface SupertrendPath {
  path: number[];
  endpoint_positive: boolean;
  mean_positive: boolean;
  endpoint: number;
  mean: number;
}

export interface SupertrendPathsResponse {
  ticker: string;
  timeframe: string;
  max_hours?: number;
  paths: SupertrendPath[];
}
```

If the backend returns extra metrics later, extend this without changing the chart component contract:

```ts
export interface SupertrendAnalysisResponse extends SupertrendPathsResponse {
  stats?: unknown;
  summary?: unknown;
  mean_path?: number[];
}
```

---

## Angular Service Method

Add a method to the existing Angular service, likely `ScreenerService`.

Example:

```ts
getSupertrendPaths(ticker: string, timeframe = '1h') {
  return this.http.get<SupertrendPathsResponse>(
    `/api/supertrend-paths/${ticker}`,
    {
      params: { timeframe }
    }
  );
}
```

Adjust the URL to match the actual FastAPI endpoint. If the existing backend endpoint is named differently, keep the response shape above and only change the route.

Recommended endpoint style:

```text
GET /api/analysis/supertrend-paths/{ticker}?timeframe=1h
```

or, if using the existing BMSB/SuperTrend endpoint:

```text
GET /api/analysis/bmsb-supertrend/{ticker}
```

---

## Angular Component

Create a standalone component:

```text
angular-client/src/app/components/supertrend-paths-chart/
  supertrend-paths-chart.component.ts
  supertrend-paths-chart.component.html
  supertrend-paths-chart.component.css
```

Responsibilities:

- Accept `ticker`, `timeframe`, and `paths` as inputs.
- Build one Chart.js dataset per SuperTrend path.
- Build two chart data objects:
  - endpoint-classified chart
  - mean-classified chart
- Compute shared Y-axis bounds.
- Add a dashed zero-line dataset.
- Display custom Angular legends with counts.

---

## Chart.js Dataset Mapping

Python:

```python
for entry in all_paths:
    color = "green" if entry["endpoint_positive"] else "red"
    ax1.plot(entry["path"], color=color, linewidth=0.8, alpha=0.3)
```

Angular/Chart.js equivalent:

```ts
const dataset = {
  label: `Signal ${index + 1}`,
  data: entry.path.map((value, hour) => ({
    x: hour,
    y: value
  })),
  borderColor: positive
    ? 'rgba(0, 128, 0, 0.3)'
    : 'rgba(220, 0, 0, 0.3)',
  backgroundColor: 'transparent',
  borderWidth: 1,
  pointRadius: 0,
  pointHoverRadius: 0,
  tension: 0,
  fill: false
};
```

Notes:

- `x` is the array index, equivalent to matplotlib's implicit X values.
- `y` is normalized percent change from entry.
- `rgba(..., 0.3)` recreates `alpha=0.3`.
- `borderWidth: 1` approximates matplotlib `linewidth=0.8`.
- `pointRadius: 0` prevents Chart.js from drawing markers on every point.

---

## Zero Line Dataset

Python:

```python
ax1.axhline(0, color="gray", linestyle="--", linewidth=1)
```

Chart.js equivalent:

```ts
const zeroLineDataset = {
  label: 'Zero line',
  data: [
    { x: 0, y: 0 },
    { x: maxHours, y: 0 }
  ],
  borderColor: 'rgba(120, 120, 120, 0.9)',
  borderWidth: 1,
  borderDash: [6, 4],
  pointRadius: 0,
  pointHoverRadius: 0,
  tension: 0,
  fill: false
};
```

Add this dataset to both charts after the path datasets.

---

## Chart Options

Use shared options for both charts, with only the title changed.

```ts
const options: ChartOptions<'line'> = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  parsing: false,
  normalized: true,
  interaction: {
    mode: 'nearest',
    intersect: false
  },
  plugins: {
    title: {
      display: true,
      text: 'By Endpoint (last value)'
    },
    legend: {
      display: false
    },
    tooltip: {
      callbacks: {
        title: items => {
          const hour = items[0]?.parsed.x ?? 0;
          return `Hours since signal: ${hour}`;
        },
        label: item => {
          return `% change: ${item.parsed.y.toFixed(2)}%`;
        }
      }
    }
  },
  scales: {
    x: {
      type: 'linear',
      title: {
        display: true,
        text: 'Hours since signal'
      },
      ticks: {
        precision: 0
      },
      grid: {
        display: true
      }
    },
    y: {
      title: {
        display: true,
        text: '% change'
      },
      grid: {
        display: true
      }
    }
  }
};
```

For the right chart, use title:

```text
By Mean (mostly above or below entry)
```

---

## Shared Y-Axis Range

The matplotlib version uses:

```python
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
```

In Chart.js, compute a common Y range and apply it to both chart options.

```ts
private calculateSharedYBounds(paths: SupertrendPath[]): { min: number; max: number } {
  const values = paths.flatMap(entry => entry.path);

  if (values.length === 0) {
    return { min: -5, max: 5 };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = Math.max((max - min) * 0.1, 1);

  return {
    min: Math.floor(min - padding),
    max: Math.ceil(max + padding)
  };
}
```

Apply the result to both charts:

```ts
y: {
  min: yBounds.min,
  max: yBounds.max,
  title: {
    display: true,
    text: '% change'
  }
}
```

---

## Custom Legends and Counts

Do not use Chart.js' built-in legend for the signal paths. It would try to show one legend item per path, which is noisy.

Instead, hide Chart.js legend:

```ts
legend: {
  display: false
}
```

Then render Angular legend rows above each chart.

Endpoint counts:

```ts
endpointPositiveCount = paths.filter(path => path.endpoint_positive).length;
endpointNegativeCount = paths.length - endpointPositiveCount;
```

Mean counts:

```ts
meanPositiveCount = paths.filter(path => path.mean_positive).length;
meanNegativeCount = paths.length - meanPositiveCount;
```

Render labels equivalent to Python:

```text
Positive endpoint ({count})
Negative endpoint ({count})
Positive mean ({count})
Negative mean ({count})
```

---

## Component Template Layout

Use CSS grid to recreate the matplotlib side-by-side layout.

```html
<section class="supertrend-chart-section">
  <h2>
    SuperTrend Signal Paths — {{ ticker }} ({{ timeframe }}) — {{ paths.length }} total
  </h2>

  <div class="charts-grid">
    <article class="chart-card">
      <div class="legend-row">
        <span class="legend-item">
          <span class="legend-swatch positive"></span>
          Positive endpoint ({{ endpointPositiveCount }})
        </span>
        <span class="legend-item">
          <span class="legend-swatch negative"></span>
          Negative endpoint ({{ endpointNegativeCount }})
        </span>
      </div>

      <div class="chart-container">
        <canvas
          baseChart
          [type]="'line'"
          [data]="endpointChartData"
          [options]="endpointChartOptions">
        </canvas>
      </div>
    </article>

    <article class="chart-card">
      <div class="legend-row">
        <span class="legend-item">
          <span class="legend-swatch positive"></span>
          Positive mean ({{ meanPositiveCount }})
        </span>
        <span class="legend-item">
          <span class="legend-swatch negative"></span>
          Negative mean ({{ meanNegativeCount }})
        </span>
      </div>

      <div class="chart-container">
        <canvas
          baseChart
          [type]="'line'"
          [data]="meanChartData"
          [options]="meanChartOptions">
        </canvas>
      </div>
    </article>
  </div>
</section>
```

---

## Component Styling

```css
.supertrend-chart-section {
  width: 100%;
}

.supertrend-chart-section h2 {
  text-align: center;
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.chart-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 0.75rem;
  background: #fff;
}

.chart-container {
  position: relative;
  height: 500px;
  width: 100%;
}

.legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: center;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.legend-swatch {
  width: 24px;
  height: 3px;
  display: inline-block;
}

.legend-swatch.positive {
  background: rgba(0, 128, 0, 0.8);
}

.legend-swatch.negative {
  background: rgba(220, 0, 0, 0.8);
}

@media (max-width: 900px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
```

---

## Chart.js Registration

For standalone Angular setup, register Chart.js providers in the app config.

Example:

```ts
import { ApplicationConfig } from '@angular/core';
import { provideCharts, withDefaultRegisterables } from 'ng2-charts';

export const appConfig: ApplicationConfig = {
  providers: [
    provideCharts(withDefaultRegisterables())
  ]
};
```

If the app is module-based, use the module import pattern documented by `ng2-charts` instead.

---

## Parent Component Flow

Recommended UI flow:

1. User selects or clicks a ticker in the stock list.
2. Angular calls the SuperTrend path analysis endpoint.
3. Parent component stores the response.
4. Parent passes `ticker`, `timeframe`, and `paths` into `SupertrendPathsChartComponent`.

Example:

```ts
selectedTicker = '';
selectedTimeframe = '1h';
supertrendPaths: SupertrendPath[] = [];

loadSupertrendPaths(ticker: string): void {
  this.selectedTicker = ticker;

  this.screenerService
    .getSupertrendPaths(ticker, this.selectedTimeframe)
    .subscribe(response => {
      this.supertrendPaths = response.paths;
    });
}
```

Template:

```html
<app-supertrend-paths-chart
  *ngIf="supertrendPaths.length > 0"
  [ticker]="selectedTicker"
  [timeframe]="selectedTimeframe"
  [paths]="supertrendPaths">
</app-supertrend-paths-chart>
```

---

## Python-to-Chart.js Mapping

| Python matplotlib | Angular Chart.js |
|---|---|
| `plt.subplots(1, 2, figsize=(16, 6), sharey=True)` | CSS grid with two `<canvas>` charts and shared Y bounds |
| `ax1.plot(entry["path"])` | One line dataset per path |
| `endpoint_positive` color selection | Dataset `borderColor` in endpoint chart |
| `mean_positive` color selection | Dataset `borderColor` in mean chart |
| `color="green"` | `rgba(0, 128, 0, 0.3)` |
| `color="red"` | `rgba(220, 0, 0, 0.3)` |
| `linewidth=0.8` | `borderWidth: 1` |
| `alpha=0.3` | RGBA alpha channel |
| `axhline(0, linestyle="--")` | Dashed zero-line dataset |
| `set_xlabel("Hours since signal")` | `scales.x.title.text` |
| `set_ylabel("% change")` | `scales.y.title.text` |
| `grid(True)` | `scales.x.grid.display` and `scales.y.grid.display` |
| `legend([...])` | Custom Angular legend row with counts |
| `fig.suptitle(...)` | Section `<h2>` above both charts |

---

## Performance Notes

The Python code currently uses:

```python
all_paths = build_all_supertrend_paths(df_with_supertrend, max_hours=40, max_paths=100)
```

That is a good browser-friendly default.

For Chart.js, use:

- `animation: false`
- `parsing: false`
- `normalized: true`
- `pointRadius: 0`
- `pointHoverRadius: 0`
- `borderWidth: 1`
- no built-in legend for every dataset

Recommended path limits:

- 100 paths: should be smooth.
- 200-300 paths: probably acceptable depending on device.
- 500+ paths: consider downsampling, pagination, or rendering aggregated paths only.

If the API may return many paths, add a frontend cap:

```ts
const visiblePaths = paths.slice(0, 200);
```

Or expose `max_paths` as a backend query parameter:

```text
GET /api/analysis/supertrend-paths/TSLA?timeframe=1h&max_paths=100&max_hours=40
```

---

## Edge Cases

Handle these explicitly:

1. **No paths**
   - Show an empty-state message.
   - Do not render misleading zero-only charts.

2. **Single path**
   - Shared Y-bound calculation still works.
   - Add minimum padding so the line is visible.

3. **Paths with different lengths**
   - This is expected because extraction stops when SuperTrend flips bearish.
   - Each dataset gets its own X values from `0` to `path.length - 1`.

4. **Zero or flat values**
   - Add minimum Y padding to avoid a collapsed scale.

5. **Large responses**
   - Disable animations and points.
   - Cap visible paths if needed.

6. **Backend returns `path_percent` instead of `path`**
   - Normalize the frontend adapter to one internal field before charting.

---

## Validation Checklist

After implementation, validate:

1. **Dependency install**

```powershell
cd C:\Users\laszlb\projects\stockscreener\angular-client
npm install
```

2. **Angular build**

```powershell
cd C:\Users\laszlb\projects\stockscreener\angular-client
npm run build
```

3. **Angular tests**

```powershell
cd C:\Users\laszlb\projects\stockscreener\angular-client
npm test
```

4. **Manual smoke test**

```powershell
cd C:\Users\laszlb\projects\stockscreener\angular-client
npm start
```

Then open the app, choose a ticker with SuperTrend history, and confirm:

- Two charts appear side by side on desktop.
- Charts stack on narrow screens.
- Endpoint chart colors by final path value.
- Mean chart colors by average path value.
- Positive/negative counts match backend data.
- Zero line is dashed gray.
- Y-axis is shared between charts.
- X-axis represents hours since signal.
- Tooltips show hour and percent change.

---

## Suggested Implementation Order

1. Add `chart.js` and `ng2-charts`.
2. Register Chart.js providers.
3. Add TypeScript response interfaces.
4. Add Angular service method.
5. Create `SupertrendPathsChartComponent`.
6. Add dataset builder functions.
7. Add shared Y-axis calculation.
8. Add custom legends/counts.
9. Wire the component into the stock-list or analysis page.
10. Run build/tests and smoke-test with a real ticker.

---

## Stock List Analyze Column and Routed Chart Flow

Add the charting feature as a user action from the existing stock list table.

The stock list currently has these columns:

- `Symbol`
- `Exchange`
- `Chart`
- `Historical Prices`

Add a new column named:

```text
Analyze
```

Each row should include an `Analyze` link for that stock symbol. Clicking the link should navigate to a new Angular analysis view/page, load the REST analysis data for that ticker, show a loading message while the request is in progress, and render the new Chart.js component once data is received.

---

### Recommended Route

Use Angular Router for the analysis page rather than opening the REST endpoint directly in the browser.

Recommended frontend route:

```text
/analyze/:ticker
```

Example links:

```text
/analyze/AAPL
/analyze/MSFT
/analyze/TSLA
```

The Angular route then calls the backend endpoint internally:

```text
GET /api/analysis/bmsb-supertrend/{ticker}
```

This keeps the user in the Angular app and lets the UI show loading, error, empty, and chart states.

---

### Stock List Table Change

Update `angular-client/src/app/components/stock-list/stock-list.component.html` so the table header includes the new column.

Current header:

```html
<th>Symbol</th>
<th>Exchange</th>
<th>Chart</th>
<th>Historical Prices</th>
```

Recommended header:

```html
<th>Symbol</th>
<th>Exchange</th>
<th>Chart</th>
<th>Analyze</th>
<th>Historical Prices</th>
```

For every row, add an `Analyze` link using the row ticker dynamically:

```html
<td>
  <a [routerLink]="['/analyze', stock.symbol]">
    Analyze
  </a>
</td>
```

Recommended row order:

```html
<td>{{ stock.symbol }}</td>
<td>{{ stock.exchange }}</td>
<td>
  <a *ngIf="hasValidExchange(stock)"
     [href]="getTradingViewUrl(stock)"
     target="_blank"
     rel="noopener noreferrer">
    View on TradingView
  </a>
</td>
<td>
  <a [routerLink]="['/analyze', stock.symbol]">
    Analyze
  </a>
</td>
<td>
  <button class="load-btn" (click)="openDialog(stock)">
    Load Historical Prices Into DB
  </button>
</td>
```

If `stock-list.component.ts` is standalone, ensure it imports `RouterLink` from `@angular/router`.

Example:

```ts
import { RouterLink } from '@angular/router';

@Component({
  // ...existing code...
  imports: [
    // ...existing imports...
    RouterLink
  ]
})
export class StockListComponent {
  // ...existing code...
}
```

If the component is module-based, import `RouterModule` in the owning Angular module instead.

---

### Analyze Page Component

Create a routed page component responsible for loading analysis data.

Recommended files:

```text
angular-client/src/app/components/analyze-page/
  analyze-page.component.ts
  analyze-page.component.html
  analyze-page.component.css
```

Responsibilities:

- Read `ticker` from the route parameter.
- Call the analysis REST endpoint through `ScreenerService`.
- Show a loading message while the REST call is pending.
- Show an error message if the request fails.
- Show an empty message if the response has no paths.
- Render `SupertrendPathsChartComponent` when paths are available.

Recommended state fields:

```ts
ticker = '';
timeframe = '1h';
loading = false;
error = false;
analysis?: SupertrendPathsResponse;
```

Recommended flow:

```ts
ngOnInit(): void {
  this.route.paramMap
    .pipe(
      map(params => params.get('ticker') ?? ''),
      filter(ticker => ticker.length > 0),
      distinctUntilChanged(),
      switchMap(ticker => {
        this.ticker = ticker;
        this.loading = true;
        this.error = false;
        this.analysis = undefined;

        return this.screenerService.getBmsbSupertrendAnalysis(ticker).pipe(
          finalize(() => {
            this.loading = false;
          }),
          catchError(() => {
            this.error = true;
            return of(undefined);
          })
        );
      })
    )
    .subscribe(response => {
      this.analysis = response;
    });
}
```

Use the actual service method name chosen during implementation. The preferred name is:

```ts
getBmsbSupertrendAnalysis(ticker: string)
```

---

### Analyze Page Template

The routed analysis page should own the loading state and render the chart component only after data is available.

Recommended template:

```html
<section class="analyze-page">
  <a routerLink="/" class="back-link">← Back to stock list</a>

  <h1>Analyze {{ ticker }}</h1>

  <div *ngIf="loading" class="loading" data-testid="analysis-loading">
    Loading analysis for {{ ticker }}…
  </div>

  <div *ngIf="!loading && error" class="error-message" data-testid="analysis-error">
    Unable to load analysis for {{ ticker }}. Please try again later.
  </div>

  <div
    *ngIf="!loading && !error && analysis && analysis.paths.length === 0"
    class="empty-message"
    data-testid="analysis-empty">
    No SuperTrend signal paths are available for {{ ticker }}.
  </div>

  <app-supertrend-paths-chart
    *ngIf="!loading && !error && analysis && analysis.paths.length > 0"
    [ticker]="ticker"
    [timeframe]="analysis.timeframe || timeframe"
    [paths]="analysis.paths">
  </app-supertrend-paths-chart>
</section>
```

This gives the requested behavior:

1. User clicks `Analyze` in the stock-list table.
2. Angular navigates to `/analyze/{ticker}`.
3. The analysis page opens immediately.
4. A loading message is displayed.
5. REST data is requested from the backend.
6. When data arrives, the Chart.js component is rendered.

---

### Analyze Page Styling

Recommended minimal styling:

```css
.analyze-page {
  padding: 1rem;
}

.back-link {
  display: inline-block;
  margin-bottom: 1rem;
}

.loading,
.error-message,
.empty-message {
  margin: 1rem 0;
  padding: 1rem;
  border-radius: 6px;
}

.loading {
  background: #eef5ff;
}

.error-message {
  background: #ffecec;
  color: #8a1f1f;
}

.empty-message {
  background: #fff8df;
}
```

---

### Router Configuration

Add a route for the new analysis page.

Recommended routes:

```ts
export const routes: Routes = [
  {
    path: '',
    component: StockListComponent
  },
  {
    path: 'analyze/:ticker',
    component: AnalyzePageComponent
  },
  {
    path: '**',
    redirectTo: ''
  }
];
```

If the app currently renders `StockListComponent` directly in `AppComponent`, update `AppComponent` to render a router outlet instead:

```html
<router-outlet></router-outlet>
```

Then ensure the Angular app is bootstrapped with router providers.

Standalone setup example:

```ts
bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(routes),
    provideHttpClient(),
    provideCharts(withDefaultRegisterables())
  ]
});
```

Adjust this to match the existing Angular bootstrap style in the project.

---

### Service Method for Analyze Page

Use a typed service method that calls the backend analysis endpoint with the ticker from the route.

Recommended method:

```ts
getBmsbSupertrendAnalysis(ticker: string) {
  return this.http.get<SupertrendPathsResponse>(
    `/api/analysis/bmsb-supertrend/${encodeURIComponent(ticker)}`
  );
}
```

If timeframe, `max_hours`, or `max_paths` become configurable later, add them as query parameters:

```ts
getBmsbSupertrendAnalysis(
  ticker: string,
  options: { timeframe?: string; maxHours?: number; maxPaths?: number } = {}
) {
  let params = new HttpParams();

  if (options.timeframe) {
    params = params.set('timeframe', options.timeframe);
  }

  if (options.maxHours) {
    params = params.set('max_hours', options.maxHours);
  }

  if (options.maxPaths) {
    params = params.set('max_paths', options.maxPaths);
  }

  return this.http.get<SupertrendPathsResponse>(
    `/api/analysis/bmsb-supertrend/${encodeURIComponent(ticker)}`,
    { params }
  );
}
```

---

### Loading, Error, and Empty State Contract

The new routed analysis page should explicitly handle these states:

| State | UI behavior |
|---|---|
| Initial navigation | Page opens with ticker in title |
| Loading | Show `Loading analysis for {ticker}…` |
| Success with paths | Render `SupertrendPathsChartComponent` |
| Success without paths | Show empty message |
| REST error | Show error message |
| New ticker route clicked | Clear previous analysis and show loading again |

Important detail: clear the previous `analysis` value before starting a new request so stale charts are not displayed under the new ticker while loading.

---

### Updated Implementation Order

Replace the earlier high-level wiring step with this more specific flow:

1. Add `chart.js` and `ng2-charts`.
2. Register Chart.js providers.
3. Enable Angular Router if not already enabled.
4. Add TypeScript response interfaces.
5. Add `ScreenerService.getBmsbSupertrendAnalysis(ticker)`.
6. Create `SupertrendPathsChartComponent`.
7. Create routed `AnalyzePageComponent`.
8. Add `/analyze/:ticker` route.
9. Update `AppComponent` to use `router-outlet` if needed.
10. Add `Analyze` column to `stock-list.component.html`.
11. Add per-row `[routerLink]="['/analyze', stock.symbol]"` link.
12. Add loading, error, and empty states to the analysis page.
13. Run build/tests and smoke-test by clicking `Analyze` for a real ticker.

---

### Updated Validation Checklist

Add these checks to the validation process:

1. Stock-list table includes an `Analyze` column.
2. Every stock row has an `Analyze` link.
3. The link URL contains the row ticker, for example `/analyze/TSLA`.
4. Clicking `Analyze` opens the analysis page without a full browser reload.
5. The analysis page shows `Loading analysis for TSLA…` while waiting for REST data.
6. The Angular service calls `/api/analysis/bmsb-supertrend/TSLA` or the configured equivalent endpoint.
7. Previous chart data is cleared when navigating to a different ticker.
8. The chart component renders only after paths are received.
9. Empty responses show an empty-state message.
10. Failed REST requests show an error-state message.
11. Browser back navigation returns to the stock list.
12. Existing `View on TradingView` and `Load Historical Prices Into DB` actions still work.

---

### Suggested Unit and Component Tests

Add or update Angular tests for:

1. `StockListComponent`
   - Renders the `Analyze` table header.
   - Renders one `Analyze` link per stock row.
   - Uses the correct dynamic router link for each symbol.

2. `ScreenerService`
   - Calls `/api/analysis/bmsb-supertrend/{ticker}`.
   - URL-encodes ticker symbols.

3. `AnalyzePageComponent`
   - Reads the ticker route parameter.
   - Shows the loading message while the request is pending.
   - Renders `SupertrendPathsChartComponent` after data arrives.
   - Shows an error message on REST failure.
   - Shows an empty message when `paths` is empty.

4. `SupertrendPathsChartComponent`
   - Builds endpoint-colored datasets correctly.
   - Builds mean-colored datasets correctly.
   - Adds the dashed zero-line dataset.
   - Uses shared Y-axis bounds for both charts.

---

## Summary

The Angular Chart.js version should treat each Python `entry["path"]` as one Chart.js line dataset.

The endpoint chart differs from the mean chart only by which boolean controls the line color:

- Endpoint chart: `entry.endpoint_positive`
- Mean chart: `entry.mean_positive`

Everything else — X-axis, Y-axis, zero line, opacity, line width, grid, and title — maps directly from the matplotlib code.
