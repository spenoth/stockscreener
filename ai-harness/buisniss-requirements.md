# Business Requirements Specification (BRS)

**Project:** Weekly Stock Screener (Hobby)  
**Version:** 1.0 (Draft Baseline)  
**Date:** 2026-06-03  
**Owner:** Single user (project owner)

## 1. Purpose
Build a weekly stock screening capability that generates personal trade ideas by identifying stocks that pass a Bull Market Support Band (BMSB) rule and presenting only the latest valid results in an Angular client.

## 2. Business Objectives
- Generate actionable weekly trade ideas from a predefined ticker universe.
- Maintain a clear "current state" list of passing stocks based strictly on the latest screener version.
- Preserve historical run/version data for traceability and debugging.
- Enable future expansion to additional weekly screeners without changing core usage expectations.

## 3. Stakeholders
- Primary user: project owner (single end user, hobby use)
- Secondary stakeholder: operator/debugger role (same person)
- System consumers: Angular client (read-only current results), middleware/API

## 4. Scope

### In Scope (v1)
- One weekly screener: BMSB
- Input universe from `tickers` table
- Weekly batch scan of tickers
- Create new watchlist version per run
- Persist passing symbols as watchlist items for that version
- Expose latest-version passed symbols + exchange to Angular
- Angular displays list + TradingView redirect capability
- Logging for per-ticker scan outcome and pass/fail

### Out of Scope (v1)
- Authentication/authorization/security hardening
- Multi-user workflows
- Retry mechanisms
- Non-weekly screeners
- Advanced portfolio/order execution integration

## 5. Business Context and Definitions
- **Ticker Master Data:** `tickers` table is the source of truth for ticker metadata, including exchange.
- **Version:** A run-specific watchlist version identifier created on each screener run.
- **Latest Version:** The most recently created version, regardless of scan completeness.
- **Current Ideas:** Only items present in latest version; no fallback to older versions.
- **No-data State:** If latest version has no passed items, UI must show informational empty-state messaging.

## 6. Functional Business Requirements

- **BR-1 Weekly Screening**  
  System shall run a weekly BMSB screening process over tickers from `tickers`.

- **BR-2 Version Creation**  
  System shall create a new watchlist version for each run attempt/execution.

- **BR-3 Pass Persistence**  
  System shall persist entries only for tickers that pass the BMSB criteria in that run/version.

- **BR-4 Latest-Version Semantics**  
  System shall define "latest" strictly by most recently created version.  
  System shall not fallback to prior versions when latest has fewer/no items.

- **BR-5 Angular Data Contract (Business Level)**  
  Middleware shall provide Angular with the list of passed stocks from latest version.  
  Each returned stock shall include at least symbol and exchange (from `tickers` master data).

- **BR-6 UI Display Rule**  
  Angular shall display only current latest-version items.  
  If no items exist for latest version, Angular shall display "No stocks to show" informational message.

- **BR-7 Logging and Diagnosability**  
  System shall log, for each ticker:
    - scan attempted/succeeded/failed
    - pass/fail outcome (when scan succeeded)  
      Logs shall support local debugging and operational review.

- **BR-8 Extensibility Requirement**  
  System shall support adding more weekly screeners later without changing the core current-state interpretation model.

## 7. Run Outcome Classification (Business Rules)
- **Success:** all tickers scanned
- **Warning:** only part of tickers scanned
- **Error:** 0 tickers scanned

Note: This classification is operational/diagnostic and not required to be shown in Angular UI.

## 8. Non-Functional Requirements (Business-Relevant)
- **NFR-1 Usability:** End-user output is simple and focused: current passed stocks only.
- **NFR-2 Observability:** Logs must be sufficient to explain missing symbols and scan failures per run.
- **NFR-3 Portability:** Must run locally in IDE for debugging and be deployable in Linux Docker environment.
- **NFR-4 Data Freshness Integrity:** UI must represent only latest run data, even when that means empty results.
- **NFR-5 Maintainability:** Future weekly screeners should be addable with minimal disruption to existing flow.

## 9. Data Requirements (Business View)

### Inputs
- Ticker universe from `tickers`
- Market data from Alpaca feed (accepted for v1)

### Outputs
- Versioned watchlist records
- Current-view dataset for Angular: latest-version passed symbols + exchange

### Master Data Rule
- Exchange displayed/used for TradingView linking is sourced from `tickers`.

## 10. Assumptions
- BMSB formula implementation in existing logic is accepted as initial business logic baseline.
- Weekly cadence is sufficient for initial idea-generation use case.
- Single user and no security constraints are acceptable in v1.
- Latest-version rule remains strict, even under partial/incomplete scans.

## 11. Dependencies
- Alpaca market data availability
- PostgreSQL data model/tables for tickers, watchlist versions, watchlist items
- Middleware endpoint consumed by Angular
- Correct exchange values in `tickers` master data

## 12. Risks
- Partial scans can temporarily remove previously visible ideas (intentional behavior but user-visible).
- Incorrect/missing exchange in `tickers` leads to bad TradingView links.
- No retry policy may increase warning runs due to transient external failures.
- Strict latest-version rule may produce empty UI after problematic runs.

## 13. Acceptance Criteria (Business Acceptance)
- Weekly run can be executed and creates a new version.
- Latest-version query returns only stocks that passed in that latest version.
- Angular list shows only latest-version stocks; no historical fallback.
- Angular shows explicit empty-state message when latest version has zero items.
- Each displayed stock includes exchange from `tickers`.
- Per-ticker logging exists for scan success/failure and pass/fail outcomes.
- Run outcome (success/warning/error) is determinable from run statistics.

## 14. Open Items (to freeze before technical design)
- Final wording/content of empty-state UI message.
- Canonical mapping format for TradingView symbol construction from exchange + ticker.
- Confirmation of exact weekly run trigger mechanism (manual initially vs scheduled immediately).
