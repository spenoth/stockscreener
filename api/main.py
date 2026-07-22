import os
import threading

from dataclasses import asdict
from datetime import datetime, timezone, timedelta

from analyzer.supertrend_bmsb_analyzer_dbprices import (
    calculate_supertrend, calculate_bmsb,
    attach_bmsb_to_hourly, build_all_supertrend_paths_bmsb_filtered,
    fetch_prices,
)
from analyzer.trademetrics import TradeAnalyzer

# Force the corporate CA bundle for ALL outbound HTTPS (requests, urllib3, Alpaca SDK).
# Must be set before any network-using library is imported/initialized.
_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
os.environ["REQUESTS_CA_BUNDLE"] = _CA_BUNDLE
os.environ["SSL_CERT_FILE"] = _CA_BUNDLE
os.environ["CURL_CA_BUNDLE"] = _CA_BUNDLE

# The Alpaca SDK calls certifi.where() directly when building its requests.Session,
# which bypasses the REQUESTS_CA_BUNDLE env var entirely.
# Monkey-patch certifi so it returns the system CA bundle (which includes Zscaler).
import certifi
certifi.where = lambda: _CA_BUNDLE

import logging
import logging.handlers
import time
import traceback
from contextlib import asynccontextmanager

import pandas as pd
import psycopg2
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    CORS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGIN_REGEX, CORS_ALLOW_CREDENTIALS,
    ALPACA_API_KEY, ALPACA_API_SECRET,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s UTC %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logging.Formatter.converter = time.gmtime
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connectivity
    try:
        conn = get_connection()
        conn.close()
        logger.info(
            "Database connection verified on startup (host=%s port=%s dbname=%s)",
            DB_HOST, DB_PORT, DB_NAME,
        )
    except Exception as exc:
        logger.error(
            "STARTUP FAILED: cannot connect to database at %s:%s/%s — %s",
            DB_HOST, DB_PORT, DB_NAME, exc,
        )
        raise RuntimeError(
            f"Cannot connect to database at {DB_HOST}:{DB_PORT}/{DB_NAME}"
        ) from exc
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )



# ---------------------------------------------------------------------------
# Global exception handler — ensures no raw tracebacks leak into responses
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s: %s\n%s",
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# BMSB Screener — background job
# ---------------------------------------------------------------------------

WATCHLIST_NAME = "BMSB_ABOVE"


