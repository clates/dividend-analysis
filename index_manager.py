"""
index_manager.py

Builds a historical record of S&P 500 constituents by parsing Wikipedia's
addition/removal change log. This allows the PortfolioEngine to only buy
stocks that were actually in the index on any given date, eliminating
survivorship bias.

Usage:
    python3 index_manager.py          # builds data/historical_constituents.json
"""

import json
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUTPUT_PATH = "data/historical_constituents.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def normalize_ticker(ticker: str) -> str:
    """yfinance uses '-' instead of '.' for tickers like BRK.B."""
    return ticker.strip().replace(".", "-")


def fetch_current_constituents() -> set:
    """Fetch today's S&P 500 members from Wikipedia's main table."""
    print("Fetching current S&P 500 constituents...")
    resp = requests.get(SP500_URL, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    tickers = set()
    if table:
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if cols:
                tickers.add(normalize_ticker(cols[0].text))
    print(f"  Found {len(tickers)} current members.")
    return tickers


def fetch_changes() -> list[dict]:
    """
    Parse the 'Selected changes' table on the Wikipedia page.
    Returns list of dicts sorted by date ascending:
        [{"date": datetime, "added": [tickers], "removed": [tickers]}, ...]
    """
    print("Fetching S&P 500 historical changes...")
    resp = requests.get(SP500_URL, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")

    # The changes table is the second wikitable on the page
    changes_table = soup.find("table", {"id": "changes"})
    if not changes_table:
        # Fallback: second table with class wikitable
        tables = soup.find_all("table", {"class": "wikitable"})
        changes_table = tables[1] if len(tables) > 1 else None

    if not changes_table:
        print("  WARNING: Could not find changes table. Returning empty list.")
        return []

    rows = changes_table.find_all("tr")[1:]  # skip header
    changes_by_date = {}

    for row in rows:
        cols = row.find_all(["td", "th"])
        if len(cols) < 4:
            continue
        try:
            date_str = cols[0].text.strip()
            # Wikipedia dates look like "January 21, 2020" or "2020-01-21"
            date = None
            for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
                try:
                    date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            if date is None:
                continue

            added_raw = cols[1].text.strip()
            removed_raw = cols[3].text.strip()

            added = [normalize_ticker(t) for t in added_raw.split("\n") if t.strip()]
            removed = [
                normalize_ticker(t) for t in removed_raw.split("\n") if t.strip()
            ]

            key = date.strftime("%Y-%m-%d")
            if key not in changes_by_date:
                changes_by_date[key] = {"date": date, "added": [], "removed": []}
            changes_by_date[key]["added"].extend(added)
            changes_by_date[key]["removed"].extend(removed)

        except Exception:
            continue

    result = sorted(changes_by_date.values(), key=lambda x: x["date"])
    print(f"  Parsed {len(result)} change events.")
    return result


def build_historical_constituents(
    start_date: str = "2015-01-01",
    end_date: str = None,
) -> dict:
    """
    Rewinds from today's S&P 500 list using the change log to reconstruct
    the index membership for every month-start between start_date and end_date.

    Returns a dict: { "YYYY-MM-DD": [list of tickers] }
    Only stores monthly snapshots to keep the file size manageable.
    The engine will use the most recent snapshot on or before a given date.
    """
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    current_members = fetch_current_constituents()
    changes = fetch_changes()

    # Sort changes descending so we can rewind from today
    changes_desc = sorted(changes, key=lambda x: x["date"], reverse=True)

    today = datetime.today()
    start = datetime.strptime(start_date, "%Y-%m-%d")

    # Build a list of monthly snapshot dates (first of each month)
    snapshot_dates = []
    d = today.replace(day=1)
    while d >= start:
        snapshot_dates.append(d)
        # go back one month
        if d.month == 1:
            d = d.replace(year=d.year - 1, month=12)
        else:
            d = d.replace(month=d.month - 1)

    # Walk backwards through time, undoing each change
    snapshots = {}
    members = set(current_members)
    change_idx = 0

    for snap_date in sorted(snapshot_dates, reverse=True):
        # Undo all changes that happened AFTER this snapshot date
        while change_idx < len(changes_desc):
            change = changes_desc[change_idx]
            if change["date"] > snap_date:
                # This change happened after our snapshot — undo it
                for t in change["added"]:
                    members.discard(t)
                for t in change["removed"]:
                    members.add(t)
                change_idx += 1
            else:
                break

        key = snap_date.strftime("%Y-%m-%d")
        snapshots[key] = sorted(list(members))

    print(
        f"  Built {len(snapshots)} monthly snapshots from {start_date} to {end_date}."
    )
    return snapshots


def get_constituents_for_date(snapshots: dict, date: str) -> set:
    """
    Given a date string 'YYYY-MM-DD', return the set of S&P 500 tickers
    that were in the index on that date, using the nearest snapshot on or before.
    """
    dates = sorted(snapshots.keys())
    # Binary search for the most recent snapshot <= date
    lo, hi = 0, len(dates) - 1
    result_key = dates[0]
    while lo <= hi:
        mid = (lo + hi) // 2
        if dates[mid] <= date:
            result_key = dates[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return set(snapshots[result_key])


def main():
    os.makedirs("data", exist_ok=True)
    snapshots = build_historical_constituents(start_date="2015-01-01")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(snapshots, f)

    print(f"\nSaved to {OUTPUT_PATH}")

    # Quick sanity check
    jan2016 = get_constituents_for_date(snapshots, "2016-01-15")
    jan2024 = get_constituents_for_date(snapshots, "2024-01-15")
    print(f"Members on 2016-01-15: {len(jan2016)}")
    print(f"Members on 2024-01-15: {len(jan2024)}")

    # Show a few that were added after 2016 (should not be in 2016 list)
    new_members = jan2024 - jan2016
    print(
        f"Tickers in 2024 but NOT in 2016 ({len(new_members)} total): {sorted(new_members)[:10]}"
    )

    old_members = jan2016 - jan2024
    print(
        f"Tickers in 2016 but NOT in 2024 ({len(old_members)} total): {sorted(old_members)[:10]}"
    )


if __name__ == "__main__":
    main()
