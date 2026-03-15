import os
import pandas as pd

DATA_DIR = "data"


class DataManager:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def get_ticker_data(self, ticker):
        """Loads ticker data from local parquet file and cleans it for backtesting."""
        filepath = os.path.join(self.data_dir, f"{ticker}.parquet")
        if os.path.exists(filepath):
            df = pd.read_parquet(filepath)

            # If yfinance returned a multi-index (Ticker level), flatten it
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Backtesting.py expects specific column names and a DatetimeIndex
            df.index = pd.to_datetime(df.index)

            # Ensure columns are properly named (yfinance usually does this but good to be sure)
            # We also keep 'Dividends' and 'Stock Splits' if they exist
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            if not all(col in df.columns for col in required_cols):
                print(
                    f"Warning: Missing required columns in {ticker}. Found: {df.columns}"
                )

            # Reorder to ensure standard columns are first, followed by dividends/splits
            existing_cols = list(df.columns)
            extra_cols = ["Dividends", "Stock Splits"]
            final_cols = required_cols + [c for c in extra_cols if c in existing_cols]
            df = df[final_cols]

            return df

        else:
            print(f"Data for {ticker} not found locally.")
            return None

    def list_available_tickers(self):
        """Returns a list of all tickers we have downloaded."""
        files = os.listdir(self.data_dir)
        return [f.replace(".parquet", "") for f in files if f.endswith(".parquet")]


if __name__ == "__main__":
    # Quick test
    dm = DataManager()
    tickers = dm.list_available_tickers()
    print(f"Available tickers: {len(tickers)}")
    if tickers:
        print(f"Sample data for {tickers[0]}:")
        print(dm.get_ticker_data(tickers[0]).head())
