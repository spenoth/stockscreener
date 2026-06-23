import argparse

import numpy as np
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt

from datetime import datetime
import pytz

import psycopg2

def calculate_supertrend(
        df,
        length=10,
        multiplier=3.0
):
    """
    Calculates the SuperTrend indicator and appends it to the dataframe.

    SuperTrend is a trend-following indicator based on ATR (Average True Range).
    It switches between bullish (+1) and bearish (-1) direction when price
    crosses the upper or lower band.

    Args:
        df (pd.DataFrame): OHLCV dataframe with columns: open, high, low, close.
        length (int):      ATR period used for band calculation. Default: 10.
        multiplier (float): ATR multiplier that controls band width. Default: 3.0.

    Returns:
        pd.DataFrame: Copy of the input dataframe with two additional columns:
            - supertrend:           the raw SuperTrend line value (price level)
            - supertrend_direction: +1 = bullish trend, -1 = bearish trend
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
    Finds all timestamps where the SuperTrend flips from bearish to bullish.

    A bullish start is defined as:
        - previous bar: supertrend_direction == -1  (bearish)
        - current bar:  supertrend_direction == +1  (bullish)

    These crossover points are used as trade entry signals.

    Args:
        df (pd.DataFrame): Dataframe with a 'supertrend_direction' column.

    Returns:
        list: Index values (timestamps) where a bearish -> bullish flip occurs.
    """

    direction = df["supertrend_direction"]

    # Boolean mask: True only where the previous bar was -1 and current bar is +1
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
    Extracts the sequence of closing prices starting from a bullish signal.

    Walks forward bar by bar from the signal timestamp and collects closing
    prices until one of the following exit conditions is met:
        1. The SuperTrend flips back to bearish (direction == -1)
        2. The maximum number of hours (bars) is reached
        3. The end of the dataframe is reached

    Note: The first bar (entry bar) is never counted as a bearish exit,
    so a signal that immediately flips would still produce at least 1 close.

    Args:
        df (pd.DataFrame):      Dataframe with 'close' and 'supertrend_direction'.
        start_timestamp:        Index value marking the entry bar.
        max_hours (int):        Maximum number of bars to include. Default: 40.

    Returns:
        list[float]: Sequence of closing prices from entry until exit.
    """

    # Locate the integer position of the entry bar
    start_pos = df.index.get_loc(start_timestamp)

    closes = []

    for offset in range(max_hours + 1):

        pos = start_pos + offset

        # Stop if we've walked past the end of the dataframe
        if pos >= len(df):
            break

        row = df.iloc[pos]

        closes.append(row["close"])

        # Stop after the first bar if the trend has already reversed
        # (offset > 0 prevents the entry bar itself from triggering an exit)
        if (
                offset > 0
                and row["supertrend_direction"] == -1
        ):
            break

    return closes

def normalize_path(closes):
    """
    Converts a sequence of raw closing prices into percentage changes
    relative to the first (entry) price.

    Formula per bar:  ((price / base) - 1) * 100
    This is equivalent to:  ((price - base) / base) * 100

    Example:
        closes = [100, 105, 95, 110]
        result = [0.0, 5.0, -5.0, 10.0]

    Args:
        closes (list[float]): Raw closing prices starting from the entry bar.

    Returns:
        list[float]: Percentage change from entry for each bar.
                     First element is always 0.0.
    """

    if len(closes) == 0:
        return []

    base = closes[0]

    return [
        (price / base - 1) * 100
        for price in closes
    ]

def classify_path(normalized_path):
    """
    Classifies a normalized path as positive or negative using two independent methods.

    Methods:
        - Endpoint: looks at the last value only.
                    Answers: "Did this trade close in profit?"
                    Best for evaluating final trade outcome.

        - Mean:     looks at the average of all values.
                    Answers: "Was this trade mostly above entry during its lifetime?"
                    Useful for assessing holding comfort, even if it ended well.

    Args:
        normalized_path (list[float]): % change values from normalize_path().

    Returns:
        dict with keys:
            - endpoint_positive (bool):  True if the path ended above entry
            - mean_positive     (bool):  True if the average value was above entry
            - endpoint          (float): Final % value
            - mean               (float): Average % value across the path
    """

    endpoint = normalized_path[-1]
    mean     = sum(normalized_path) / len(normalized_path)

    return {
        "endpoint_positive": endpoint > 0,
        "mean_positive":     mean > 0,
        "endpoint":          endpoint,
        "mean":              mean,
    }

def build_all_supertrend_paths(
        df,
        max_hours=40,
        max_paths=None
):
    """
    Builds the full dataset of SuperTrend signal paths with classifications.

    For every bullish SuperTrend start in the dataframe:
        1. Extracts the raw price path (extract_supertrend_path)
        2. Normalizes it to % change from entry (normalize_path)
        3. Classifies it by endpoint and mean (classify_path)
        4. Bundles path + classification into a single dict

    Args:
        df (pd.DataFrame): Dataframe with SuperTrend columns already calculated.
        max_hours (int):   Maximum bars to include per path. Default: 40.
        max_paths (int):   If set, only processes the first N signals. Default: all.

    Returns:
        list[dict]: One dict per signal, each containing:
            - path               (list[float]): normalized % change values
            - endpoint_positive  (bool):        did the path end above entry?
            - mean_positive      (bool):        was the path mostly above entry?
            - endpoint           (float):       final % value
            - mean               (float):       average % value
    """

    starts = find_supertrend_starts(df)

    # Optionally cap the number of signals to process
    if max_paths is not None:
        starts = starts[:max_paths]

    results = []

    for timestamp in starts:

        closes = extract_supertrend_path(
            df,
            timestamp,
            max_hours=max_hours
        )

        # Skip signals with only 1 bar — no meaningful path to analyze
        if len(closes) < 2:
            continue

        normalized = normalize_path(closes)
        classification = classify_path(normalized)

        # Merge the path and its classification into one dict
        results.append({
            "path": normalized,
            **classification
        })

    return results

# =========================
# CLI ARGUMENTS
# =========================
# Parse the ticker symbol from the command line so the same script can be
# reused for any symbol stored in the quant.prices table.
parser = argparse.ArgumentParser(
    description="Run SuperTrend signal-path analysis for a given ticker."
)
parser.add_argument(
    "ticker",
    type=str,
    help="Ticker symbol to analyze (e.g. TSLA, AAPL, NVDA).",
)
parser.add_argument(
    "--timeframe",
    type=str,
    default="1h",
    help="Price timeframe to fetch from the database. Default: 1h.",
)
args = parser.parse_args()

# Normalize ticker to uppercase to match the convention used in the database
ticker = args.ticker.upper()
timeframe = args.timeframe

# =========================
# TIME RANGE
# =========================
# Define the date range for filtering (used if fetching from Alpaca or similar APIs)
start = pd.Timestamp("2016-01-01", tz="America/New_York")
end   = pd.Timestamp("2025-12-31", tz="America/New_York")

# =========================
# DATABASE CONNECTION
# =========================
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypassword"
}

# Connect to PostgreSQL and fetch hourly OHLCV prices for the requested ticker
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute(
    "select timestamp, open, high, low, close "
    "from quant.prices "
    "where ticker=%s and timeframe=%s "
    "order by timestamp asc",
    (ticker, timeframe),
)
rows = cur.fetchall()

if not rows:
    raise SystemExit(
        f"No price data found for ticker={ticker!r} timeframe={timeframe!r}."
    )

# Build a dataframe from the raw query results
df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])

# psycopg2 returns Decimal types — convert to float for numeric operations
for col in ["open", "high", "low", "close"]:
    df[col] = pd.to_numeric(df[col])

# =========================
# SUPERTREND CALCULATION
# =========================
# Append supertrend and supertrend_direction columns to the dataframe
df_with_supertrend = calculate_supertrend(df)
print("Dataframe with SuperTrend columns:")
print(df_with_supertrend.head(10))
print(df_with_supertrend.tail(10))

# =========================
# BUILD ALL PATHS
# =========================
# Extract, normalize, and classify every bullish SuperTrend signal in the data
all_paths = build_all_supertrend_paths(df_with_supertrend, max_hours=40, max_paths=100)

print(f"Total normalized paths: {len(all_paths)}")

# =========================
# PLOT
# =========================
# Two side-by-side charts comparing endpoint vs mean classification
# Green = positive signal, Red = negative signal
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

# --- Left plot: color-coded by endpoint (final % value) ---
for entry in all_paths:
    color = "green" if entry["endpoint_positive"] else "red"
    ax1.plot(entry["path"], color=color, linewidth=0.8, alpha=0.3)

ax1.axhline(0, color="gray", linestyle="--", linewidth=1)
ax1.set_title("By Endpoint (last value)")
ax1.set_xlabel("Hours since signal")
ax1.set_ylabel("% change")
ax1.grid(True)

n_pos_ep = sum(e["endpoint_positive"] for e in all_paths)
ax1.legend([
    plt.Line2D([0], [0], color="green"),
    plt.Line2D([0], [0], color="red"),
], [
    f"Positive endpoint ({n_pos_ep})",
    f"Negative endpoint ({len(all_paths) - n_pos_ep})",
])

# --- Right plot: color-coded by mean (average % across the path) ---
for entry in all_paths:
    color = "green" if entry["mean_positive"] else "red"
    ax2.plot(entry["path"], color=color, linewidth=0.8, alpha=0.3)

ax2.axhline(0, color="gray", linestyle="--", linewidth=1)
ax2.set_title("By Mean (mostly above or below entry)")
ax2.set_xlabel("Hours since signal")
ax2.grid(True)

n_pos_mean = sum(e["mean_positive"] for e in all_paths)
ax2.legend([
    plt.Line2D([0], [0], color="green"),
    plt.Line2D([0], [0], color="red"),
], [
    f"Positive mean ({n_pos_mean})",
    f"Negative mean ({len(all_paths) - n_pos_mean})",
])

fig.suptitle(f"SuperTrend Signal Paths — {ticker} ({timeframe}) — {len(all_paths)} total", fontsize=13)
plt.tight_layout()
plt.show()
