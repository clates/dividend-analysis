import pandas as pd
import yfinance as yf
import os
import json


def get_market_caps(tickers):
    cache_file = "market_caps.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    caps = {}
    print(f"Fetching market caps for {len(tickers)} tickers...")
    for i, ticker in enumerate(tickers):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            caps[ticker] = info.get("marketCap", 0)
            if i % 50 == 0:
                print(f"Progress: {i}/{len(tickers)}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            caps[ticker] = 0

    with open(cache_file, "w") as f:
        json.dump(caps, f)
    return caps


def analyze_b5s5():
    trades_path = "reports/portfolio_20260314_190939/portfolio_trades.csv"
    if not os.path.exists(trades_path):
        print(f"Error: {trades_path} not found.")
        return

    df = pd.read_csv(trades_path)
    # Filter to SELLS to get PnL
    sells = df[df["Action"] == "SELL"].copy()

    # Aggregate PnL per ticker
    ticker_performance = (
        sells.groupby("Ticker")
        .agg(
            {
                "TotalPnL": "sum",
                "DivCaptured": "sum",
                "Ticker": "count",  # Number of trades
            }
        )
        .rename(columns={"Ticker": "TradeCount"})
    )

    # Get market caps
    tickers = df["Ticker"].unique().tolist()
    market_caps = get_market_caps(tickers)

    ticker_performance["MarketCap"] = ticker_performance.index.map(market_caps)

    # Remove tickers with missing market cap info
    ticker_performance = ticker_performance[ticker_performance["MarketCap"] > 0]

    # Define Segments
    # Mega Cap: > $200B
    # Large Cap: $10B - $200B
    # Mid Cap: $2B - $10B
    # (Note: S&P 500 is mostly Large/Mega)

    def segment(mc):
        if mc >= 200e9:
            return "Mega Cap (>200B)"
        if mc >= 50e9:
            return "Large Cap (50B-200B)"
        return "Upper Mid/Large Cap (<50B)"

    ticker_performance["Segment"] = ticker_performance["MarketCap"].apply(segment)

    # Analysis
    segment_analysis = ticker_performance.groupby("Segment").agg(
        {
            "TotalPnL": ["mean", "sum", "count"],
            "DivCaptured": "mean",
            "TradeCount": "mean",
        }
    )

    print("\nMarket Cap Segmentation Analysis (B5/S5 Strategy):")
    print("=" * 60)
    print(segment_analysis)

    # Save detailed results
    ticker_performance.sort_values("MarketCap", ascending=False).to_csv(
        "reports/b5s5_market_cap_analysis.csv"
    )
    print(
        f"\nDetailed per-ticker analysis saved to: reports/b5s5_market_cap_analysis.csv"
    )


if __name__ == "__main__":
    analyze_b5s5()
