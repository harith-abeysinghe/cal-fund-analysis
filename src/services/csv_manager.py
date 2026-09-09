import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

class CSVManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_scraped_date(self) -> str:
        """
        Get the appropriate date for recording based on the day of the week.

        Rules:
        - If today is Tuesday, use Monday's date
        - If today is Saturday, Sunday, or Monday, use the previous Friday's date
        - Otherwise (Wed, Thu, Fri), use today's date

        Returns date in ISO format (YYYY-MM-DD)
        """
        today = date.today()
        today_weekday = today.weekday()  # Monday=0, Sunday=6

        if today_weekday == 0:  # Monday
            # Use Friday's date (3 days ago)
            scraped_date = today - timedelta(days=3)
        elif today_weekday == 1:  # Tuesday
            # Use Monday's date (1 day ago)
            scraped_date = today - timedelta(days=1)
        elif today_weekday in (5, 6):  # Saturday (5) or Sunday (6)
            # Use previous Friday's date (1 or 2 days ago)
            days_to_subtract = 1 if today_weekday == 5 else 2
            scraped_date = today - timedelta(days=days_to_subtract)
        else:
            # Wednesday (2), Thursday (3), or Friday (4) - use today
            scraped_date = today

        return scraped_date.isoformat()

    def record_returns(self, funds: List[Dict]) -> None:
        today = self._get_scraped_date()
        for fund in funds:
            fund_name = fund['name']
            safe_name = fund_name.replace(' ', '_')
            csv_path = self.data_dir / f'{safe_name}.csv'
            file_exists = csv_path.exists()

            # Flag to determine if we should write this entry
            write_entry = True
            if file_exists:
                try:
                    with csv_path.open('r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Check if this exact entry already exists
                            if (row.get('scraped_date') == today and
                                row.get('old_date') == fund['old_date'] and
                                row.get('new_date') == fund['latest_date']):
                                print(f"[Info] Data already exists for {fund_name} on {today}, skipping duplicate entry")
                                write_entry = False
                                break
                except Exception as e:
                    print(f"[Error] Failed to check for duplicates in {csv_path}: {e}")

            # Append new data if it doesn't exist and no duplicate was found
            if write_entry:
                with csv_path.open('a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['scraped_date', 'old_date', 'old_price', 'new_date', 'new_price', 'price_difference', 'price_growth'])
                    # Use actual values from API response
                    writer.writerow([
                        today,
                        fund['old_date'],
                        fund['old_price'],
                        fund['latest_date'],
                        fund['latest_price'],
                        fund['price_difference'],
                        fund['price_growth']
                    ])
