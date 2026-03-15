from strategies.base_portfolio_strategy import BasePortfolioStrategy


class DividendPortfolioStrategy(BasePortfolioStrategy):
    """
    Portfolio-wide Dividend Strategy.
    Parameterized for buy/sell windows.
    """

    def __init__(self, buy_before=30, sell_after=30):
        super().__init__()
        self.buy_before = buy_before
        self.sell_after = sell_after
        self.name = f"Dividend Capture Strategy ({buy_before}/{sell_after})"
        self.description = f"Buys stocks {buy_before} days before their ex-dividend date and sells them {sell_after} days after. Designed to capture both the dividend payment and potential price recovery."

    def compute_signals(
        self, current_date, active_tickers, portfolio_holdings, market_data
    ):
        buy_signals = []
        sell_signals = []

        for ticker in active_tickers:
            df = market_data[ticker]

            # Check if this ticker has data for today
            if current_date not in df.index:
                continue

            row = df.loc[current_date]

            # Use our pre-calculated indicators
            days_to_div = row["DaysToDiv"]
            days_since_div = row["DaysSinceDiv"]

            # Sell logic: If we hold it and it's X days past dividend
            if ticker in portfolio_holdings:
                if days_since_div >= self.sell_after:
                    sell_signals.append(ticker)

            # Buy logic: If we don't hold it and it's within Y days before dividend
            else:
                if 0 < days_to_div <= self.buy_before:
                    buy_signals.append(ticker)

        return {"buy": buy_signals, "sell": sell_signals}
