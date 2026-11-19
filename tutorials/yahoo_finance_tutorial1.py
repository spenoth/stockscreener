import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime

# from tutorials.alpaca_tutorial4 import ticker

# =========================
# CONFIG
# =========================
CSV_FILE = "tickers.csv"
OUTPUT_DIR = Path("yahoo_hourly")

START_DATE = "2010-01-01"
END_DATE   = "2012-12-31"

INTERVAL = "1h"

# chunk size (Yahoo ignores very large ranges for intraday)
CHUNK_DAYS = 60

OUTPUT_DIR.mkdir(exist_ok=True)


# =========================
# DATE CHUNKER
# =========================
def date_range_chunks(start, end, chunk_days):
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    current = start

    while current < end:
        next_date = min(current + pd.Timedelta(days=chunk_days), end)
        yield current, next_date
        current = next_date


# =========================
# DOWNLOAD FUNCTION
# =========================
def download_symbol(symbol):
    print(f"\nDownloading {symbol}")

    all_data = []

    for start, end in date_range_chunks(START_DATE, END_DATE, CHUNK_DAYS):

        print(f"  {start.date()} -> {end.date()}")

        try:
            df = yf.download(
                symbol,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=INTERVAL,
                auto_adjust=True,
                progress=False,
                threads=False
            )

            if df is not None and not df.empty:
                all_data.append(df)

        except Exception as e:
            print(f"    ERROR: {e}")

    if not all_data:
        print("  No data returned")
        return None

    df = pd.concat(all_data)

    # clean duplicates + sort
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()

    return df


# =========================
# MAIN
# =========================
def main():

    # tickers = pd.read_csv(CSV_FILE)
    #
    # for _, row in tickers.iterrows():
    #     symbol = row["ticker"]
    #
    #     df = download_symbol(symbol)
    #
    #     if df is None:
    #         continue
    #
    #     out_file = OUTPUT_DIR / f"{symbol}_1h.parquet"
    #     df.to_parquet(out_file)

    symbol = "AAPL"
    df = download_symbol(symbol)
    print(df.head())
    print(df.tail())
    # print(f"Saved {symbol}: {len(df):,} rows -> {out_file}")


if __name__ == "__main__":
    main()