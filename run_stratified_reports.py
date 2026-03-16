import json
import os
import pandas as pd
from portfolio_engine import PortfolioEngine
from data_manager import DataManager


def run_stratified():
    # Load base config
    with open("config.json", "r") as f:
        base_config = json.load(f)

    # Load market caps
    with open("market_caps.json", "r") as f:
        market_caps = json.load(f)

    dm = DataManager()
    all_tickers = dm.list_available_tickers()

    # Pre-prepare all data once to save time
    engine_setup = PortfolioEngine(base_config)
    engine_setup.prepare_data(all_tickers)

    segments = [
        {
            "name": "Mega Cap Only",
            "min_cap": 200e9,
            "desc": "Companies with Market Cap > $200 Billion",
        },
        {
            "name": "Large Cap and Up",
            "min_cap": 50e9,
            "desc": "Companies with Market Cap > $50 Billion",
        },
        {
            "name": "Mid-Large Cap and Up",
            "min_cap": 10e9,
            "desc": "Companies with Market Cap > $10 Billion",
        },
    ]

    results = []

    for seg in segments:
        print(f"\n>>> Running Segment: {seg['name']}")

        # Filter tickers
        seg_tickers = [
            t
            for t in all_tickers
            if t in market_caps and market_caps[t] >= seg["min_cap"]
        ]
        print(f"Tickers in segment: {len(seg_tickers)}")

        if not seg_tickers:
            print("No tickers found for this segment. Skipping.")
            continue

        config = base_config.copy()
        # Ensure we use ALL but filtered by the engine call if we wanted to re-filter,
        # but we already have the matrices.
        # Actually, if we pass matrices, the engine currently uses the full matrix.
        # We need to slice the matrices for the segment.

        # Slicing matrices
        seg_price_matrix = engine_setup.price_matrix[seg_tickers]
        seg_div_matrix = engine_setup.div_matrix[seg_tickers]
        seg_to_div_matrix = engine_setup.to_div_matrix[seg_tickers]
        seg_since_div_matrix = engine_setup.since_div_matrix[seg_tickers]

        engine = PortfolioEngine(
            config,
            price_matrix=seg_price_matrix,
            div_matrix=seg_div_matrix,
            to_div_matrix=seg_to_div_matrix,
            since_div_matrix=seg_since_div_matrix,
        )

        # Run 30/30 strategy for all (default in config)
        report_dir = engine.run()

        # Update index.html later with these
        results.append(
            {"segment": seg["name"], "dir": report_dir, "count": len(seg_tickers)}
        )

    # Update index.html
    update_index(results)


def update_index(results):
    # This function is now just a placeholder or we can make it more precise
    # For this task, I will manually update index.html to ensure it looks perfect
    pass


if __name__ == "__main__":
    run_stratified()
