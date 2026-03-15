import json
import os
import pandas as pd
from portfolio_engine import PortfolioEngine
from data_manager import DataManager


def run_sweep():
    # Load base config
    with open("config.json", "r") as f:
        base_config = json.load(f)

    dm = DataManager()
    tickers = dm.list_available_tickers()

    # Pre-prepare data once
    initial_engine = PortfolioEngine(base_config)
    initial_engine.prepare_data(tickers)

    # Extract matrices for reuse
    price_matrix = initial_engine.price_matrix
    div_matrix = initial_engine.div_matrix
    to_div_matrix = initial_engine.to_div_matrix
    since_div_matrix = initial_engine.since_div_matrix

    results = []

    # Range from 5 to 60 in 5-day increments
    increments = list(range(5, 65, 5))
    total_runs = len(increments) * len(increments)
    run_count = 0

    for buy_before in increments:
        for sell_after in increments:
            run_count += 1
            print(
                f"\n[{run_count}/{total_runs}] SWEEP: Buy {buy_before} / Sell {sell_after}"
            )

            # Create a specific config for this run
            config = base_config.copy()
            config["strategy_params"] = {
                "buy_before": buy_before,
                "sell_after": sell_after,
            }

            # Pass pre-loaded matrices and disable plots for sweep speed
            engine = PortfolioEngine(
                config,
                price_matrix=price_matrix,
                div_matrix=div_matrix,
                to_div_matrix=to_div_matrix,
                since_div_matrix=since_div_matrix,
            )
            report_dir = engine.run(do_plots=False)

            # Load the summary for this run
            with open(os.path.join(report_dir, "portfolio_summary.json"), "r") as f:
                summary = json.load(f)

            results.append(
                {
                    "BuyBefore": buy_before,
                    "SellAfter": sell_after,
                    "FinalEquity": summary["Final Equity"],
                    "TotalReturnPct": summary["Total Return %"],
                    "MaxDrawdownPct": summary["Max Drawdown %"],
                    "TotalTrades": summary["Total Trades"],
                    "ReportDir": report_dir,
                }
            )

    # Save master sweep results
    sweep_df = pd.DataFrame(results)
    sweep_df.to_csv("reports/sweep_results.csv", index=False)

    # Generate a simple HTML summary of the sweep
    best_return = sweep_df.loc[sweep_df["TotalReturnPct"].idxmax()]

    html_summary = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dividend Strategy Sweep Results</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body {{ padding: 20px; }} .table {{ margin-top: 20px; }}</style>
    </head>
    <body>
        <h2>Parameter Sweep: Dividend Capture Strategy</h2>
        <div class="alert alert-success">
            <strong>Best Performer:</strong> Buy {best_return["BuyBefore"]} days before / Sell {best_return["SellAfter"]} days after 
            ({best_return["TotalReturnPct"]}% Return)
        </div>
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Buy Before</th>
                    <th>Sell After</th>
                    <th>Total Return (%)</th>
                    <th>Max Drawdown (%)</th>
                    <th>Trades</th>
                    <th>Dashboard</th>
                </tr>
            </thead>
            <tbody>
    """
    for _, row in sweep_df.sort_values("TotalReturnPct", ascending=False).iterrows():
        dashboard_link = os.path.join(
            os.path.relpath(row["ReportDir"], "reports"), "portfolio_dashboard.html"
        )
        html_summary += f"""
            <tr>
                <td>{row["BuyBefore"]}</td>
                <td>{row["SellAfter"]}</td>
                <td>{row["TotalReturnPct"]}%</td>
                <td>{row["MaxDrawdownPct"]}%</td>
                <td>{row["TotalTrades"]}</td>
                <td><a href="{dashboard_link}">View</a></td>
            </tr>
        """

    html_summary += """
            </tbody>
        </table>
    </body>
    </html>
    """

    with open("reports/sweep_summary.html", "w") as f:
        f.write(html_summary)

    print("\n" + "=" * 50)
    print("SWEEP COMPLETE")
    print(f"Master CSV: reports/sweep_results.csv")
    print(f"HTML Summary: reports/sweep_summary.html")
    print(
        f"Best Configuration: {best_return['BuyBefore']} before / {best_return['SellAfter']} after"
    )


if __name__ == "__main__":
    run_sweep()
