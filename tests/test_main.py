import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import main


class MainCommandTests(unittest.TestCase):
    @patch("src.main.FundScraper")
    def test_scrape_and_record_updates_csv_without_network(self, fund_scraper):
        fund = {
            "name": "CAL Income Fund",
            "old_date": "2025-09-08",
            "old_price": 100.0,
            "latest_date": "2026-09-08",
            "latest_price": 110.0,
            "price_difference": 10.0,
            "price_growth": 10.0,
        }
        fund_scraper.return_value.scrape_funds.return_value = [fund]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(main, "DATA_DIR", Path(temp_dir)):
                result = main.scrape_and_record()

            csv_path = Path(temp_dir) / "CAL_Income_Fund.csv"
            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(result, [fund])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["new_price"], "110.0")
        fund_scraper.assert_called_once_with(url=main.CAL_API_BASE)

    @patch("src.main.write_recommendation")
    @patch("src.main.scrape_and_record")
    def test_scrape_only_skips_recommendation(self, scrape_and_record, write_recommendation):
        scrape_and_record.return_value = [{"name": "CAL Income Fund"}]

        result = main.main(["--scrape-only"])

        self.assertEqual(result, 0)
        write_recommendation.assert_not_called()

    @patch("src.main.write_recommendation")
    @patch("src.main.scrape_and_record")
    def test_default_run_keeps_recommendation(self, scrape_and_record, write_recommendation):
        funds = [{"name": "CAL Income Fund"}]
        scrape_and_record.return_value = funds

        result = main.main([])

        self.assertEqual(result, 0)
        write_recommendation.assert_called_once_with(funds)

    @patch("src.main.write_recommendation")
    @patch("src.main.scrape_and_record", return_value=[])
    def test_empty_scrape_fails_command(self, scrape_and_record, write_recommendation):
        result = main.main(["--scrape-only"])

        self.assertEqual(result, 1)
        write_recommendation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
