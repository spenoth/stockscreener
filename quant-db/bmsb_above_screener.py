"""
BMSB Above Screener — Wave 1 production implementation.

Features implemented:
  F-01  Per-ticker scan logging (structured stdout, every ticker logged)
  F-02  Run outcome classification (success / warning / error persisted on version row)

Business rules honoured:
  BR-1  Every active ticker produces exactly one log entry per run.
  BR-2  Exception isolation — one ticker failure never stops the run.
  BR-3  Version row always created at run start (before any ticker is scanned).
  BR-4  Outcome = success when scanned==total, warning when 0<scanned<total, error when scanned==0.
"""

import sys
import os
import logging
import certifi
import ssl
from datetime import datetime, timezone, timedelta

import psycopg2
import pandas as pd
import pandas_ta as ta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

os.environ["SSL_CERT_FILE"] = r"c:\Users\laszlb\Downloads\combined.pem"  # Fix SSL issues on some platforms
print("Default verify paths =", ssl.get_default_verify_paths())


from config import API_KEY, API_SECRET, DB_CONFIG

# ---------------------------------------------------------------------------
# Logging — structured plain text to stdout
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s",
)
log = logging.getLogger(__name__)

WATCHLIST_NAME = "BMSB_ABOVE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log_ticker(run_timestamp: str, symbol: str, scan_status: str,
               pass_result: str | None = None, error_message: str | None = None) -> None:
    """Emit one structured log line for a ticker (F-01)."""
    parts = [
        f"run_timestamp={run_timestamp}",
        f"symbol={symbol}",
        f"scan_status={scan_status}",
    ]
    if pass_result is not None:
        parts.append(f"pass_result={pass_result}")
    if error_message is not None:
        parts.append(f"error_message={error_message!r}")
    log.info(" | ".join(parts))


def determine_outcome(total: int, scanned: int) -> str:
    """Classify run outcome per BR-4."""
    if scanned == 0:
        return "error"
    if scanned == total:
        return "success"
    return "warning"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log.info(f"=== BMSB screener run started at {run_timestamp} ===")

    # --- DB connection ---
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as exc:
        log.error(f"FATAL: cannot connect to database: {exc}")
        sys.exit(1)

    # --- Alpaca client ---
    client = StockHistoricalDataClient(API_KEY, API_SECRET)

    # --- Watchlist id ---
    cur.execute("SELECT id FROM quant.watchlists WHERE name = %s", (WATCHLIST_NAME,))
    row = cur.fetchone()
    if row is None:
        log.error(f"FATAL: watchlist '{WATCHLIST_NAME}' not found in quant.watchlists")
        cur.close()
        conn.close()
        sys.exit(1)
    watchlist_id = row[0]

    # --- Next version number ---
    cur.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM quant.watchlist_versions WHERE watchlist_id = %s",
        (watchlist_id,),
    )
    version = cur.fetchone()[0]

    # --- Create version row BEFORE any scanning (BR-3) ---
    try:
        cur.execute(
            """
            INSERT INTO quant.watchlist_versions (watchlist_id, version)
            VALUES (%s, %s)
            RETURNING id
            """,
            (watchlist_id, version),
        )
        watchlist_version_id = cur.fetchone()[0]
        conn.commit()
    except Exception as exc:
        log.error(f"FATAL: could not create watchlist_versions row: {exc}")
        cur.close()
        conn.close()
        sys.exit(1)

    log.info(f"version={version} watchlist_version_id={watchlist_version_id}")

    # --- Load active tickers (F-01 / BR-1) ---
    cur.execute("SELECT symbol FROM quant.tickers WHERE active = true ORDER BY symbol")
    tickers = [r[0] for r in cur.fetchall()]
    total_tickers = len(tickers)
    log.info(f"total_tickers={total_tickers}")

    # --- Time window ---
    end = datetime.now(timezone.utc) - timedelta(minutes=60)
    start = end - timedelta(weeks=55)

    # --- Scan loop ---
    scanned_count = 0
    failed_count = 0

    for symbol in tickers:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Week,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(request).data.get(symbol, [])

            if len(bars) < 30:
                scanned_count += 1  # we processed it, just insufficient data → fail
                log_ticker(run_timestamp, symbol, "succeeded", pass_result="fail")
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
                        """
                        INSERT INTO quant.watchlist_items (watchlist_version_id, ticker)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (watchlist_version_id, symbol),
                    )
                    conn.commit()
                except Exception as db_exc:
                    conn.rollback()
                    # Item insert failure is non-fatal (section 7.2); log and continue
                    log_ticker(run_timestamp, symbol, "failed",
                               error_message=f"DB insert failed: {db_exc}")
                    failed_count += 1
                    continue

            scanned_count += 1
            log_ticker(run_timestamp, symbol, "succeeded",
                       pass_result="pass" if is_above else "fail")

        except Exception as exc:
            # BR-2: isolate ticker failures
            failed_count += 1
            log_ticker(run_timestamp, symbol, "failed", error_message=str(exc))
            try:
                conn.rollback()
            except Exception:
                pass

    # --- Classify outcome (BR-4) and persist (F-02) ---
    run_outcome = determine_outcome(total_tickers, scanned_count)
    log.info(
        f"run_outcome={run_outcome} "
        f"total_tickers={total_tickers} "
        f"scanned_count={scanned_count} "
        f"failed_count={failed_count}"
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
        log.error(f"ERROR: could not persist run_outcome to watchlist_versions: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass

    cur.close()
    conn.close()
    log.info(f"=== Run complete: version={version} outcome={run_outcome} ===")


if __name__ == "__main__":
    run()

