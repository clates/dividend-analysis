import pandas as pd
import numpy as np
import os
import json
import gc
from datetime import datetime
from data_manager import DataManager
from index_manager import get_constituents_for_date


class PortfolioEngine:
    def __init__(
        self,
        config,
        price_matrix=None,
        div_matrix=None,
        to_div_matrix=None,
        since_div_matrix=None,
    ):
        self.config = config
        self.dm = DataManager()
        self.cash = config["initial_cash"]
        self.commission = config.get("commission", 0.0)
        self.slippage_pct = config.get("slippage_pct", 0.0)
        self.account_type = config.get("account_type", "tax_advantaged")

        # Portfolio Rules
        self.rules = config.get("portfolio_rules", {})
        self.max_positions = self.rules.get("max_active_positions", 20)
        self.max_pos_size_pct = self.rules.get("max_position_size_pct", 0.05)

        # Pre-loaded matrices (if provided)
        self.price_matrix = price_matrix
        self.div_matrix = div_matrix
        self.to_div_matrix = to_div_matrix
        self.since_div_matrix = since_div_matrix

        # Historical index constituents for survivorship bias mitigation
        self.historical_constituents = {}
        constituents_path = "data/historical_constituents.json"
        if os.path.exists(constituents_path):
            with open(constituents_path, "r") as f:
                self.historical_constituents = json.load(f)
            print(
                f"Loaded historical constituents ({len(self.historical_constituents)} snapshots).",
                flush=True,
            )
        else:
            print(
                "WARNING: historical_constituents.json not found. No survivorship bias filtering.",
                flush=True,
            )

        # Accounting
        self.holdings = {}  # {ticker: {'shares': 10, 'entry_price': 100, 'captured_dividends': 0.0}}
        self.equity_history = []
        self.trade_log = []

    def prepare_data(self, tickers):
        print(f"Loading market data for {len(tickers)} tickers...", flush=True)
        all_prices = {}
        all_divs = {}

        for t in tickers:
            df = self.dm.get_ticker_data(t)
            if df is not None:
                all_prices[t] = df["Close"]
                if "Dividends" in df.columns:
                    all_divs[t] = df["Dividends"]

        print("Pivoting data...", flush=True)
        self.price_matrix = pd.DataFrame(all_prices).ffill()
        self.div_matrix = (
            pd.DataFrame(all_divs).reindex(self.price_matrix.index).fillna(0)
        )

        print("Calculating dividend indicators (vectorized)...", flush=True)
        self.to_div_matrix = pd.DataFrame(
            index=self.price_matrix.index, columns=self.price_matrix.columns
        ).fillna(999.0)
        self.since_div_matrix = pd.DataFrame(
            index=self.price_matrix.index, columns=self.price_matrix.columns
        ).fillna(999.0)

        for t in self.div_matrix.columns:
            div_series = self.div_matrix[t]
            div_dates = div_series.index[div_series > 0]
            if not div_dates.empty:
                for d in div_dates:
                    # Days Since
                    diff_since = (self.price_matrix.index - d).days
                    mask_since = (diff_since >= 0) & (
                        diff_since < self.since_div_matrix[t]
                    )
                    self.since_div_matrix.loc[mask_since, t] = diff_since[mask_since]

                    # Days To
                    diff_to = (d - self.price_matrix.index).days
                    mask_to = (diff_to >= 0) & (diff_to < self.to_div_matrix[t])
                    self.to_div_matrix.loc[mask_to, t] = diff_to[mask_to]

    def run(self, tickers=None, do_plots=True):
        if self.price_matrix is None:
            if tickers is None:
                raise ValueError("No data loaded and no tickers provided.")
            self.prepare_data(tickers)
        else:
            if tickers:
                print(
                    f"Using pre-loaded market data ({len(self.price_matrix.columns)} tickers).",
                    flush=True,
                )

        price_matrix = self.price_matrix
        div_matrix = self.div_matrix
        to_div_matrix = self.to_div_matrix
        since_div_matrix = self.since_div_matrix

        sorted_dates = price_matrix.index.sort_values()
        print(f"Simulating {len(sorted_dates)} trading days...", flush=True)

        # Load Strategy
        from strategies.loyal_dividend_portfolio_strategy import (
            LoyalDividendPortfolioStrategy,
        )
        from strategies.dividend_portfolio_strategy import DividendPortfolioStrategy

        # Extract strategy parameters from config
        strat_params = self.config.get(
            "strategy_params", {"buy_before": 30, "sell_after": 30}
        )
        buy_before = strat_params.get("buy_before", 30)
        sell_after = strat_params.get("sell_after", 30)

        strat_name = self.config.get("strategy", "LoyalDividendPortfolioStrategy")
        if strat_name == "LoyalDividendPortfolioStrategy":
            strategy = LoyalDividendPortfolioStrategy(
                buy_before=buy_before, sell_after=sell_after
            )
        else:
            strategy = DividendPortfolioStrategy(
                buy_before=buy_before, sell_after=sell_after
            )

        use_constituents = bool(self.historical_constituents)
        strategy_metadata = {
            "name": getattr(strategy, "name", "Unknown Strategy"),
            "description": getattr(strategy, "description", "No description provided."),
            "start_date": pd.to_datetime(sorted_dates[0]).strftime("%Y-%m-%d"),
            "end_date": pd.to_datetime(sorted_dates[-1]).strftime("%Y-%m-%d"),
            "market_segment": "S&P 500"
            if len(price_matrix.columns) > 400
            else f"{len(price_matrix.columns)} tickers",
            "slippage_pct": self.slippage_pct,
            "account_type": self.account_type,
            "survivorship_filter": use_constituents,
        }

        total_divs_collected = 0
        # Cache current constituents to avoid repeated lookups
        current_constituents = set()
        last_constituents_date = ""

        for i, current_date in enumerate(sorted_dates):
            if i % 250 == 0:
                print(f"Progress: {i}/{len(sorted_dates)} days...", flush=True)

            # Update constituents snapshot monthly (first trading day of each month)
            date_str = pd.to_datetime(current_date).strftime("%Y-%m-%d")
            if use_constituents and date_str[:7] != last_constituents_date:
                current_constituents = get_constituents_for_date(
                    self.historical_constituents, date_str
                )
                last_constituents_date = date_str[:7]

            row_prices = price_matrix.loc[current_date]
            row_to_div = to_div_matrix.loc[current_date]
            row_since_div = since_div_matrix.loc[current_date]
            row_div_amounts = div_matrix.loc[current_date]

            # 1. Update Portfolio Valuation and Collect Dividends
            total_holdings_value = 0
            for t, info in self.holdings.items():
                price = row_prices[t]
                if not np.isnan(price):
                    total_holdings_value += price * info["shares"]

                # Check for dividend today
                div_per_share = row_div_amounts[t]
                if div_per_share > 0:
                    dividend_received = div_per_share * info["shares"]
                    self.cash += dividend_received
                    info["captured_dividends"] += dividend_received
                    total_divs_collected += dividend_received

                    # Log dividend receipt
                    self.trade_log.append(
                        {
                            "Date": current_date,
                            "Ticker": t,
                            "Action": "DIVIDEND",
                            "Price": div_per_share,
                            "Shares": info["shares"],
                            "Value": dividend_received,
                            "CashReserves": self.cash,
                            "PricePnL": None,
                            "DivCaptured": dividend_received,
                            "TotalPnL": dividend_received,
                            "Reason": "Dividend Payment",
                        }
                    )

            current_equity = self.cash + total_holdings_value
            self.equity_history.append(
                {"Date": current_date, "Equity": current_equity, "Cash": self.cash}
            )

            # 2. Ask the strategy for today's signals
            signals = strategy.get_signals(
                current_date,
                set(self.holdings.keys()),
                row_to_div,
                row_since_div,
            )

            # 3. Execute SELLS
            for t in signals.get("sell", []):
                if t in self.holdings:
                    price = row_prices[t]
                    shares = self.holdings[t]["shares"]
                    entry_price = self.holdings[t]["entry_price"]
                    captured_divs = self.holdings[t]["captured_dividends"]

                    # Apply slippage to sell price (receive slightly less)
                    price = price * (1 - self.slippage_pct)
                    price_pnl = (price - entry_price) * shares
                    total_pnl = price_pnl + captured_divs

                    proceeds = shares * price * (1 - self.commission)
                    self.cash += proceeds
                    self.trade_log.append(
                        {
                            "Date": current_date,
                            "Ticker": t,
                            "Action": "SELL",
                            "Price": price,
                            "Shares": shares,
                            "Value": proceeds,
                            "CashReserves": self.cash,
                            "PricePnL": price_pnl,
                            "DivCaptured": captured_divs,
                            "TotalPnL": total_pnl,
                            "Reason": f"{sell_after} days post-div",
                        }
                    )
                    del self.holdings[t]

            # 4. Execute BUYS
            if len(self.holdings) < self.max_positions:
                for t in signals.get("buy", []):
                    if len(self.holdings) >= self.max_positions:
                        break

                    # Survivorship bias filter: only buy if ticker was in index on this date
                    if use_constituents and t not in current_constituents:
                        continue

                    if t not in self.holdings and not np.isnan(row_prices[t]):
                        # Apply slippage to buy price (pay slightly more)
                        raw_price = row_prices[t]
                        price = raw_price * (1 + self.slippage_pct)
                        target_investment = current_equity * self.max_pos_size_pct
                        actual_investment = min(target_investment, self.cash)

                        if actual_investment > price:
                            shares = int(
                                actual_investment // (price * (1 + self.commission))
                            )
                            if shares > 0:
                                cost = shares * price * (1 + self.commission)
                                self.cash -= cost
                                self.holdings[t] = {
                                    "shares": shares,
                                    "entry_price": price,
                                    "captured_dividends": 0.0,
                                }
                                self.trade_log.append(
                                    {
                                        "Date": current_date,
                                        "Ticker": t,
                                        "Action": "BUY",
                                        "Price": price,
                                        "Shares": shares,
                                        "Value": cost,
                                        "CashReserves": self.cash,
                                        "PricePnL": None,
                                        "DivCaptured": 0.0,
                                        "TotalPnL": None,
                                        "Reason": f"Div in {int(row_to_div[t])} days",
                                    }
                                )

        print(
            f"Simulation complete. Total Dividends Collected: ${total_divs_collected:,.2f}"
        )
        return self.finalize_report(strategy_metadata, do_plots=do_plots)

    def finalize_report(self, strategy_metadata, do_plots=True):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join("reports", f"portfolio_{ts}")
        os.makedirs(report_dir, exist_ok=True)

        equity_df = pd.DataFrame(self.equity_history)
        equity_df["Date"] = pd.to_datetime(equity_df["Date"])
        equity_df["RunningMax"] = equity_df["Equity"].cummax()
        equity_df["DrawdownPct"] = (
            equity_df["Equity"] / equity_df["RunningMax"] - 1
        ) * 100

        benchmarks_df = self.calculate_benchmarks(equity_df["Date"])
        equity_df = equity_df.merge(benchmarks_df, on="Date", how="left")
        equity_df.to_csv(os.path.join(report_dir, "equity_curve.csv"), index=False)

        trades_df = pd.DataFrame(self.trade_log)
        if not trades_df.empty:
            trades_df["Date"] = pd.to_datetime(trades_df["Date"])
            trades_df.to_csv(
                os.path.join(report_dir, "portfolio_trades.csv"), index=False
            )

        final_equity = self.equity_history[-1]["Equity"]
        initial_cash = self.config["initial_cash"]
        total_return = (final_equity / initial_cash - 1) * 100
        max_drawdown = equity_df["DrawdownPct"].min()

        benchmark_stats = {}
        for col in benchmarks_df.columns:
            if col == "Date":
                continue
            final_bench = equity_df[col].iloc[-1]
            bench_return = (final_bench / initial_cash - 1) * 100
            benchmark_stats[col] = round(bench_return, 2)

        summary = {
            "Initial Cash": initial_cash,
            "Final Equity": round(final_equity, 2),
            "Total Return %": round(total_return, 2),
            "Max Drawdown %": round(max_drawdown, 2),
            "Total Trades": len(self.trade_log),
            "Benchmarks": benchmark_stats,
        }

        with open(os.path.join(report_dir, "portfolio_summary.json"), "w") as f:
            json.dump(summary, f, indent=4)

        self.generate_html_report(
            report_dir,
            equity_df,
            trades_df,
            summary,
            strategy_metadata,
            do_plots=do_plots,
        )
        return report_dir

    def calculate_benchmarks(self, dates):
        initial_cash = self.config["initial_cash"]
        bench_df = pd.DataFrame({"Date": dates})
        bench_df["Date"] = pd.to_datetime(bench_df["Date"]).dt.normalize()
        daily_rate = (1 + 0.05) ** (1 / 252) - 1
        bench_df["CD_5Pct"] = initial_cash * (1 + daily_rate) ** np.arange(len(dates))
        for ticker, name in [("SPY", "S&P500_SPY"), ("RSP", "EqualWeight_RSP")]:
            data = self.dm.get_ticker_data(ticker)
            if data is not None:
                data.index = pd.to_datetime(data.index).normalize()
                norm_dates = pd.to_datetime(dates).dt.normalize()
                joined = data.reindex(norm_dates).ffill().bfill()
                returns = joined["Close"].pct_change().fillna(0)
                if "Dividends" in joined.columns:
                    returns += (joined["Dividends"] / joined["Close"]).fillna(0)
                bench_df[name] = initial_cash * (1 + returns).cumprod().values
        if "S&P500_SPY" in bench_df.columns:
            agg = self.dm.get_ticker_data("AGG")
            if agg is not None:
                agg.index = pd.to_datetime(agg.index).normalize()
                joined_agg = (
                    agg.reindex(pd.to_datetime(dates).dt.normalize()).ffill().bfill()
                )
                agg_returns = joined_agg["Close"].pct_change().fillna(0)
                if "Dividends" in joined_agg.columns:
                    agg_returns += (
                        joined_agg["Dividends"] / joined_agg["Close"]
                    ).fillna(0)
                spy_returns = bench_df["S&P500_SPY"].pct_change().fillna(0).values
                balanced_returns = 0.6 * spy_returns + 0.4 * agg_returns.values
                bench_df["Balanced_60_40"] = (
                    initial_cash * (1 + balanced_returns).cumprod()
                )
        return bench_df

    def generate_html_report(
        self,
        report_dir,
        equity_df,
        trades_df,
        summary,
        strategy_metadata,
        do_plots=True,
    ):
        initial_cash_str = f"${summary['Initial Cash']:,.0f}"
        final_equity_str = f"${summary['Final Equity']:,.2f}"
        total_return_str = f"{summary['Total Return %']}%"
        max_drawdown_str = f"{summary['Max Drawdown %']}%"
        total_trades_str = str(summary["Total Trades"])
        return_color = "green" if summary["Total Return %"] >= 0 else "red"

        equity_cols = ["Date", "Equity", "Cash"] + [
            c
            for c in equity_df.columns
            if c
            not in [
                "Date",
                "Equity",
                "Cash",
                "RunningMax",
                "DrawdownPct",
                "PrevDivDate",
                "NextDivDate",
                "DaysToDiv",
                "DaysSinceDiv",
            ]
        ]
        equity_json_df = equity_df[equity_cols].copy()
        equity_json_df["Date"] = equity_json_df["Date"].dt.strftime("%Y-%m-%d")
        equity_data = equity_json_df.to_json(orient="records")
        drawdown_data = equity_df[["Date", "DrawdownPct"]].copy()
        drawdown_data["Date"] = drawdown_data["Date"].dt.strftime("%Y-%m-%d")
        drawdown_json = drawdown_data.to_json(orient="records")

        bench_rows = "".join(
            [
                f"<tr><td>{n.replace('_', ' ')}</td><td style='color: {'green' if r >= 0 else 'red'}; font-weight: bold;'>{r}%</td></tr>"
                for n, r in summary.get("Benchmarks", {}).items()
            ]
        )

        if not trades_df.empty:
            all_trades = trades_df.iloc[::-1].copy()
            for col in [
                "Price",
                "Value",
                "CashReserves",
                "PricePnL",
                "DivCaptured",
                "TotalPnL",
            ]:
                if col in all_trades.columns:
                    all_trades[col] = all_trades[col].apply(
                        lambda x: (
                            round(x, 2)
                            if pd.notnull(x) and isinstance(x, (int, float))
                            else None
                        )
                    )
            all_trades["Date"] = all_trades["Date"].dt.strftime("%Y-%m-%d")
            trades_json = all_trades.to_json(orient="records")
            trades_html = '<table id="trades-table" class="display table table-sm table-hover align-middle" style="width:100%"><thead><tr><th>Date</th><th>Ticker</th><th>Action</th><th>Price</th><th>Shares</th><th>Value</th><th>Cash Reserves</th><th>Price PnL</th><th>Div Captured</th><th>Total PnL</th><th>Reason</th></tr></thead></table>'
        else:
            trades_html = "<p class='text-muted'>No trades executed.</p>"
            trades_json = "[]"

        charts_html = ""
        plotly_scripts = ""
        if do_plots:
            charts_html = f"""
                <div class="row">
                    <div class="col-md-9"><div class="card"><div class="card-header bg-primary text-white">Equity, Cash & Benchmarks</div><div class="card-body"><div id="equity-chart"></div></div></div></div>
                    <div class="col-md-3"><div class="card"><div class="card-header bg-info text-white">Benchmark Comparison</div><div class="card-body p-0"><table class="table mb-0"><thead class="table-light"><tr><th>Benchmark</th><th>Return</th></tr></thead><tbody><tr class="table-primary"><td><strong>Strategy</strong></td><td style='color: {return_color}; font-weight: bold;'>{total_return_str}</td></tr>{bench_rows}</tbody></table></div></div></div>
                </div>
                <div class="row"><div class="col-12"><div class="card"><div class="card-header bg-danger text-white">Drawdown (%)</div><div class="card-body"><div id="drawdown-chart"></div></div></div></div></div>
            """
            plotly_scripts = f"""
                <script>
                    const eqData = {equity_data};
                    const ddData = {drawdown_json};
                    const dates = eqData.map(d => d.Date);
                    const traces = [
                        {{ x: dates, y: eqData.map(d => d.Equity), name: 'Total Portfolio Value', type: 'scatter', mode: 'lines', line: {{ color: '#0d6efd', width: 3 }}, fill: 'tozeroy', fillcolor: 'rgba(13, 110, 253, 0.1)' }},
                        {{ x: dates, y: eqData.map(d => d.Cash), name: 'Cash Reserves', type: 'scatter', mode: 'lines', line: {{ color: '#6c757d', width: 2, dash: 'dash' }} }}
                    ];
                    const benchmarks = {list(summary.get("Benchmarks", {}).keys())};
                    const colors = ['#ffc107', '#198754', '#dc3545', '#6f42c1'];
                    benchmarks.forEach((b, i) => {{ traces.push({{ x: dates, y: eqData.map(d => d[b]), name: b.replace('_', ' '), type: 'scatter', mode: 'lines', line: {{ color: colors[i % colors.length], width: 1.5, dash: 'dot' }} }}); }});
                    Plotly.newPlot('equity-chart', traces, {{ margin: {{ t: 10, r: 10, b: 40, l: 60 }}, xaxis: {{ title: 'Date' }}, yaxis: {{ title: 'Value ($)' }}, legend: {{ orientation: 'h', y: -0.2 }} }});
                    Plotly.newPlot('drawdown-chart', [{{ x: dates, y: ddData.map(d => d.DrawdownPct), type: 'scatter', mode: 'lines', line: {{ color: '#dc3545', width: 1 }}, fill: 'tozeroy', fillcolor: 'rgba(220, 53, 69, 0.2)' }}], {{ margin: {{ t: 10, r: 10, b: 40, l: 60 }}, xaxis: {{ title: 'Date' }}, yaxis: {{ title: 'Drawdown (%)' }} }});
                </script>
            """

        html = f"""
        <!DOCTYPE html><html><head><title>Portfolio Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
        <script type="text/javascript" language="javascript" src="https://code.jquery.com/jquery-3.7.0.js"></script>
        <script type="text/javascript" language="javascript" src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <style>
            body {{ background-color: #f8f9fa; padding: 20px; font-family: sans-serif; }} 
            .metric-card {{ padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #dee2e6; }} 
            .metric-value {{ font-size: 24px; font-weight: bold; color: #0d6efd; }} 
            .metric-label {{ font-size: 12px; color: #6c757d; text-transform: uppercase; font-weight: bold; }} 
            .card {{ margin-bottom: 20px; border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }} 
            #equity-chart {{ height: 550px; }} #drawdown-chart {{ height: 300px; }} 
            .table-container {{ background: white; border-radius: 8px; border: 1px solid #dee2e6; padding: 15px; }}
            .table-success-row {{ background-color: #d1e7dd !important; }}
            .table-danger-row {{ background-color: #f8d7da !important; }}
            .table-info-row {{ background-color: #e0f2fe !important; }}
        </style>
        </head>
        <body><div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h2>Portfolio Analysis Dashboard</h2>
                <span class="badge bg-secondary">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
            </div>
            <div class="card mb-4 border-0 bg-white shadow-sm"><div class="card-body"><div class="row">
                <div class="col-md-5"><h5 class="text-primary">{strategy_metadata["name"]}</h5><p class="mb-0 text-secondary">{strategy_metadata["description"]}</p></div>
                <div class="col-md-2"><div class="small text-uppercase text-muted fw-bold">Period</div><div>{strategy_metadata["start_date"]} to {strategy_metadata["end_date"]}</div></div>
                <div class="col-md-2"><div class="small text-uppercase text-muted fw-bold">Segment</div><div>{strategy_metadata["market_segment"]}</div></div>
                <div class="col-md-3">
                    <div class="small text-uppercase text-muted fw-bold">Reality Constraints</div>
                    <div class="mt-1">
                        <span class="badge {"bg-success" if strategy_metadata.get("survivorship_filter") else "bg-warning text-dark"}">
                            {"✓ Survivorship Filter" if strategy_metadata.get("survivorship_filter") else "⚠ No Survivorship Filter"}
                        </span>
                        <span class="badge bg-info text-dark ms-1" title="Simulated cost of not getting the perfect market price">
                            Slippage: {strategy_metadata.get("slippage_pct", 0) * 100:.2f}%
                        </span>
                        <span class="badge bg-secondary ms-1">
                            {"IRA/401k" if strategy_metadata.get("account_type") == "tax_advantaged" else "Taxable"}
                        </span>
                    </div>
                </div>
            </div></div></div>
            <div class="row mb-4">
                <div class="col-md-2"><div class="metric-card"><div class="metric-label">Initial</div><div class="metric-value">{initial_cash_str}</div></div></div>
                <div class="col-md-3"><div class="metric-card"><div class="metric-label">Final Value</div><div class="metric-value">{final_equity_str}</div></div></div>
                <div class="col-md-2"><div class="metric-card"><div class="metric-label">Return</div><div class="metric-value" style="color: {return_color}">{total_return_str}</div></div></div>
                <div class="col-md-2"><div class="metric-card"><div class="metric-label">Max Drawdown</div><div class="metric-value" style="color: #dc3545">{max_drawdown_str}</div></div></div>
                <div class="col-md-2"><div class="metric-card"><div class="metric-label">Total Trades</div><div class="metric-value">{total_trades_str}</div></div></div>
            </div>
            {charts_html}
            <div class="row"><div class="col-12"><div class="card"><div class="card-header bg-dark text-white d-flex justify-content-between"><span>Full Transaction History</span><small>Showing all {len(trades_df)} entries</small></div><div class="card-body"><div class="table-container">{trades_html}</div></div></div></div></div>
            <div class="card mt-4"><div class="card-header bg-secondary text-white">Metrics Explanation</div><div class="card-body"><div class="row"><div class="col-md-4"><strong>Max Drawdown</strong><p class="small text-muted">Largest peak-to-trough decline.</p></div><div class="col-md-4"><strong>Total Return</strong><p class="small text-muted">Growth of initial capital.</p></div><div class="col-md-4"><strong>Benchmarks</strong><p class="small text-muted">Comparison against S&P500 (SPY), Equal-Weight S&P500 (RSP), 5% CD, and 60/40 Portfolio.</p></div></div></div></div>
        </div>
        {plotly_scripts}
        <script>
            const tradesData = {trades_json};
            $(document).ready(function() {{
                $('#trades-table').DataTable({{
                    data: tradesData,
                    columns: [
                        {{ data: 'Date' }}, {{ data: 'Ticker' }}, {{ data: 'Action' }},
                        {{ data: 'Price', render: $.fn.dataTable.render.number(',', '.', 2, '$') }},
                        {{ data: 'Shares' }},
                        {{ data: 'Value', render: $.fn.dataTable.render.number(',', '.', 2, '$') }},
                        {{ data: 'CashReserves', render: $.fn.dataTable.render.number(',', '.', 2, '$') }},
                        {{ data: 'PricePnL', render: function(data) {{ return data ? '$' + data.toLocaleString(undefined, {{minimumFractionDigits: 2}}) : '-'; }} }},
                        {{ data: 'DivCaptured', render: function(data) {{ return data ? '$' + data.toLocaleString(undefined, {{minimumFractionDigits: 2}}) : '-'; }} }},
                        {{ data: 'TotalPnL', render: function(data) {{ return data ? '$' + data.toLocaleString(undefined, {{minimumFractionDigits: 2}}) : '-'; }} }},
                        {{ data: 'Reason' }}
                    ],
                    pageLength: 25, order: [[0, 'desc']], deferRender: true,
                    createdRow: function(row, data, dataIndex) {{
                        if (data.Action === 'SELL') $(row).addClass('table-success-row');
                        else if (data.Action === 'BUY') $(row).addClass('table-danger-row');
                        else if (data.Action === 'DIVIDEND') $(row).addClass('table-info-row');
                    }}
                }});
            }});
        </script>
        </body></html>
        """
        with open(os.path.join(report_dir, "portfolio_dashboard.html"), "w") as f:
            f.write(html)


if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)
    dm = DataManager()
    tickers = dm.list_available_tickers()
    engine = PortfolioEngine(config)
    engine.run(tickers)
