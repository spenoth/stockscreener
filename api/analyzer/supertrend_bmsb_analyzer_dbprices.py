import pandas as pd
import pandas_ta as ta

# =========================
# SUPERTREND CORE FUNCTIONS
# =========================
# These are identical to those in supertrend_analyzer_dbprices.py — kept here
# so this script is self-contained and can be run on its own.

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
    Finds all index positions where the SuperTrend flips from bearish to bullish.

    A bullish start is defined as:
        - previous bar: supertrend_direction == -1  (bearish)
        - current bar:  supertrend_direction == +1  (bullish)

    Args:
        df (pd.DataFrame): Dataframe with a 'supertrend_direction' column.

    Returns:
        list: Index values where a bearish -> bullish flip occurs.
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
    Extracts the sequence of closing prices starting from a bullish signal.

    Walks forward bar by bar from the signal until one of:
        1. The SuperTrend flips back to bearish
        2. max_hours bars have been collected
        3. The end of the dataframe is reached

    Args:
        df (pd.DataFrame):      Dataframe with 'close' and 'supertrend_direction'.
        start_timestamp:        Index value marking the entry bar.
        max_hours (int):        Maximum bars to include. Default: 40.

    Returns:
        list[float]: Closing prices from entry until exit.
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
    Converts raw closing prices into % change vs. the first (entry) price.

    Example:
        closes = [100, 105, 95, 110]
        result = [0.0, 5.0, -5.0, 10.0]

    Returns:
        list[float]: % change from entry. First element is always 0.0.
    """

    if len(closes) == 0:
        return []

    base = closes[0]

    return [
        (price / base - 1)
        for price in closes
    ]


def classify_path(normalized_path):
    """
    Classifies a normalized path by endpoint and by mean.

    Returns:
        dict with endpoint_positive, mean_positive, endpoint, mean.
    """

    endpoint = normalized_path[-1]
    mean     = sum(normalized_path) / len(normalized_path)

    return {
        "endpoint_positive": endpoint > 0,
        "mean_positive":     mean > 0,
        "endpoint":          endpoint,
        "mean":              mean,
    }


# =========================
# BMSB (Bull Market Support Band)
# =========================

def calculate_bmsb(weekly_df):
    """
    Calculates the Bull Market Support Band on weekly OHLCV data.

    The BMSB is defined as the band between:
        - 20-week Simple Moving Average (SMA20) of the weekly close
        - 21-week Exponential Moving Average (EMA21) of the weekly close

    Price is considered to be "above the BMSB" when the weekly close is
    strictly above BOTH lines. This is the same rule used by the project's
    BMSB screener (quant-db/bmsb_above_screener.py).

    Args:
        weekly_df (pd.DataFrame): Weekly OHLCV dataframe with at least a
            'close' column and a 'timestamp' column, sorted ascending.

    Returns:
        pd.DataFrame: Copy of the input with three additional columns:
            - bmsb_sma20:  20-week SMA of close
            - bmsb_ema21:  21-week EMA of close
            - bmsb_above:  bool, True when close > sma20 AND close > ema21
    """

    result = weekly_df.copy()

    result["bmsb_sma20"] = ta.sma(result["close"], length=20)
    result["bmsb_ema21"] = ta.ema(result["close"], length=21)

    result["bmsb_above"] = (
            (result["close"] > result["bmsb_sma20"])
            &
            (result["close"] > result["bmsb_ema21"])
    )

    return result


def attach_bmsb_to_hourly(hourly_df, weekly_df_with_bmsb):
    """
    Attaches the most recent weekly BMSB status to every hourly bar.

    For each hourly bar at timestamp T, we look up the most recent weekly
    bar whose timestamp is <= T (a backward as-of join). The resulting row
    gets that weekly bar's bmsb_sma20 / bmsb_ema21 / bmsb_above values.

    Notes:
        - Hourly bars that occur before the first valid weekly BMSB
          (i.e. before there are 21 weeks of history) will have NaN values
          which downstream code must treat as "BMSB unknown -> filter out".
        - Following the project convention used by bmsb_above_screener.py,
          the "current" (still-forming) weekly bar's close is used. This is
          slightly look-ahead in a backtest, but matches what the live
          screener would see at the time of the signal.

    Args:
        hourly_df (pd.DataFrame):           Hourly bars with a 'timestamp' column.
        weekly_df_with_bmsb (pd.DataFrame): Weekly bars already enriched with
                                            bmsb_sma20 / bmsb_ema21 / bmsb_above.

    Returns:
        pd.DataFrame: Copy of hourly_df with bmsb_sma20, bmsb_ema21, bmsb_above
                      columns added.
    """

    # merge_asof requires both inputs to be sorted on the join key
    h = hourly_df.sort_values("timestamp").reset_index(drop=True)

    w = (
        weekly_df_with_bmsb[["timestamp", "bmsb_sma20", "bmsb_ema21", "bmsb_above"]]
        .dropna(subset=["bmsb_sma20", "bmsb_ema21"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    merged = pd.merge_asof(
        h,
        w,
        on="timestamp",
        direction="backward",
    )

    return merged


# =========================
# PATH BUILDER (BMSB-filtered)
# =========================

def build_all_supertrend_paths_bmsb_filtered(
        df,
        max_hours=40,
        max_paths=None
):
    """
    Builds normalized SuperTrend paths, keeping ONLY signals fired while the
    underlying weekly price was above the Bull Market Support Band.

    For every bullish SuperTrend flip:
        1. Check the 'bmsb_above' flag on the signal bar.
        2. If False (or NaN), skip the signal entirely.
        3. Otherwise extract / normalize / classify the path as usual.

    Args:
        df (pd.DataFrame): Hourly dataframe enriched with both SuperTrend
                           columns AND a 'bmsb_above' column.
        max_hours (int):   Max bars per path. Default: 40.
        max_paths (int):   If set, cap the number of qualifying paths.

    Returns:
        tuple:
            list[dict]: One dict per qualifying signal (path + classification).
            dict:       Summary stats {total_signals, bmsb_above, bmsb_below_or_unknown}.
    """

    all_starts = find_supertrend_starts(df)

    # Vectorized BMSB lookup at each signal bar — NaN is treated as "not above".
    bmsb_flags = (
        df.loc[all_starts, "bmsb_above"]
          .fillna(False)
          .astype(bool)
          .tolist()
    )

    qualifying_starts = [
        ts
        for ts, above in zip(all_starts, bmsb_flags)
        if above
    ]

    stats = {
        "total_signals":          len(all_starts),
        "bmsb_above":             sum(bmsb_flags),
        "bmsb_below_or_unknown":  len(all_starts) - sum(bmsb_flags),
    }

    if max_paths is not None:
        qualifying_starts = qualifying_starts[:max_paths]

    results = []

    for timestamp in qualifying_starts:

        closes = extract_supertrend_path(
            df,
            timestamp,
            max_hours=max_hours,
        )

        # Skip signals with only the entry bar — no meaningful path.
        if len(closes) < 2:
            continue

        normalized = normalize_path(closes)
        classification = classify_path(normalized)

        results.append({
            "timestamp": timestamp,
            "path":      normalized,
            "path_percent": [p * 100 for p in normalized],
            **classification,
        })

    return results, stats


# =========================
# DATABASE HELPERS
# =========================

def fetch_prices(cur, ticker, timeframe):
    """
    Fetches OHLC prices for a given ticker / timeframe from quant.prices.

    Args:
        cur:                 psycopg2 cursor.
        ticker (str):        Uppercase ticker symbol.
        timeframe (str):     One of the values in quant.timeframe_enum
                             (e.g. '1h', '1d', '1w').

    Returns:
        pd.DataFrame: Columns [timestamp, open, high, low, close], sorted
                      ascending by timestamp, with numeric dtypes.
    """

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

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])

    # psycopg2 returns Decimal types — convert to float for numeric operations
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    return df

def print_summary(summary):
    print("=" * 60)
    print("SIGNAL PERFORMANCE SUMMARY")
    print("=" * 60)

    print(f"Number of Trades          : {summary['num_trades']}")
    print(f"Win Rate                  : {summary['win_rate']:.2%}")
    print()

    print(f"Average Winner            : {summary['avg_win']:.2%}")
    print(f"Average Loser             : {summary['avg_loss']:.2%}")
    print(f"Expectancy / Trade        : {summary['expectancy']:.2%}")
    print()

    print(f"Average MFE               : {summary['avg_mfe']:.2%}")
    print(f"Average Drawdown (Winner) : {summary['avg_drawdown_winners']:.2%}")
    print(f"Average Drawdown (Loser)  : {summary['avg_drawdown_losers']:.2%}")

    print("=" * 60)
