"""Weekly CAL fund data scraper - main entry point.

Usage:
    cd "D:/Personal/CAL Fund Analysis"
    .venv\Scripts\activate
    python src/main.py
"""

from pathlib import Path

from src.services.fund_scraper import FundScraper
from src.services.csv_manager import CSVManager

# Base URL for CAL fund data API
CAL_API_BASE = "https://cal.lk/wp-admin/admin-ajax.php"

# Data directory: project root / data
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Import InvestmentPlanner for generating recommendations
from src.services.investment_planner import InvestmentPlanner


def main() -> None:
    """Scrape CAL fund rates, record to CSV files, and generate investment recommendations."""
    print("[Init] Initializing CAL Fund Scraper...")

    # Step 1: Use FundScraper to fetch fund data from the CAL API
    scraper = FundScraper(url=CAL_API_BASE, data_dir=DATA_DIR)
    funds = scraper.scrape_funds()

    if not funds:
        print("[Warn] No fund data retrieved - nothing to record")
        return

    print(f"[OK] Scraped {len(funds)} fund data point(s) from CAL API")

    # Step 2: Use CSVManager to write the returns to the relevant CSV files
    csv_manager = CSVManager(data_dir=DATA_DIR)
    csv_manager.record_returns(funds)

    print(f"[OK] Updated fund data recorded to CSV files")

    # Step 3: Generate investment recommendations
    # Use max LKR investment as per project spec (100,000 LKR/month max)
    planner = InvestmentPlanner(max_investment_lkr=100_000)

    # Get top funds based on price growth
    top_funds = planner.get_top_funds(funds, count=3)
    if not top_funds:
        print("[Info] No funds available for recommendation")
        return

    # Compute allocation plan
    allocations = planner.plan_investment(top_funds)

    # Prepare recommendation output
    recommendation_output = "📊 Investment Recommendation - {current_date}\n\n".format(
        current_date=funds[0]["latest_date"]
    )
    recommendation_output += "🏆 Top 3 Best Performing Funds:\n"
    for fund_name, allocation in allocations:
        recommendation_output += f"• {fund_name}: {allocation:,} LKR\n"
    recommendation_output += "\n💰 Total Allocation: 100,000 LKR or less\n"
    recommendation_output += "\n📈 Pattern Analysis: Active Momentum Phase\n"

    # Save recommendation to output directory for WhatsApp gateway pickup
    date_str = funds[0]["latest_date"]
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    recommendation_path = output_dir / f"recommendation_{date_str}.txt"
    recommendation_path.write_text(recommendation_output.strip(), encoding="utf-8")
    print(f"[OK] Recommendation saved to {recommendation_path}")
    print(recommendation_output.strip())


if __name__ == "__main__":
    main()