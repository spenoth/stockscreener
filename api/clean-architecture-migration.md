# API Clean Architecture Migration Plan

## Purpose

This document describes a staged migration of the API toward a cleaner architecture. The goal is to make the API easier to understand, test, and change without rewriting it or changing its externally visible behavior.

The current [`main.py`](./main.py) combines FastAPI setup, endpoint handling, database access, Alpaca calls, screener orchestration, analysis, logging, and process-wide configuration. The recommended direction is a **modular monolith**: keep one deployable API, but separate responsibilities into modules with clear boundaries.

## Architectural principles

- **Single responsibility:** Routes handle HTTP concerns; services coordinate application workflows; repositories own database queries; integrations own vendor-specific clients.
- **Dependency direction:** Routes depend on services. Services depend on defined data-access and integration boundaries. Infrastructure details should not leak into routes or calculation code.
- **Explicit side effects:** Database connections, external API calls, and application startup configuration should be visible at their boundaries, not triggered as incidental import-time behavior.
- **Testability:** Workflows should be testable with controlled repository and integration dependencies, without requiring a live database or Alpaca connection.
- **Incremental change:** Move and isolate existing behavior before considering redesigns. Avoid broad abstractions and preserve API contracts unless a behavior change is separately agreed.

## Proposed structure

This is a destination, not a requirement to create every module at once:

```text
api/
  main.py                  # Compatibility entry point; exports app
  app/
    factory.py             # FastAPI construction, middleware, lifespan
    routes/                 # Health, screener, prices, analysis
    services/               # Screener, ingestion, and analysis workflows
    repositories/           # SQL queries and persistence
    integrations/           # Alpaca client boundary
    core/                   # Settings, logging, error handling
  analyzer/                 # Existing calculation modules, retained initially
  tests/
```

Keep the existing analyzer modules as the calculation layer during this migration. Separate the API's workflow orchestration from the calculations before considering any changes to the algorithms.

## Migration phases

### 1. Establish behavior to preserve

Before moving code, document and test the current routes, status codes, response shapes, and important side effects. Existing API tests in [`tests/test_api.py`](./tests/test_api.py) cover health and current BMSB results; expand them to cover price retrieval, analysis responses, Alpaca failures, and screener-job outcomes.

Treat the Angular client's paths and response expectations in [`screener.service.ts`](../angular-client/src/app/services/screener.service.ts) as compatibility constraints. Capture the analysis response shape as well, even if it is not currently consumed by every client.

### 2. Separate application startup from endpoint code

Move FastAPI construction, middleware, lifespan handling, and exception handling into an application factory or bootstrap module. Keep `api/main.py` exporting `app` so the existing `uvicorn main:app` Docker startup command continues to work.

Move logging and settings initialization out of route modules. Importing a route should not perform unrelated process-wide or network-related mutations.

### 3. Isolate database access

Introduce a small connection dependency and focused repositories for watchlist results and price data. Move SQL out of endpoint and screener-job code, and centralize connection and cursor cleanup.

Preserve the current queries and transaction behavior initially. In particular, changing the screener job's commit frequency or atomicity could change partial-failure behavior; make such changes separately and intentionally. Classify database connectivity failures consistently so routes can return the established error responses.

### 4. Extract workflows into services

Keep routes focused on input validation, calling a service, and translating its result into the existing HTTP contract. Extract the BMSB screener workflow, Alpaca price ingestion, and BMSB/SuperTrend analysis orchestration into separate services.

Keep calculations in [`analyzer/supertrend_bmsb_analyzer_dbprices.py`](./analyzer/supertrend_bmsb_analyzer_dbprices.py) and [`analyzer/trademetrics.py`](./analyzer/trademetrics.py) for now. Do not duplicate or redesign the algorithms as part of this structural migration.

### 5. Make integrations and configuration explicit

Put Alpaca client construction behind an integration boundary so workflows can be tested without network access. Consolidate configuration into an explicit settings object while preserving existing environment-variable names.

Remove the application-level `certifi.where` monkey-patch as part of this phase. The API Dockerfile already configures CA bundle environment variables; preserve that deployment behavior. If local corporate-CA support is required, configure it explicitly rather than mutating a dependency at import time.

### 6. Strengthen contracts after the moves

Once tests capture current outputs, introduce typed request and response models where they clarify the API. Apply them carefully, especially to the analysis response, so serialization does not unintentionally change its keys or values.

Preserve existing paths, response keys, and status-code semantics unless a behavior change is intentionally approved. Run focused API tests after each extraction, then validate the Docker startup path.

## Risks and separately scoped decisions

- **Analysis fetch failures:** The analysis route currently catches a price-fetch error and continues as though the data frames exist. The fetch helper can raise `SystemExit` when data is missing, which is not handled by the global `Exception` handler. Add tests and define the desired API error response; address this as an explicit correctness fix during the analysis-service migration.
- **Background job lifecycle:** The screener is started in an untracked daemon thread, so repeated requests can start overlapping jobs. Preserve this behavior during the structural migration. Consider queuing, duplicate-run prevention, and lifecycle management as separate reliability work.
- **Fixed price retrieval dates:** The price retrieval route uses a fixed date range ending in 2025. Preserve it during this refactor and decide separately whether the range should be dynamic.
- **Transaction semantics:** Changing per-ticker commits or failure handling could change which results remain persisted after a partial run. Preserve current semantics until a separate decision is made.

## Validation and completion criteria

The migration is complete when:

1. Existing API paths, response shapes, and status codes remain covered by tests and unchanged, except for explicitly approved behavior fixes.
2. Routes no longer own SQL or workflow orchestration.
3. Services can be tested with database and external-service dependencies controlled by the tests.
4. Database and cursor resources are closed reliably on both success and failure.
5. Importing the application does not unexpectedly mutate third-party library behavior.
6. The existing Docker command still starts the API successfully.
7. The Angular client continues to work against the existing API contracts.

No microservice split or algorithm rewrite is required. The intended outcome is a smaller, clearer API composition layer with focused modules and explicit boundaries.
