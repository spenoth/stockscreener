import pandas as pd
from datetime import datetime
import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# =========================
# API KEYS
# =========================
API_KEY = "XXXXXXXXXXXX"
API_SECRET = "XXXXXXXXXXXXXXX"

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

print(df.head())
print(df.tail())
