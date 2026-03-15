import json
import os
import importlib
import pandas as pd
import numpy as np
import gc
from datetime import datetime
from backtesting import Backtest
from data_manager import DataManager


def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)


def get_strategy_class(strategy_name):
    module_name = f"strategies.{strategy_name.lower()}"
    if strategy_name == "SMACross":
        module_name = "strategies.moving_average_cross"
    elif strategy_name == "MondayBlues":
        module_name = "strategies.monday_blues"
    elif strategy_name == "RSIReversion":
        module_name = "strategies.rsi_reversion"
    elif strategy_name == "DividendStrategy":
        module_name = "strategies.dividend_strategy"

    try:
        module = importlib.import_module(module_name)
        return getattr(module, strategy_name)
    except Exception as e:
        print(f"Error loading strategy {strategy_name}: {e}")
        return None


def generate_dashboard(ticker, strategy_name, stats, plot_html_path, report_dir):
    """Creates a combined HTML dashboard for a single ticker."""
    trades = stats["_trades"]
    if not trades.empty:
        display_trades = trades[
            [
                "EntryTime",
                "ExitTime",
                "EntryPrice",
                "ExitPrice",
                "PnL",
                "ReturnPct",
                "Tag",
            ]
        ].copy()
        display_trades["ReturnPct"] = (display_trades["ReturnPct"] * 100).round(
            2
        ).astype(str) + "%"
        display_trades["PnL"] = display_trades["PnL"].round(2)
        table_html = display_trades.to_html(
            classes="table table-striped table-hover", index=False
        )
    else:
        table_html = "<p>No trades executed.</p>"

    dashboard_path = os.path.join(
        report_dir, f"dashboard_{ticker}_{strategy_name}.html"
    )
    plot_filename = os.path.basename(plot_html_path)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{ticker} - {strategy_name}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; }} 
            .card {{ margin-bottom: 20px; }} 
            iframe {{ width: 100%; height: 600px; border: none; }}
            th, td {{ text-align: left !important; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <h1>{ticker} - {strategy_name} Analysis</h1>
            <div class="card"><div class="card-body"><iframe src="{plot_filename}"></iframe></div></div>
            <div class="card"><div class="card-header">Trades</div><div class="card-body">{table_html}</div></div>
        </div>
    </body>
    </html>
    """
    with open(dashboard_path, "w") as f:
        f.write(html_content)
    return dashboard_path


def generate_meta_analysis(strategy_name, all_trades_df, results_df, report_dir):
    """Generates a global report across all tickers."""
    if all_trades_df.empty:
        return

    meta_path = os.path.join(report_dir, f"meta_analysis_{strategy_name}.html")

    # Global Metrics
    total_trades = len(all_trades_df)
    win_rate = (all_trades_df["PnL"] > 0).mean() * 100
    avg_pnl = all_trades_df["PnL"].mean()
    total_pnl = all_trades_df["PnL"].sum()

    # Best/Worst Tickers
    best_tickers = results_df.nlargest(5, "Return [%]")[
        ["Ticker", "Return [%]", "Win Rate [%]"]
    ]
    worst_tickers = results_df.nsmallest(5, "Return [%]")[
        ["Ticker", "Return [%]", "Win Rate [%]"]
    ]

    # Master Trade Table (Top 50 most profitable)
    top_trades = all_trades_df.sort_values("PnL", ascending=False).head(50).copy()

    # Rounding for readability
    for col in ["EntryPrice", "ExitPrice", "PnL", "ReturnPct"]:
        if col in top_trades.columns:
            top_trades[col] = top_trades[col].round(2)

    top_trades_html = top_trades.to_html(
        classes="table table-sm table-striped master-trade-table", index=False
    )

    # Add tooltips to headers manually via replacement
    top_trades_html = top_trades_html.replace(
        "<th>SL</th>",
        '<th title="Stop Loss: The price at which the trade would have been automatically closed to limit losses.">SL</th>',
    )
    top_trades_html = top_trades_html.replace(
        "<th>TP</th>",
        '<th title="Take Profit: The price at which the trade would have been automatically closed to lock in gains.">TP</th>',
    )
    top_trades_html = top_trades_html.replace(
        "<th>PnL</th>",
        '<th title="Profit and Loss: The net financial gain or loss from this specific trade.">PnL</th>',
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Meta-Analysis: {strategy_name}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 30px; background-color: #f4f7f6; }} 
            .metric-card {{ text-align: center; padding: 20px; border-radius: 10px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            th, td {{ text-align: left !important; }}
            .master-trade-table th {{ cursor: help; border-bottom: 1px dotted #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="mb-4">Global Strategy Meta-Analysis: {strategy_name}</h1>
            
            <div class="row mb-4">
                <div class="col-md-3"><div class="metric-card"><h5>Total Trades</h5><h2>{total_trades}</h2></div></div>
                <div class="col-md-3"><div class="metric-card"><h5>Global Win Rate</h5><h2>{win_rate:.1f}%</h2></div></div>
                <div class="col-md-3"><div class="metric-card"><h5>Avg PnL / Trade</h5><h2>${avg_pnl:.2f}</h2></div></div>
                <div class="col-md-3"><div class="metric-card"><h5>Cumulative PnL</h5><h2>${total_pnl:.2f}</h2></div></div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-4"><div class="card-header bg-success text-white">Top 5 Performers</div><div class="card-body">
                        {best_tickers.to_html(classes="table", index=False)}
                    </div></div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-4"><div class="card-header bg-danger text-white">Bottom 5 Performers</div><div class="card-body">
                        {worst_tickers.to_html(classes="table", index=False)}
                    </div></div>
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-dark text-white">Top 50 Most Profitable Trades (All Stocks)</div>
                <div class="card-body" style="max-height: 600px; overflow-y: auto;">
                    {top_trades_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    with open(meta_path, "w") as f:
        f.write(html_content)
    print(f"Meta-analysis generated: {meta_path}")


def run_backtest(ticker, strategy_class, config, dm, report_dir, save_plot=True):
    data = dm.get_ticker_data(ticker)
    if data is None:
        return None

    bt = Backtest(
        data,
        strategy_class,
        cash=config.get("initial_cash", 10000),
        commission=config.get("commission", 0.0),
        finalize_trades=True,
    )
    stats = bt.run()

    # Save specific trades for this ticker
    trades = stats["_trades"]
    if not trades.empty:
        trades_path = os.path.join(
            report_dir, f"trades_{ticker}_{config['strategy']}.csv"
        )
        trades.to_csv(trades_path, index=False)

    if save_plot:
        plot_path = os.path.join(report_dir, f"plot_{ticker}_{config['strategy']}.html")
        bt.plot(filename=plot_path, open_browser=False)
        generate_dashboard(ticker, config["strategy"], stats, plot_path, report_dir)

    return stats


def main():
    config = load_config()
    dm = DataManager()
    strategy_class = get_strategy_class(config["strategy"])
    if not strategy_class:
        return

    # Create timestamped report directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = os.path.join("reports", timestamp)
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    results_data = []
    all_trades = []

    tickers_to_run = config["tickers"]
    if "ALL" in [t.upper() for t in tickers_to_run]:
        tickers_to_run = dm.list_available_tickers()

    do_plots = len(tickers_to_run) <= 50
    if not do_plots:
        print(
            f"Large run detected ({len(tickers_to_run)} tickers). Skipping individual plots for speed."
        )

    for i, ticker in enumerate(tickers_to_run):
        print(
            f"[{i + 1}/{len(tickers_to_run)}] Testing {ticker}...", end=" ", flush=True
        )
        try:
            stats = run_backtest(
                ticker, strategy_class, config, dm, report_dir, save_plot=do_plots
            )
            if stats is not None:
                results_data.append(
                    {
                        "Ticker": ticker,
                        "Return [%]": stats["Return [%]"],
                        "Buy & Hold Return [%]": stats["Buy & Hold Return [%]"],
                        "Sharpe Ratio": stats["Sharpe Ratio"],
                        "Max. Drawdown [%]": stats["Max. Drawdown [%]"],
                        "Win Rate [%]": stats["Win Rate [%]"],
                        "# Trades": stats["# Trades"],
                    }
                )
                t_df = stats["_trades"].copy()
                t_df["Ticker"] = ticker
                all_trades.append(t_df)
                print(f"Done.")
            else:
                print("Failed (No Data)")

            # Help garbage collection
            del stats
            gc.collect()
        except Exception as e:
            print(f"Error: {e}")

    if results_data:
        res_df = pd.DataFrame(results_data)
        res_df.to_csv(os.path.join(report_dir, "summary.csv"), index=False)

        master_trades_df = pd.concat(all_trades) if all_trades else pd.DataFrame()
        generate_meta_analysis(config["strategy"], master_trades_df, res_df, report_dir)

        print("-" * 50)
        print(f"All reports for this run are saved in: {report_dir}")


if __name__ == "__main__":
    main()
