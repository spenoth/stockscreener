import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeMetrics:
    timestamp: any

    final_return: float
    mean_return: float

    mfe: float                  # Maximum Favorable Excursion
    mae: float                  # Maximum Adverse Excursion

    time_to_mfe: int
    time_to_mae: int

    recovery_factor: Optional[float]

    winner_final: bool
    winner_mean: bool


class TradeAnalyzer:
    """
TradeAnalyzer computes statistical performance metrics for a collection of
historical trading signals.

Each signal contains a normalized price path beginning at 0% (entry) and
continuing for a fixed holding period (for example, the next 30 candles).

The goal is not only to determine whether the signal was profitable, but also
to answer practical trading questions such as:

• How often does the signal produce a profitable trade?
    -> Win Rate

• When the signal works, how much does it usually make?
    -> Average Winner

• When the signal fails, how much does it usually lose?
    -> Average Loser

• What is the expected return if every signal is traded?
    -> Expectancy

• How much profit was available during the lifetime of a trade?
    -> Maximum Favorable Excursion (MFE)

• How much did the trade move against the position before recovering?
    -> Drawdown of Winners

• How much did losing trades move against the position?
    -> Drawdown of Losers

These statistics provide a quantitative estimate of both the reward and the
risk of a trading strategy, helping determine suitable stop-losses,
take-profit levels, and the overall quality of the signal.
"""

    def __init__(self, all_paths):
        self.all_paths = all_paths
        self.metrics = []

    def analyze(self):

        self.metrics.clear()

        for trade in self.all_paths:

            path = np.asarray(trade['path'])

            final_return = path[-1]
            mean_return = path.mean()

            mfe = path.max()
            mae = path.min()

            time_to_mfe = np.argmax(path)
            time_to_mae = np.argmin(path)

            if mae == 0:
                recovery = None
            else:
                recovery = float(final_return / abs(mae))

            self.metrics.append(
                TradeMetrics(
                    timestamp=trade['timestamp'],

                    final_return=float(final_return),
                    mean_return=float(mean_return),

                    mfe=float(mfe),
                    mae=float(mae),

                    time_to_mfe=int(time_to_mfe),
                    time_to_mae=int(time_to_mae),

                    recovery_factor=recovery,

                    winner_final=bool(final_return > 0),
                    winner_mean=bool(mean_return > 0)
                )
            )

        return self.metrics

    # ----------------------------

    def summary(self):

        m = self.metrics

        winners = [x for x in m if x.winner_final]
        losers = [x for x in m if not x.winner_final]

        win_rate = len(winners) / len(m)

        avg_win = np.mean([x.final_return for x in winners]) if winners else 0
        avg_loss = np.mean([x.final_return for x in losers]) if losers else 0

        avg_drawdown_win = np.mean([x.mae for x in winners]) if winners else 0
        avg_drawdown_loss = np.mean([x.mae for x in losers]) if losers else 0

        avg_mfe = np.mean([x.mfe for x in winners]) if winners else 0

        expectancy = (
            win_rate * avg_win
            - (1 - win_rate) * abs(avg_loss)
        )

        return {
            "num_trades": len(m),

            "win_rate": float(win_rate),

            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),

            "avg_mfe": float(avg_mfe),

            "avg_drawdown_winners": float(avg_drawdown_win),
            "avg_drawdown_losers": float(avg_drawdown_loss),

            "expectancy": float(expectancy),
        }

    # ----------------------------

    def drawdown_percentiles(self):

        dd = np.array([m.mae for m in self.metrics])

        return {
            "50%": float(np.percentile(dd, 50)),
            "75%": float(np.percentile(dd, 75)),
            "90%": float(np.percentile(dd, 90)),
            "95%": float(np.percentile(dd, 95)),
            "99%": float(np.percentile(dd, 99)),
        }

    # ----------------------------

    def probability_of_target(self, target):

        hits = 0

        for trade in self.all_paths:
            if np.max(trade.path) >= target:
                hits += 1

        return hits / len(self.all_paths)

    # ----------------------------

    def mean_path(self):

        raw = [np.asarray(t["path"]) for t in self.all_paths]
        max_len = max(len(p) for p in raw)
        padded = [np.pad(p, (0, max_len - len(p)), constant_values=np.nan) for p in raw]
        paths = np.vstack(padded)

        return {
            "mean": np.nanmean(paths, axis=0).tolist(),
            "median": np.nanmedian(paths, axis=0).tolist(),
            "std": np.nanstd(paths, axis=0).tolist(),
            "q25": np.nanpercentile(paths, 25, axis=0).tolist(),
            "q75": np.nanpercentile(paths, 75, axis=0).tolist(),
            "q10": np.nanpercentile(paths, 10, axis=0).tolist(),
            "q90": np.nanpercentile(paths, 90, axis=0).tolist(),
        }