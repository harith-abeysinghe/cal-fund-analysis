"""FundScraper service - scrapes CAL fund rates from the AJAX endpoint."""

import datetime
import requests


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
        "CDGTF": "CAL Fixed Income Opportunities Fund",
    }
    TARGET_FUNDS = list(FUND_CODE_MAP.keys())

    def __init__(self, url: str) -> None:
        self.url = url
        self._page_content: dict | None = None

    def scrape_funds(self) -> list[dict]:
        """Extract fund data from the AJAX endpoint for target funds only."""
        if not self._fetch_page():
            return []

        # The response is {"UTMS_FUND": [ {...}, {...} ]}
        funds_list = self._page_content.get("UTMS_FUND", []) if isinstance(self._page_content, dict) else []

        # Check if we got valid data
        if not funds_list:
            print("[Info] No fund data in API response")
            return []

        funds: list[dict] = []
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
