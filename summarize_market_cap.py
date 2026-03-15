import pandas as pd
import os


def summarize():
    df = pd.read_csv("reports/b5s5_market_cap_analysis.csv")

    def segment(mc):
        if mc >= 200e9:
            return "Mega Cap (>200B)"
        if mc >= 50e9:
            return "Large Cap (50B-200B)"
        return "Upper Mid/Large Cap (<50B)"

    df["Segment"] = df["MarketCap"].apply(segment)

    summary = (
        df.groupby("Segment")
        .agg(
            {
                "Ticker": "count",
                "TotalPnL": "mean",
                "DivCaptured": "mean",
                "TradeCount": "mean",
            }
        )
        .rename(columns={"Ticker": "CompanyCount"})
    )

    summary["AvgPnLPerTrade"] = summary["TotalPnL"] / summary["TradeCount"]

    print("\nB5/S5 Market Cap Summary:")
    print("=" * 80)
    print(summary.to_string())

    # Sort top 10 companies by Total PnL
    print("\nTop 10 Most Profitable Companies in B5/S5:")
    print("-" * 40)
    print(
        df.sort_values("TotalPnL", ascending=False)[
            ["Ticker", "MarketCap", "TotalPnL", "DivCaptured", "TradeCount"]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    summarize()
