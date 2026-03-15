import os
import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

DATA_DIR = "data"
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def get_sp500_tickers():
    print("Fetching S&P 500 ticker list from Wikipedia...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(SP500_URL, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    if not table:
        print("Failed to find the S&P 500 table on Wikipedia.")
        return []

    tickers = []
    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) > 0:
            ticker = cols[0].text.strip()
            # yfinance uses '-' instead of '.' for tickers like BRK.B
            ticker = ticker.replace(".", "-")
            tickers.append(ticker)
    return tickers


def download_data(ticker, period="10y"):
    filepath = os.path.join(DATA_DIR, f"{ticker}.parquet")

    if os.path.exists(filepath):
        # Optional: Check if file is old and needs refresh
        return False

    try:
        data = yf.download(
            ticker, period=period, interval="1d", progress=False, actions=True
        )
        if not data.empty:
            data.to_parquet(filepath)
            return True
    except Exception as e:
        print(f"Error downloading {ticker}: {e}")
    return False


def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    tickers = get_sp500_tickers()
    print(f"Found {len(tickers)} tickers. Starting download...")

    count = 0
    new_downloads = 0
    for i, ticker in enumerate(tickers):
        success = download_data(ticker)
        if success:
            new_downloads += 1

        count += 1
        if count % 20 == 0:
            print(f"Processed {count}/{len(tickers)} tickers... ({new_downloads} new)")

        # Small delay to be polite to Yahoo APIs if downloading many new files
        if success:
            time.sleep(0.2)

    print(f"Finished. Total tickers: {len(tickers)}. New downloads: {new_downloads}")


if __name__ == "__main__":
    main()
