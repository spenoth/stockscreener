import numpy as np
import pandas as pd
import pandas_ta as ta

from datetime import datetime
import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import API_KEY, API_SECRET

def calculate_supertrend(
        df,
        length=10,
        multiplier=3.0
):
    """
    Adds SuperTrend columns to dataframe.

    Returns:
        Original dataframe with:
            supertrend
            supertrend_direction
    """

    st = ta.supertrend(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
        multiplier=multiplier
    )

    direction_col = f"SUPERTd_{length}_{multiplier}"
    trend_col = f"SUPERT_{length}_{multiplier}"

    result = df.copy()

    result["supertrend"] = st[trend_col]
    result["supertrend_direction"] = st[direction_col]

    return result

def find_supertrend_starts(df):
    """
    Returns timestamps where
    SuperTrend switches bearish -> bullish.
    """

    direction = df["supertrend_direction"]

    mask = (
            (direction.shift(1) == -1)
            &
            (direction == 1)
    )

    return list(df.index[mask])

def extract_supertrend_path(
        df,
        start_timestamp,
        max_hours=40
):
    """
    Extract closes from signal start until:

    - bearish reversal
    - max_hours reached
    - dataframe end
    """

    start_pos = df.index.get_loc(start_timestamp)

    closes = []

    for offset in range(max_hours + 1):

        pos = start_pos + offset

        if pos >= len(df):
            break

        row = df.iloc[pos]

        closes.append(row["close"])

        if (
                offset > 0
                and row["supertrend_direction"] == -1
        ):
            break

    return closes

def normalize_path(closes):
    """
    Converts closes into % returns
    relative to first close.
    """

    if len(closes) == 0:
        return []

    base = closes[0]

    return [
        (price / base - 1) * 100
        for price in closes
    ]

def build_all_supertrend_paths(
        df,
        max_hours=40
):
    """
    Returns list of normalized paths.
    """

    starts = find_supertrend_starts(df)

    paths = []

    for timestamp in starts:

        closes = extract_supertrend_path(
            df,
            timestamp,
            max_hours=max_hours
        )

        if len(closes) < 2:
            continue

        normalized = normalize_path(closes)

        paths.append(normalized)

    return paths

client = StockHistoricalDataClient(API_KEY, API_SECRET)

# =========================
# TIME RANGE
# =========================
start = pd.Timestamp("2016-01-01", tz="America/New_York")
end   = pd.Timestamp("2025-12-31", tz="America/New_York")


# =========================
# REQUEST
# =========================
request = StockBarsRequest(
    symbol_or_symbols=["AAPL"],
    timeframe=TimeFrame.Hour,
    start=start,
    end=end,
    feed="sip"   # full market feed (important if you have access)
)

bars = client.get_stock_bars(request)

# =========================
# DATAFRAME
# =========================
df = bars.df




df_with_supertrend = calculate_supertrend(df)
print("Dataframe with SuperTrend columns:")
print(df_with_supertrend.head())
print(df_with_supertrend.tail())

starts = find_supertrend_starts(df)

print(len(starts))
print(starts[:5])

# assuming this just extracts one path?
path = extract_supertrend_path(
    df,
    starts[0]
)

print(path)
