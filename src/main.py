"""CAL fund scraper and recommendation entry point."""

import argparse
import sys
from pathlib import Path

from src.services.csv_manager import CSVManager
from src.services.fund_scraper import FundScraper
from src.services.investment_planner import InvestmentPlanner

# Base URL for CAL fund data API
CAL_API_BASE = "https://cal.lk/wp-admin/admin-ajax.php"

# Data directory: project root / data
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def print_console_safe(value: str) -> None:
    """Print Unicode text even when Windows stdout uses a legacy code page."""
    try:
        print(value)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(value.encode(encoding, errors="replace").decode(encoding))


def scrape_and_record() -> list[dict]:
    """Fetch the tracked funds and append any new observations to their CSVs."""
    print("[Init] Initializing CAL Fund Scraper...")
    scraper = FundScraper(url=CAL_API_BASE)
    funds = scraper.scrape_funds()

    if not funds:
        print("[Warn] No fund data retrieved - nothing to record")
        return []

    print(f"[OK] Scraped {len(funds)} fund data point(s) from CAL API")
    csv_manager = CSVManager(data_dir=DATA_DIR)
    csv_manager.record_returns(funds)
    print("[OK] Updated fund data recorded to CSV files")
    return funds


def write_recommendation(funds: list[dict]) -> None:
    """Generate the existing recommendation output for interactive runs."""
    planner = InvestmentPlanner(max_investment_lkr=100_000)
    top_funds = planner.get_top_funds(funds, count=3)
    if not top_funds:
        print("[Info] No funds available for recommendation")
        return

    allocations = planner.plan_investment(top_funds)
    recommendation_output = "📊 Investment Recommendation - {current_date}\n\n".format(
        current_date=funds[0]["latest_date"]
    )
    recommendation_output += "🏆 Top 3 Best Performing Funds:\n"
    for fund_name, allocation in allocations:
        recommendation_output += f"• {fund_name}: {allocation:,} LKR\n"
    recommendation_output += "\n💰 Total Allocation: 100,000 LKR or less\n"
    recommendation_output += "\n📈 Pattern Analysis: Active Momentum Phase\n"

    date_str = funds[0]["latest_date"]
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    recommendation_path = output_dir / f"recommendation_{date_str}.txt"
    recommendation_path.write_text(recommendation_output.strip(), encoding="utf-8")
    print(f"[OK] Recommendation saved to {recommendation_path}")
    print_console_safe(recommendation_output.strip())


def main(argv: list[str] | None = None) -> int:
    """Scrape data, with optional recommendation generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="update data/*.csv without generating recommendation output",
    )
    args = parser.parse_args(argv)

    funds = scrape_and_record()
    if not funds:
        return 1
    if not args.scrape_only:
        write_recommendation(funds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
