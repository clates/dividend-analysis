from strategies.base_strategy import BaseStrategy


class SMACross(BaseStrategy):
    """
    A simple Moving Average Crossover strategy.
    Buy when 10-day SMA crosses above 50-day SMA.
    Sell when 10-day SMA crosses below 50-day SMA.
    """

    n1 = 10
    n2 = 50

    def init(self):
        # Precompute the two moving averages
        self.sma1 = self.sma(self.n1)
        self.sma2 = self.sma(self.n2)

    def next(self):
        # If sma1 crosses above sma2, close any existing short trades, and buy the asset
        if not self.position and self.sma1[-1] > self.sma2[-1]:
            self.buy()

        # Else, if sma1 crosses below sma2, close any existing long trades, and sell the asset
        elif self.position and self.sma1[-1] < self.sma2[-1]:
            self.position.close()