def _run_bmsb_screener_job():
    """
    Replicates bmsb_above_screener.py logic.
    Runs in a background thread — all errors are caught and logged.
    """
    import pandas_ta as ta

    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("=== BMSB screener job started at %s ===", run_timestamp)

    try:
        conn = get_connection()
        cur = conn.cursor()
    except Exception as exc:
        logger.error("BMSB job FATAL: cannot connect to database: %s", exc)
        return

    try:
        client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_API_SECRET)

        # Watchlist id
        cur.execute("SELECT id FROM quant.watchlists WHERE name = %s", (WATCHLIST_NAME,))
        row = cur.fetchone()
        if row is None:
            logger.error("BMSB job FATAL: watchlist '%s' not found", WATCHLIST_NAME)
            return
        watchlist_id = row[0]

        # Next version number
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM quant.watchlist_versions WHERE watchlist_id = %s",
            (watchlist_id,),
        )
        version = cur.fetchone()[0]

        # Create version row before scanning (BR-3)
        cur.execute(
            "INSERT INTO quant.watchlist_versions (watchlist_id, version) VALUES (%s, %s) RETURNING id",
            (watchlist_id, version),
        )
        watchlist_version_id = cur.fetchone()[0]
        conn.commit()
        logger.info("BMSB job version=%s watchlist_version_id=%s", version, watchlist_version_id)

        # Load active tickers
        cur.execute("SELECT symbol FROM quant.tickers WHERE active = true ORDER BY symbol")
        tickers = [r[0] for r in cur.fetchall()]
        total_tickers = len(tickers)
        logger.info("BMSB job total_tickers=%s", total_tickers)

        # Time window
        end_dt = datetime.now(timezone.utc) - timedelta(minutes=60)
        start_dt = end_dt - timedelta(weeks=55)

        scanned_count = 0
        failed_count = 0

        for symbol in tickers:
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Week,
                    start=start_dt,
                    end=end_dt,
                    feed="iex",
                )
                bars = client.get_stock_bars(request).data.get(symbol, [])

                if len(bars) < 30:
                    scanned_count += 1
                    logger.info(
                        "run_timestamp=%s | symbol=%s | scan_status=succeeded | pass_result=fail (insufficient data)",
                        run_timestamp, symbol,
                    )
                    continue

                df = pd.DataFrame([{"timestamp": b.timestamp, "close": b.close} for b in bars])
                df = df.sort_values("timestamp")
                df["sma20"] = ta.sma(df["close"], length=20)
                df["ema21"] = ta.ema(df["close"], length=21)
                df = df.dropna()

                latest = df.iloc[-1]
                is_above = (latest["close"] > latest["sma20"]) and (latest["close"] > latest["ema21"])

                if is_above:
                    try:
                        cur.execute(
                            "INSERT INTO quant.watchlist_items (watchlist_version_id, ticker) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (watchlist_version_id, symbol),
                        )
                        conn.commit()
                    except Exception as db_exc:
                        conn.rollback()
                        logger.error("BMSB job symbol=%s DB insert failed: %s", symbol, db_exc)
                        failed_count += 1
                        continue

                scanned_count += 1
                logger.info(
                    "run_timestamp=%s | symbol=%s | scan_status=succeeded | pass_result=%s",
                    run_timestamp, symbol, "pass" if is_above else "fail",
                )

            except Exception as exc:
                failed_count += 1
                logger.error("BMSB job symbol=%s failed: %s", symbol, exc)
                try:
                    conn.rollback()
                except Exception:
                    pass

        # Determine and persist outcome (BR-4)
        if scanned_count == 0:
            run_outcome = "error"
        elif scanned_count == total_tickers:
            run_outcome = "success"
        else:
            run_outcome = "warning"

        logger.info(
            "BMSB job run_outcome=%s total_tickers=%s scanned_count=%s failed_count=%s",
            run_outcome, total_tickers, scanned_count, failed_count,
        )

        try:
            cur.execute(
                """
                UPDATE quant.watchlist_versions
                SET run_outcome   = %s,
                    total_tickers = %s,
                    scanned_count = %s,
                    failed_count  = %s
                WHERE id = %s
                """,
                (run_outcome, total_tickers, scanned_count, failed_count, watchlist_version_id),
            )
            conn.commit()
        except Exception as exc:
            logger.error("BMSB job ERROR: could not persist run_outcome: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass

        logger.info("=== BMSB screener job complete: version=%s outcome=%s ===", version, run_outcome)

    except Exception as exc:
        logger.error("BMSB job unhandled exception: %s\n%s", exc, traceback.format_exc())
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


@app.post("/api/screener/bmsb/run")
def trigger_bmsb_screener(request: Request):
    """
    Spawns a background thread that runs the BMSB screener job.
    Returns immediately with 202 Accepted.
    """
    t = threading.Thread(target=_run_bmsb_screener_job, daemon=True)
    t.start()
    logger.info("BMSB screener job spawned (thread id=%s)", t.ident)
    return JSONResponse(
        status_code=202,
        content={"detail": "BMSB screener job started", "status": "accepted"},
    )


# ---------------------------------------------------------------------------
# Current BMSB results
# ---------------------------------------------------------------------------

@app.get("/api/screener/bmsb/current")
def get_current_bmsb(request: Request):
    try:
        conn = get_connection()
    except Exception as exc:
        logger.error(
            "DB connectivity failure on %s: %s\n%s",
            request.url.path,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT symbol, exchange FROM quant.v_current_bmsb ORDER BY symbol;")
                rows = cur.fetchall()
        return [{"symbol": row[0], "exchange": row[1]} for row in rows]
    except Exception as exc:
        logger.error(
            "Query failure on %s: %s\n%s",
            request.url.path,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    finally:
        conn.close()

@app.get("/api/retriever/prices/{symbol}/{timeframe}")
def retrieve_historical_prices(request: Request, symbol: str, timeframe: str):
    """
    Retrieves historical price data for a given symbol from Alpaca and
    populates the quant.prices table.

    Path parameters:
      - symbol:    Ticker symbol, e.g. "AAPL"
      - timeframe: One of "1h" (hourly) or "1w" (weekly)

    Returns a summary of how many bars were fetched and inserted.
    """
    SUPPORTED_TIMEFRAMES = {
        "1h": TimeFrame.Hour,
        "1w": TimeFrame.Week,
    }

    if timeframe not in SUPPORTED_TIMEFRAMES:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Unsupported timeframe '{timeframe}'. Use one of: {list(SUPPORTED_TIMEFRAMES.keys())}"},
        )

    start = pd.Timestamp("2016-01-01", tz="America/New_York")
    end   = pd.Timestamp("2025-12-31", tz="America/New_York")

    # --- Fetch from Alpaca ---
    try:
        client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_API_SECRET)
        bar_request = StockBarsRequest(
            symbol_or_symbols=symbol.upper(),
            timeframe=SUPPORTED_TIMEFRAMES[timeframe],
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(bar_request).data.get(symbol.upper(), [])
    except Exception as exc:
        logger.error(
            "Alpaca fetch failure for %s/%s on %s: %s\n%s",
            symbol, timeframe, request.url.path, exc, traceback.format_exc(),
        )
        return JSONResponse(status_code=502, content={"detail": "Failed to fetch data from Alpaca"})

    if not bars:
        return {"symbol": symbol.upper(), "timeframe": timeframe, "inserted": 0, "message": "No data returned from Alpaca"}

    # --- Persist to DB ---
    try:
        conn = get_connection()
    except Exception as exc:
        logger.error(
            "DB connectivity failure on %s: %s\n%s",
            request.url.path, exc, traceback.format_exc(),
        )
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    try:
        with conn:
            with conn.cursor() as cur:
                for bar in bars:
                    cur.execute(
                        """
                        INSERT INTO quant.prices (
                            ticker, timestamp, timeframe,
                            open, high, low, close, volume
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, timestamp, timeframe) DO NOTHING
                        """,
                        (
                            symbol.upper(),
                            bar.timestamp,
                            timeframe,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                        ),
                    )
        logger.info("Inserted %d bars for %s/%s", len(bars), symbol.upper(), timeframe)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "inserted": len(bars)}
    except Exception as exc:
        logger.error(
            "DB insert failure for %s/%s on %s: %s\n%s",
            symbol, timeframe, request.url.path, exc, traceback.format_exc(),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    finally:
        conn.close()

@app.get("/api/analysis/bmsb-supertrend/{symbol}")
def retrieve_bmsb_supertrand_stats(request: Request, symbol: str):
    #Retrieve weekly and hourly prices from db
    try:
        conn = get_connection()
    except Exception as exc:
        logger.error(
            "DB connectivity failure on %s: %s\n%s",
            request.url.path, exc, traceback.format_exc(),
        )
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    try:
        with conn:
            with conn.cursor() as cur:
                start_time = time.time()
                df_hourly = fetch_prices(cur, symbol, "1h")
                df_weekly = fetch_prices(cur, symbol, "1w")
                end_time_db_fetch = time.time()
                logger.info ("Fetched hourly and weekly prices for %s. Took %d seconds", symbol, end_time_db_fetch-start_time)
    except Exception as exc:
        logger.error(
            "Could not fetch prices for %s", symbol
        )

    logger.debug(df_hourly.head(20))
    logger.debug(df_weekly.head(20))
    cur.close()
    conn.close()

    # INDICATOR CALCULATIONS
    # =========================
    # SuperTrend on the hourly series.
    df_hourly_st = calculate_supertrend(df_hourly)

    # BMSB on the weekly series.
    df_weekly_bmsb = calculate_bmsb(df_weekly)

    df_combined = attach_bmsb_to_hourly(df_hourly_st, df_weekly_bmsb)

    # =========================
    # BUILD BMSB-FILTERED PATHS
    # =========================
    all_paths, stats = build_all_supertrend_paths_bmsb_filtered(
        df_combined,
        max_hours=40,
        max_paths=200,
    )

    logger.info(
        f"SuperTrend signals — total: {stats['total_signals']}, "
        f"above BMSB: {stats['bmsb_above']}, "
        f"below/unknown BMSB: {stats['bmsb_below_or_unknown']}"
    )
    logger.info(f"Qualifying paths plotted: {len(all_paths)}")

    analyzer = TradeAnalyzer(all_paths)

    metrics = analyzer.analyze()

    paths_json = [
        {
            **p,
            "path": p["path"].tolist() if hasattr(p["path"], "tolist") else p["path"]
        }
        for p in all_paths
    ]

    return {
        "stats": stats,
        "paths": paths_json,
        "metrics": [asdict(m) for m in metrics],
        "summary": analyzer.summary(),
        "drawdown_percentiles": analyzer.drawdown_percentiles(),
        "mean_path": analyzer.mean_path(),
    }