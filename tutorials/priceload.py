from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pandas as pd
import psycopg2
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "XXXXXXXXXXXXXXXXXX"
API_SECRET = "XXXXXXXXXXXXXXXXXXXXXS"

# PKYKFACHR7CTONZOMWC2OT66MD
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypassword"
}

# --- DB CONNECTION ---
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# --- ALPACA CLIENT ---
client = StockHistoricalDataClient(API_KEY, API_SECRET)

# --- GET TICKERS ---
cur.execute("SELECT symbol FROM quant.tickers WHERE active = true")
tickers = [row[0] for row in cur.fetchall()]

print(f"Loading {len(tickers)} tickers...")

# --- TIME RANGES ---
start = pd.Timestamp("2016-01-01", tz="America/New_York")
end   = pd.Timestamp("2025-12-31", tz="America/New_York")

# --- INSERT FUNCTION ---
def insert_bars(symbol, bars, timeframe_str):
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
                symbol,
                bar.timestamp,
                timeframe_str,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume
            )
        )

# --- MAIN LOOP ---
for symbol in tickers:
    print(f"Fetching {symbol}...")

    try:
        # --- 1H DATA ---
        request_1h = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start,
            end=end
        )

        bars_1h = client.get_stock_bars(request_1h).data.get(symbol, [])
        insert_bars(symbol, bars_1h, "1h")

        # --- 1W DATA ---
        request_1w = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Week,
            start=start,
            end=end
        )

        bars_1w = client.get_stock_bars(request_1w).data.get(symbol, [])
        insert_bars(symbol, bars_1w, "1w")

        conn.commit()

    except Exception as e:
        print(f"Error with {symbol}: {e}")
        conn.rollback()

cur.close()
conn.close()