import pytz

import psycopg2

import matplotlib.pyplot as plt


import argparse
import time

from api.analyzers.supertrend_bmsb_analyzer_dbprices import attach_bmsb_to_hourly, build_all_supertrend_paths_bmsb_filtered, calculate_bmsb, calculate_supertrend, fetch_prices, print_summary
from api.analyzers.trademetrics import TradeAnalyzer

# =========================
# CLI ARGUMENTS
# =========================
parser = argparse.ArgumentParser(
    description=(
        "Run SuperTrend signal-path analysis for a given ticker, keeping "
        "only signals fired while the weekly close is above the Bull Market "
        "Support Band (SMA20 + EMA21 weekly)."
    )
)
parser.add_argument(
    "ticker",
    type=str,
    default="TSLA",
    help="Ticker symbol to analyze (e.g. TSLA, AAPL, NVDA).",
)
parser.add_argument(
    "--timeframe",
    type=str,
    default="1h",
    help="Hourly timeframe used for SuperTrend. Default: 1h.",
)
parser.add_argument(
    "--weekly-timeframe",
    type=str,
    default="1w",
    help="Weekly timeframe used for BMSB. Default: 1w.",
)
args = parser.parse_args()

ticker           = args.ticker.upper()
timeframe        = args.timeframe
weekly_timeframe = args.weekly_timeframe

# =========================
# TIME RANGE (kept for parity with the original script)
# =========================
start = pd.Timestamp("2016-01-01", tz="America/New_York")
end   = pd.Timestamp("2025-12-31", tz="America/New_York")

# =========================
# DATABASE CONNECTION
# =========================
DB_CONFIG = {
    "host": "localhost",
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypassword",
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

start_time = time.time()

# Fetch hourly prices (for SuperTrend) and weekly prices (for BMSB).
df_hourly = fetch_prices(cur, ticker, timeframe)
df_weekly = fetch_prices(cur, ticker, weekly_timeframe)

end_time_db_fetch = time.time()

print("Time to fetch data took %d second", end_time_db_fetch - start_time)

cur.close()
conn.close()

print(f"Hourly bars fetched: {len(df_hourly)}")
print(f"Weekly bars fetched: {len(df_weekly)}")

# =========================
# INDICATOR CALCULATIONS
# =========================
# SuperTrend on the hourly series.
df_hourly_st = calculate_supertrend(df_hourly)

# BMSB on the weekly series.
df_weekly_bmsb = calculate_bmsb(df_weekly)

# Attach the latest weekly BMSB status to each hourly bar (backward as-of join).
df_combined = attach_bmsb_to_hourly(df_hourly_st, df_weekly_bmsb)

print("Combined hourly dataframe (head):")
print(df_combined.head(10))
print("Combined hourly dataframe (tail):")
print(df_combined.tail(10))

# =========================
# BUILD BMSB-FILTERED PATHS
# =========================
all_paths, stats = build_all_supertrend_paths_bmsb_filtered(
    df_combined,
    max_hours=40,
    max_paths=200,
)

print(
    f"SuperTrend signals — total: {stats['total_signals']}, "
    f"above BMSB: {stats['bmsb_above']}, "
    f"below/unknown BMSB: {stats['bmsb_below_or_unknown']}"
)
print(f"Qualifying paths plotted: {len(all_paths)}")

if not all_paths:
    raise SystemExit(
        "No SuperTrend signals occurred above the BMSB — nothing to plot."
    )

analyzer = TradeAnalyzer(all_paths)

metrics = analyzer.analyze()

print_summary(analyzer.summary())

# =========================
# PLOT
# =========================
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

fig.suptitle(
    f"SuperTrend Signal Paths ABOVE BMSB — {ticker} "
    f"({timeframe} / BMSB on {weekly_timeframe}) — "
    f"{len(all_paths)} of {stats['total_signals']} signals kept",
    fontsize=13,
)
plt.tight_layout()
plt.show()

