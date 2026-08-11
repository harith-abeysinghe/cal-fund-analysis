"""FundScraper service - scrapes CAL fund rates from the AJAX endpoint."""

import csv
import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional, TypedDict

try:
    import requests
except ImportError:
    print("Install dependencies: pip install requests")
    sys.exit(1)


class FundData(TypedDict):
    """TypedDict for fund data structure."""
    name: str
    price_growth: float
    old_date: str
    old_price: float
    latest_date: str
    latest_price: float
    price_difference: float


class FundScraper:
    """Scrapes fund data from CAL AJAX endpoint for specific target funds."""

    # Target funds to track (by FUND code from the AJAX response)
    # Maps FUND code -> display name used for CSV files / target funds
    FUND_CODE_MAP = {
        "IGF": "Investment Grade Fund",
        "IF": "CAL Income Fund",
        "QEF": "Quantitative Equity Fund",
        "CAHYF": "High Yield Fund",
        "GF": "Capital Alliance Gilt Fund",
    }
    TARGET_FUNDS = list(FUND_CODE_MAP.keys())

    def __init__(self, url: str, data_dir: Optional[Path] = None) -> None:
        self.url = url
        self.data_dir = data_dir
        self._page_content: Optional[dict] = None

    def scrape_funds(self) -> List[dict]:
        """Extract fund data from the AJAX endpoint for target funds only."""
        if not self._fetch_page():
            return []

        # The response is {"UTMS_FUND": [ {...}, {...} ]}
        funds_list = self._page_content.get("UTMS_FUND", []) if isinstance(self._page_content, dict) else []

        # Check if we got valid data
        if not funds_list or len(funds_list) == 0:
            print("[Info] No fund data in API response, using fallback CSV data")
            return self._load_fallback_funds()

        funds: List[dict] = []
        for entry in funds_list:
            code = entry.get("FUND")
            if code not in self.TARGET_FUNDS:
                continue

            try:
                latest_price = float(entry.get("LATEST_PRICE", "0"))
                old_price = float(entry.get("OLD_PRICE", "0"))
            except (ValueError, TypeError):
                continue

            if old_price <= 0:
                continue

            price_difference = latest_price - old_price
            growth = ((latest_price - old_price) / old_price) * 100.0
            # Map code to display name for consistent CSV filenames
            display_name = self.FUND_CODE_MAP.get(code, code)
            funds.append({
                "name": display_name,
                "price_growth": round(growth, 4),
                "old_date": entry.get("OLD_DATE", ""),
                "old_price": old_price,
                "latest_date": entry.get("LATEST_DATE", ""),
                "latest_price": latest_price,
                "price_difference": round(price_difference, 4),
                "fund_name": entry.get("FUND_NAME", code),
            })

        return funds

    def _load_fallback_funds(self) -> List[dict]:
        """
        Load fallback fund data from CSV files if the API returns empty results.
        This reads the most recent data from the data directory.
        """
        if not self.data_dir or not self.data_dir.exists():
            print("[Error] Fallback data directory not found")
            return []

        funds: List[dict] = []
        for csv_file in self.data_dir.glob("*.csv"):
            fund_name = csv_file.stem  # filename without .csv
            try:
                with csv_file.open('r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if not rows:
                        continue
                    latest_row = rows[-1]  # Get the most recent row

                # Map CSV columns to FundData fields
                # CSV headers: scraped_date,old_date,old_price,new_date,new_price,price_difference,price_growth
                try:
                    growth_value = float(latest_row.get('price_growth', 0) or 0)
                except (ValueError, TypeError):
                    growth_value = 0.0

                try:
                    price_diff = float(latest_row.get('price_difference', 0) or 0)
                except (ValueError, TypeError):
                    price_diff = 0.0

                try:
                    old_price_val = float(latest_row.get('old_price', 0) or 0)
                except (ValueError, TypeError):
                    old_price_val = 0.0

                try:
                    new_price_val = float(latest_row.get('new_price', 0) or 0)
                except (ValueError, TypeError):
                    new_price_val = 0.0

                try:
                    old_date_val = latest_row.get('old_date', '') or ''
                except (ValueError, TypeError):
                    old_date_val = ''

                try:
                    new_date_val = latest_row.get('new_date', '') or ''
                except (ValueError, TypeError):
                    new_date_val = ''

                # Prepare the fallback FundData entry
                fund_entry = {
                    "name": fund_name,
                    "price_growth": round(growth_value, 4),
                    "old_date": old_date_val,
                    "old_price": old_price_val,
                    "latest_date": new_date_val,
                    "latest_price": new_price_val,
                    "price_difference": round(price_diff, 4),
                }
                funds.append(fund_entry)

            except Exception as e:
                print(f"[Error] Failed to load fallback fund data for {csv_file}: {e}")

        return funds

    def _fetch_page(self) -> bool:
        """Fetch fund data from CAL AJAX endpoint.

        The API treats `valuedate` as the OLD anchor and returns the most
        recent available price as LATEST. A recent valuedate (e.g. yesterday)
        yields OLD == LATEST, forcing growth to 0.0 — useless for analysis.
        We therefore default to a year-ago anchor (a date before the current
        date that produces a meaningful OLD-vs-LATEST comparison) and accept
        only responses where OLD_DATE differs from LATEST_DATE.
        """
        try:
            today = datetime.date.today()
            # Try ~1 year ago first, then step backwards up to 30 more days
            # until we land on a date whose response has real old-vs-latest spread.
            for offset in range(376, 407):
                candidate = (today - datetime.timedelta(days=offset)).isoformat()
                params = {
                    "action": "getUTFundRates",
                    "valuedate": candidate,
                }
                print(f"[Debug] Requesting data with valuedate: {candidate}")
                response = requests.get(self.url, params=params, timeout=15)
                response.raise_for_status()

                data = response.json()
                # Empty result comes back as a bare list []; treat that as no data.
                if isinstance(data, list):
                    if not data:
                        continue
                    data = {"UTMS_FUND": data}

                funds = data.get("UTMS_FUND", []) if isinstance(data, dict) else []
                if not funds:
                    continue

                # Reject responses where every fund has OLD == LATEST (zero spread).
                has_spread = any(
                    str(f.get("OLD_DATE", "")) != str(f.get("LATEST_DATE", ""))
                    for f in funds
                )
                if not has_spread:
                    continue

                self._page_content = data
                print(f"[Debug] Got {len(funds)} funds using valuedate {candidate}")
                return True

            print("[Info] No fund data with a meaningful old-vs-latest spread found")
            return False
        except Exception as e:
            print(f"[Error] Failed to fetch page: {e}")
            return False