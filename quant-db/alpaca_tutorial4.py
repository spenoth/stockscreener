import psycopg2
import pandas as pd
import pandas_ta as ta

DB_CONFIG = {
    "host": "localhost",
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypassword"
}

# --- DB CONNECTION ---
conn = psycopg2.connect(**DB_CONFIG)

# --- GET TICKERS ---
tickers_df = pd.read_sql(
    "SELECT symbol FROM tickers WHERE active = true",
    conn
)

tickers = tickers_df["symbol"].tolist()

print(f"Processing {len(tickers)} tickers...")

# --- LOOP TICKERS ---
for ticker in tickers:
    print(f"Processing {ticker}...")

    # --- LOAD WEEKLY PRICES ---
    df = pd.read_sql(
        """
        SELECT timestamp, open, high, low, close, volume
        FROM prices
        WHERE ticker = %s AND timeframe = '1w'
        ORDER BY timestamp ASC
        """,
        conn,
        params=(ticker,)
    )

    if df.empty or len(df) < 30:
        print(f"Skipping {ticker} (not enough data)")
        continue

    # --- PREPARE ---
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    # --- INDICATORS ---
    df["sma20"] = ta.sma(df["close"], length=20)
    df["ema21"] = ta.ema(df["close"], length=21)

    # --- DROP NA (first rows)
    df = df.dropna()

    # --- CALCULATE STATE ---
    df["state"] = df.apply(
        lambda row: "above"
        if row["close"] > row["sma20"] and row["close"] > row["ema21"]
        else "below",
        axis=1
    )

    # --- INSERT EVENTS ---
    cur = conn.cursor()

    for ts, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO events (
                ticker,
                timestamp,
                timeframe,
                event_type,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                ticker,
                ts,
                "1w",
                "BMSB_STATE",
                f'{{"state": "{row["state"]}"}}'
            )
        )

    conn.commit()
    cur.close()

conn.close()