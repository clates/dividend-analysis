import json
import pandas as pd
from portfolio_engine import PortfolioEngine
from data_manager import DataManager


def run_specific(buy_before, sell_after):
    with open("config.json", "r") as f:
        config = json.load(f)

    config["strategy_params"] = {"buy_before": buy_before, "sell_after": sell_after}

    dm = DataManager()
    tickers = dm.list_available_tickers()

    engine = PortfolioEngine(config)
    report_dir = engine.run(tickers)
    print(f"Report generated: {report_dir}")


if __name__ == "__main__":
    print("Running B35/S45 (Optimal)...")
    run_specific(35, 45)
    print("\nRunning B30/S30 (Standard)...")
    run_specific(30, 30)
