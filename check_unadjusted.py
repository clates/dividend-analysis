import yfinance as yf
import pandas as pd
import numpy as np


def analyze_unadjusted(ticker):
    print(f"Analyzing {ticker} with UNADJUSTED prices...")
    df = yf.download(
        ticker, start="2025-01-01", end="2025-12-31", auto_adjust=False, actions=True
    )
    if df.empty:
        return

    # Flatten columns
    df.columns = df.columns.get_level_values(0)

    # Simple B5/S5 simulation
    cash = 100000
    shares = 0
    in_position = False

    # We need to find ex-div dates
    div_dates = df.index[df["Dividends"] > 0]

    history = []

    for current_date in df.index:
        # Check for signals
        # Buy: 5 days before next div
        next_divs = div_dates[div_dates > current_date]
        if not next_divs.empty:
            days_to_div = (next_divs[0] - current_date).days
            if not in_position and 0 < days_to_div <= 5:
                # BUY at Open
                price = df.loc[current_date, "Open"]
                # Position size 5%
                investment = cash * 0.05
                shares = int(investment // price)
                cash -= shares * price
                in_position = True
                entry_date = current_date
                entry_price = price
                print(
                    f"  BUY  {ticker} on {current_date.date()} at ${price:.2f} (Div in {days_to_div} days)"
                )

        # Collect Dividends
        div_amount = df.loc[current_date, "Dividends"]
        if in_position and div_amount > 0:
            dividend_cash = div_amount * shares
            cash += dividend_cash
            print(f"  DIV  {ticker} on {current_date.date()}: ${dividend_cash:.2f}")

        # Sell: 5 days after last div
        prev_divs = div_dates[div_dates <= current_date]
        if not prev_divs.empty:
            days_since_div = (current_date - prev_divs[-1]).days
            if in_position and days_since_div >= 5:
                # SELL at Close
                price = df.loc[current_date, "Close"]
                cash += shares * price
                print(
                    f"  SELL {ticker} on {current_date.date()} at ${price:.2f} ({days_since_div} days post-div)"
                )
                in_position = False
                shares = 0

    final_value = cash + (shares * df.iloc[-1]["Close"] if in_position else 0)
    print(f"Final Value: ${final_value:,.2f}")
    print(f"Total Return: {(final_value / 100000 - 1) * 100:.2f}%")


if __name__ == "__main__":
    analyze_unadjusted("GIS")
    analyze_unadjusted("AAPL")
