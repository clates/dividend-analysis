from strategies.base_strategy import BaseStrategy
import pandas as pd


class DividendStrategy(BaseStrategy):
    """
    Ex-Dividend Strategy:
    Buy 30 days before the ex-dividend date.
    Sell 30 days after the ex-dividend date.
    """

    def init(self):
        # We need the Dividends data
        self.divs = self.data.Dividends

    def next(self):
        # DaysToDiv and DaysSinceDiv are our pre-calculated indicators
        days_to_div = self.data.DaysToDiv[-1]
        days_since_div = self.data.DaysSinceDiv[-1]

        # Entry: Buy 30 days before ex-dividend date
        if not self.position and days_to_div <= 30 and days_to_div > 0:
            self.buy(tag=f"Upcoming Dividend ({int(days_to_div)} days)")

        # Exit: Sell 30 days after the ex-dividend date
        elif self.position and days_since_div >= 30:
            self.position.close()
