import psycopg2
import pandas as pd
import pandas_ta as ta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
# --- CONFIG ---
from config import API_KEY, API_SECRET

DB_CONFIG = {
    "host": "localhost",
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypassword"
}

WATCHLIST_NAME = "BMSB_ABOVE"

# ---------------- CONNECTIONS ----------------
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

client = StockHistoricalDataClient(API_KEY, API_SECRET)

# ---------------- GET WATCHLIST ID ----------------
cur.execute("""
    SELECT id FROM quant.watchlists
    WHERE name = %s
""", (WATCHLIST_NAME,))
watchlist_id = cur.fetchone()[0]

# ---------------- GET NEXT VERSION ----------------
cur.execute("""
    SELECT COALESCE(MAX(version), 0) + 1
    FROM quant.watchlist_versions
    WHERE watchlist_id = %s
""", (watchlist_id,))
version = cur.fetchone()[0]

print("New version:", version)

# create version row
cur.execute("""
    INSERT INTO quant.watchlist_versions (watchlist_id, version)
    VALUES (%s, %s)
    RETURNING id
""", (watchlist_id, version))

watchlist_version_id = cur.fetchone()[0]

conn.commit()

# ---------------- GET TICKERS ----------------
cur.execute("""
    SELECT symbol FROM quant.tickers WHERE active = true
""")

tickers = [r[0] for r in cur.fetchall()]

print(f"Tickers: {len(tickers)}")

# ---------------- TIME ----------------
# end = datetime.utcnow() - timedelta(days=2)
end = datetime.utcnow() - timedelta(minutes=60)
start = end - timedelta(weeks=55)

# ---------------- INSERT HELPERS ----------------
def insert_watchlist_item(ticker):
    cur.execute("""
        INSERT INTO quant.watchlist_items (watchlist_version_id, ticker)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (watchlist_version_id, ticker))

# ---------------- MAIN LOOP ----------------
for symbol in tickers:
    print(f"Processing {symbol}")

    try:
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Week,
            start=start,
            end=end,
            feed="iex"
        )

        bars = client.get_stock_bars(request).data.get(symbol, [])

        if len(bars) < 30:
            continue

        df = pd.DataFrame([{
            "timestamp": b.timestamp,
            "close": b.close
        } for b in bars])

        df = df.sort_values("timestamp")

        # -------- BMSB --------
        df["sma20"] = ta.sma(df["close"], length=20)
        df["ema21"] = ta.ema(df["close"], length=21)

        df = df.dropna()

        latest = df.iloc[-1]

        # -------- CONDITION --------
        is_above = (latest["close"] > latest["sma20"]) and (latest["close"] > latest["ema21"])

        if is_above:
            print(f"{symbol} -> ABOVE")

            insert_watchlist_item(symbol)

    except Exception as e:
        print(f"Error {symbol}: {e}")
        conn.rollback()

# ---------------- COMMIT ----------------
conn.commit()

cur.close()
conn.close()