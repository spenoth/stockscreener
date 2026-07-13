from dataclasses import asdict
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
from analyzers.supertrend_bmsb_analyzer_dbprices import attach_bmsb_to_hourly, build_all_supertrend_paths_bmsb_filtered, calculate_bmsb, calculate_supertrend, fetch_prices
from analyzers.trademetrics import TradeAnalyzer
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

    logger.info("ALPAKA KEY IS %s", ALPACA_API_KEY)
    logger.info("ALPAKA SECRET IS %s", ALPACA_API_SECRET)
    
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