import json
import pandas as pd
from portfolio_engine import PortfolioEngine
from data_manager import DataManager


def check_ticker_2025(ticker):
    with open("config.json", "r") as f:
        config = json.load(f)

    # Force 2025 range
    dm = DataManager()
    data = dm.get_ticker_data(ticker)
    if data is None:
        print(f"No data for {ticker}")
        return

    # Manually filter to 2025
    data_2025 = data.loc["2025-01-01":"2025-12-31"]

    # We need to pivot it to the matrix format the engine likes
    price_matrix = pd.DataFrame({ticker: data_2025["Close"]}).ffill()
    div_matrix = (
        pd.DataFrame({ticker: data_2025["Dividends"]})
        .reindex(price_matrix.index)
        .fillna(0)
    )

    # We need the indicators
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

    # Setup config for B5/S5
    config["strategy_params"] = {"buy_before": 5, "sell_after": 5}

    engine = PortfolioEngine(
        config,
        price_matrix=price_matrix,
        div_matrix=div_matrix,
        to_div_matrix=to_div,
        since_div_matrix=since_div,
    )

    report_dir = engine.run(do_plots=False)

    with open(os.path.join(report_dir, "portfolio_summary.json"), "r") as f:
        summary = json.load(f)

    print(f"\nResults for {ticker} in 2025 (B5/S5):")
    print(json.dumps(summary, indent=4))


if __name__ == "__main__":
    import os

    check_ticker_2025("ET")
    check_ticker_2025("GIS")
