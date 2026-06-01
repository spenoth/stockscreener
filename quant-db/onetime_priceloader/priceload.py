from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import psycopg2
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "XXXXXXXXXXXXXXXXXXX"
API_SECRET = "XXXXXXXXXXXXXXXXXXX"

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
cur.execute("SELECT symbol FROM tickers WHERE active = true")
tickers = [row[0] for row in cur.fetchall()]

print(f"Loading {len(tickers)} tickers...")

# --- TIME RANGES ---
now = datetime.utcnow()
start_1h = now - timedelta(days=180)   # ~6 months
start_1w = now - timedelta(days=365*3) # ~3 years

# --- INSERT FUNCTION ---
def insert_bars(symbol, bars, timeframe_str):
    for bar in bars:
        cur.execute(
            """
            INSERT INTO prices (
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
            start=start_1h,
            end=datetime.utcnow() - timedelta(minutes=60)
        )

        bars_1h = client.get_stock_bars(request_1h).data.get(symbol, [])
        insert_bars(symbol, bars_1h, "1h")

        # --- 1W DATA ---
        request_1w = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Week,
            start=start_1w,
            end=now
        )

        bars_1w = client.get_stock_bars(request_1w).data.get(symbol, [])
        insert_bars(symbol, bars_1w, "1w")

        conn.commit()

    except Exception as e:
        print(f"Error with {symbol}: {e}")
        conn.rollback()

cur.close()
conn.close()