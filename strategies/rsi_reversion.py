from strategies.base_strategy import BaseStrategy


class RSIReversion(BaseStrategy):
    """
    RSI Mean Reversion Strategy.
    Buy when RSI < 30 (Oversold).
    Sell when RSI > 70 (Overbought).
    """

    rsi_period = 14
    rsi_low = 30
    rsi_high = 70

    def init(self):
        self.rsi_val = self.rsi(self.rsi_period)

    def next(self):
        # Entry: Oversold
        if self.rsi_val[-1] < self.rsi_low:
            if not self.position:
                self.buy()

        # Exit: Overbought
        elif self.rsi_val[-1] > self.rsi_high:
            if self.position:
                self.position.close()
