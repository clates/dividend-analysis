import json
import pandas as pd
import numpy as np
import os
from portfolio_engine import PortfolioEngine
from data_manager import DataManager


def validate_ticker(ticker, buy_before=7, sell_after=7):
    with open("config.json", "r") as f:
        config = json.load(f)

    config["strategy_params"] = {"buy_before": buy_before, "sell_after": sell_after}
    # Reality constraints
    config["slippage_pct"] = 0.0005

    dm = DataManager()
    data = dm.get_ticker_data(ticker)
    if data is None:
        print(f"Data for {ticker} not found.")
        return

    # Filter to 2025
    data_2025 = data.loc["2025-01-01":"2025-12-31"].copy()

    # Manually build matrices for this ticker
    price_matrix = pd.DataFrame({ticker: data_2025["Close"]}).ffill()
    div_matrix = (
        pd.DataFrame({ticker: data_2025["Dividends"]})
        .reindex(price_matrix.index)
        .fillna(0)
    )

    # Indicators
    to_div = pd.DataFrame(
        index=price_matrix.index, columns=price_matrix.columns
    ).fillna(999.0)
    since_div = pd.DataFrame(
        index=price_matrix.index, columns=price_matrix.columns
    ).fillna(999.0)

    div_dates = div_matrix.index[div_matrix[ticker] > 0]
    for d in div_dates:
        diff_since = (price_matrix.index - d).days
        mask_since = (diff_since >= 0) & (diff_since < since_div[ticker])
        since_div.loc[mask_since, ticker] = diff_since[mask_since]
        diff_to = (d - price_matrix.index).days
        mask_to = (diff_to >= 0) & (diff_to < to_div[ticker])
        to_div.loc[mask_to, ticker] = diff_to[mask_to]

    engine = PortfolioEngine(
        config,
        price_matrix=price_matrix,
        div_matrix=div_matrix,
        to_div_matrix=to_div,
        since_div_matrix=since_div,
    )

    report_dir = engine.run(do_plots=False)

    # Calculate quarterly segments or just show trades
    trades = pd.read_csv(os.path.join(report_dir, "portfolio_trades.csv"))
    sells = trades[trades["Action"] == "SELL"]

    print(
        f"\n--- Validation Results for {ticker} (2025, B{buy_before}/S{sell_after}) ---"
    )
    if not sells.empty:
        total_pnl_pct = 0
        for i, row in sells.iterrows():
            # For each sell, we want to know the return of THAT trade
            # In our engine, we use target_investment = cash * 0.05
            # PnL % = TotalPnL / Value_at_Buy
            # Find the matching buy
            ticker_trades = trades[trades["Ticker"] == ticker].sort_values("Date")
            # This is complex to pair perfectly here, but we can look at the dashboard logic
            # Simplified: Total Return % from summary
            pass

    with open(os.path.join(report_dir, "portfolio_summary.json"), "r") as f:
        summary = json.load(f)
    print(f"Engine Total Return: {summary['Total Return %']}%")
    print("Trade Details:")
    print(
        trades[["Date", "Action", "Price", "Value", "TotalPnL", "Reason"]].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    validate_ticker("UPS", buy_before=7, sell_after=7)
    validate_ticker("GIS", buy_before=7, sell_after=7)
