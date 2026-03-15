from strategies.base_strategy import BaseStrategy


class MondayBlues(BaseStrategy):
    """
    Silly Strategy:
    Buy on Monday, Sell on Friday.
    Only if the stock ticker starts with 'A' (handled by the runner).
    """

    def init(self):
        pass

    def next(self):
        # index[-1] is the current date
        day_of_week = self.data.index[-1].weekday()

        # 0 = Monday, 4 = Friday
        if day_of_week == 0:  # Monday
            if not self.position:
                self.buy()

        elif day_of_week == 4:  # Friday
            if self.position:
                self.position.close()
