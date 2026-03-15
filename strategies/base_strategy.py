from backtesting import Strategy
from backtesting.lib import resample_apply
import pandas as pd


class BaseStrategy(Strategy):
    """
    A base class for user-defined strategies.
    Inherit from this and implement init() and next().
    """

    def sma(self, period):
        """Helper to calculate Simple Moving Average."""
        return self.I(lambda x: pd.Series(x).rolling(period).mean(), self.data.Close)

    def rsi(self, period=14):
        """Helper to calculate Relative Strength Index."""

        def calc_rsi(series, n):
            delta = pd.Series(series).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=n).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=n).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        return self.I(calc_rsi, self.data.Close, period)

    # You can add more helpers here as needed.
