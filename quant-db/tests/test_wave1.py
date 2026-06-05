"""
Tests for Wave 1 — Backend Data Layer.

Coverage:
  F-01  Per-ticker log output (every ticker, correct fields, isolation)
  F-02  Run outcome classification (BR-4)
  F-03  Exchange completeness verification query (unit-level)
  F-04  v_current_bmsb semantics (latest-version, empty-result, scoping)

External I/O (Alpaca API, PostgreSQL) is mocked so tests run without
live services.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Shim heavy dependencies before importing the screener
# ---------------------------------------------------------------------------

def _make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


import pandas as _real_pd  # import BEFORE shimming so tests can reference it

for _name in [
    "psycopg2", "pandas", "pandas_ta",
    "alpaca", "alpaca.data", "alpaca.data.historical",
    "alpaca.data.requests", "alpaca.data.timeframe",
]:
    if _name not in sys.modules:
        _make_module(_name)

# Provide minimal stubs used at import time
sys.modules["alpaca.data.historical"].StockHistoricalDataClient = MagicMock()
sys.modules["alpaca.data.requests"].StockBarsRequest = MagicMock()
sys.modules["alpaca.data.timeframe"].TimeFrame = MagicMock()

# Config stub
config_mod = types.ModuleType("config")
config_mod.API_KEY = "test_key"
config_mod.API_SECRET = "test_secret"
config_mod.DB_CONFIG = {
    "host": "localhost", "dbname": "testdb",
    "user": "testuser", "password": "testpassword", "port": 5432,
}
sys.modules["config"] = config_mod

# Now we can import the helpers we want to unit-test directly
import importlib
screener = importlib.import_module("bmsb_above_screener")


# ===========================================================================
# F-02 — Run outcome classification (BR-4)
# ===========================================================================

class TestDetermineOutcome(unittest.TestCase):

    def test_all_scanned_is_success(self):
        self.assertEqual(screener.determine_outcome(100, 100), "success")

    def test_none_scanned_is_error(self):
        self.assertEqual(screener.determine_outcome(100, 0), "error")

    def test_partial_scanned_is_warning(self):
        self.assertEqual(screener.determine_outcome(100, 50), "warning")
        self.assertEqual(screener.determine_outcome(100, 1), "warning")
        self.assertEqual(screener.determine_outcome(100, 99), "warning")

    def test_zero_tickers_zero_scanned_is_error(self):
        # Edge: empty universe — no tickers, none scanned
        self.assertEqual(screener.determine_outcome(0, 0), "error")


# ===========================================================================
# F-01 — Per-ticker log format
# ===========================================================================

class TestLogTicker(unittest.TestCase):

    def _capture_log(self, *args, **kwargs):
        import io
        import logging
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        orig_level = screener.log.level
        screener.log.setLevel(logging.DEBUG)
        screener.log.addHandler(handler)
        screener.log_ticker(*args, **kwargs)
        screener.log.removeHandler(handler)
        screener.log.setLevel(orig_level)
        return stream.getvalue()

    def test_succeeded_pass_contains_all_fields(self):
        out = self._capture_log("2026-06-03T10:00:00Z", "TSLA", "succeeded", pass_result="pass")
        self.assertIn("run_timestamp=2026-06-03T10:00:00Z", out)
        self.assertIn("symbol=TSLA", out)
        self.assertIn("scan_status=succeeded", out)
        self.assertIn("pass_result=pass", out)

    def test_failed_contains_error_message(self):
        out = self._capture_log("2026-06-03T10:00:00Z", "BAD", "failed",
                                error_message="timeout")
        self.assertIn("scan_status=failed", out)
        self.assertIn("error_message=", out)
        self.assertIn("timeout", out)

    def test_failed_has_no_pass_result(self):
        out = self._capture_log("2026-06-03T10:00:00Z", "BAD", "failed",
                                error_message="boom")
        self.assertNotIn("pass_result", out)

    def test_succeeded_fail_has_no_error_message(self):
        out = self._capture_log("2026-06-03T10:00:00Z", "XYZ", "succeeded", pass_result="fail")
        self.assertNotIn("error_message", out)


# ===========================================================================
# F-01 + F-02 — Full run integration (mocked DB + Alpaca)
# ===========================================================================

def _make_bar(close):
    b = MagicMock()
    b.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    b.close = close
    return b


def _make_df_with_sufficient_bars(close_above=True):
    """Return a DataFrame that will pass or fail the BMSB condition."""
    import pandas as pd_real
    n = 50
    closes = [100.0] * n
    df = pd_real.DataFrame({"timestamp": range(n), "close": closes})
    # sma20 = ema21 = 100; if above set close[-1] slightly higher
    if close_above:
        df.loc[df.index[-1], "close"] = 110.0
    else:
        df.loc[df.index[-1], "close"] = 90.0
    return df


class TestRunIntegration(unittest.TestCase):
    """End-to-end mock test: two tickers, one passes, one fails on API error."""

    def _build_mocks(self):
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cur

        # fetchone sequence: watchlist_id, version, watchlist_version_id
        cur.fetchone.side_effect = [
            (1,),   # watchlist_id
            (3,),   # next version
            (42,),  # watchlist_version_id
        ]
        # fetchall: two active tickers
        cur.fetchall.return_value = [("AAPL",), ("BADTICKER",)]
        return conn, cur

    @patch("bmsb_above_screener.ta")
    @patch("bmsb_above_screener.pd")
    @patch("bmsb_above_screener.StockHistoricalDataClient")
    @patch("bmsb_above_screener.psycopg2")
    def test_one_pass_one_api_error(self, mock_psycopg2, mock_client_cls,
                                    mock_pd, mock_ta):
        conn, cur = self._build_mocks()
        mock_psycopg2.connect.return_value = conn

        client_instance = MagicMock()
        mock_client_cls.return_value = client_instance

        # AAPL: returns 40 bars
        bars_aapl = [_make_bar(100.0)] * 40
        # BADTICKER: raises exception
        def side_effect(request):
            sym = request.symbol_or_symbols
            result = MagicMock()
            if sym == "AAPL":
                result.data.get.return_value = bars_aapl
            else:
                raise RuntimeError("symbol not found")
            return result

        client_instance.get_stock_bars.side_effect = side_effect

        # Make pandas work minimally — return a MagicMock df that behaves correctly
        real_pd = _real_pd
        n = 40
        df_base = real_pd.DataFrame({
            "timestamp": range(n),
            "close": [100.0] * n,
        })
        df_sorted = df_base.copy()
        df_sorted["sma20"] = 95.0
        df_sorted["ema21"] = 94.0
        df_sorted = df_sorted.copy()
        df_sorted.loc[df_sorted.index[-1], "close"] = 110.0

        mock_df = MagicMock(wraps=df_sorted)
        mock_df.__len__ = MagicMock(return_value=n)
        mock_df.sort_values = MagicMock(return_value=df_sorted)
        mock_df.dropna = MagicMock(return_value=df_sorted)
        mock_df.__setitem__ = MagicMock()
        mock_pd.DataFrame.return_value = mock_df

        mock_ta.sma.return_value = real_pd.Series([95.0] * n)
        mock_ta.ema.return_value = real_pd.Series([94.0] * n)

        captured_logs = []
        original_log_ticker = screener.log_ticker

        def capturing_log_ticker(*args, **kwargs):
            captured_logs.append((args, kwargs))
            original_log_ticker(*args, **kwargs)

        with patch.object(screener, "log_ticker", side_effect=capturing_log_ticker):
            screener.run()

        # Version row must have been updated with outcome
        update_calls = [c for c in cur.execute.call_args_list
                        if "UPDATE quant.watchlist_versions" in str(c)]
        self.assertTrue(len(update_calls) >= 1, "run_outcome UPDATE must be issued")

        # Both tickers must have been logged (BR-1)
        logged_symbols = [args[0][1] for args in captured_logs]
        self.assertIn("AAPL", logged_symbols)
        self.assertIn("BADTICKER", logged_symbols)

        # BADTICKER must be logged as failed (BR-2)
        badticker_entries = [a for a in captured_logs if a[0][1] == "BADTICKER"]
        self.assertEqual(len(badticker_entries), 1)
        self.assertEqual(badticker_entries[0][0][2], "failed")


# ===========================================================================
# F-03 — Exchange completeness (unit tests for the SQL contract)
# ===========================================================================

class TestExchangeCompleteness(unittest.TestCase):
    """Verify init.sql contains the exchange verification contract."""

    def _init_sql(self):
        import pathlib
        return (pathlib.Path(__file__).parent.parent / "init.sql").read_text()

    def test_fix_sql_file_exists(self):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "init.sql"
        self.assertTrue(path.exists(), f"init.sql not found at {path}")

    def test_fix_sql_contains_verification_query(self):
        content = self._init_sql()
        self.assertIn("active_tickers_missing_exchange", content)
        self.assertIn("active = true", content)
        self.assertIn("exchange IS NULL", content)


# ===========================================================================
# F-04 — v_current_bmsb view definition checks
# ===========================================================================

class TestViewDefinition(unittest.TestCase):
    """Verify init.sql defines the view correctly."""

    def _view_sql(self):
        import pathlib
        return (pathlib.Path(__file__).parent.parent / "init.sql").read_text()

    def test_view_file_exists(self):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "init.sql"
        self.assertTrue(path.exists())

    def test_view_selects_symbol_and_exchange(self):
        sql = self._view_sql()
        self.assertIn("symbol", sql)
        self.assertIn("exchange", sql)

    def test_view_scoped_to_bmsb_above(self):
        sql = self._view_sql()
        self.assertIn("BMSB_ABOVE", sql)

    def test_view_joins_tickers_for_exchange(self):
        sql = self._view_sql()
        self.assertIn("quant.tickers", sql)

    def test_view_uses_latest_version_semantics(self):
        # Must order by created_at DESC (BR-7)
        sql = self._view_sql()
        self.assertIn("created_at DESC", sql)

    def test_view_no_watchlist_items_exchange_column(self):
        # Exchange must come from tickers, not watchlist_items (BR-5)
        sql = self._view_sql()
        self.assertNotIn("watchlist_items.exchange", sql)


# ===========================================================================
# F-02 — init.sql has required run-outcome columns
# ===========================================================================

class TestMigrationColumns(unittest.TestCase):

    def _migration_sql(self):
        import pathlib
        return (pathlib.Path(__file__).parent.parent / "init.sql").read_text()

    def test_run_outcome_column_added(self):
        self.assertIn("run_outcome", self._migration_sql())

    def test_total_tickers_column_added(self):
        self.assertIn("total_tickers", self._migration_sql())

    def test_scanned_count_column_added(self):
        self.assertIn("scanned_count", self._migration_sql())

    def test_failed_count_column_added(self):
        self.assertIn("failed_count", self._migration_sql())


if __name__ == "__main__":
    unittest.main()

