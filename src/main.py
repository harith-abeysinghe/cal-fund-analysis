"""CAL unit-trust tracker: collect daily prices and analyse them.

Commands:
  python -m src.main                      update prices, then analyse (default)
  python -m src.main update               update prices only (used by GitHub Actions)
  python -m src.main backfill --since 2014-01-01
  python -m src.main analyze --budget 90000 --risk-profile balanced --years 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.config import settings
from src.services.analysis_service import AnalysisService
from src.services.cal_api_client import CalApiClient
from src.services.inflation_analyzer import InflationAnalyzer, InflationStore
from src.services.market_context import MarketContextAnalyzer
from src.services.market_data import CseIndexClient, IndexHistoryStore, IndicatorStore
from src.services.nav_collector import CollectionResult, NavCollector
from src.services.nav_history_store import NavHistoryStore, SnapshotStore
from src.services.portfolio_planner import PortfolioPlanner
from src.services.portfolio_store import PortfolioStore
from src.services.report_writer import ReportWriter

logger = logging.getLogger("cal")


class Application:
    """Wires services together; holds no business logic of its own."""

    def __init__(self, data_dir: Path = settings.DATA_DIR, output_dir: Path = settings.OUTPUT_DIR) -> None:
        self.store = NavHistoryStore(data_dir / settings.NAV_HISTORY_PATH.name)
        self.snapshots = SnapshotStore(data_dir / settings.SNAPSHOT_PATH.name)
        self.output_dir = output_dir

    def collector(self, workers: int = 4) -> NavCollector:
        client = CalApiClient(settings.CAL_API_URL, settings.CAL_API_ACTION)
        return NavCollector(client, self.store, self.snapshots, set(settings.FUNDS), workers)

    def update(self) -> int:
        result = self.collector().update(settings.UPDATE_LOOKBACK_DAYS)
        self.update_market_index()
        return self._report_collection("update", result)

    @staticmethod
    def update_market_index() -> None:
        """Best effort: a CSE outage must not fail the fund-price update."""
        try:
            points = CseIndexClient(settings.CSE_CHART_URL).fetch_last_year()
            changed = IndexHistoryStore(settings.ASPI_PATH).merge(points)
            logger.info("ASPI: %d day(s) fetched, %d added/corrected", len(points), changed)
        except Exception as exc:  # noqa: BLE001 - network/JSON errors are non-fatal here
            logger.warning("ASPI update skipped: %s", exc)

    def backfill(self, since: date, step_days: int, workers: int) -> int:
        result = self.collector(workers).backfill(since, step_days=step_days)
        return self._report_collection("backfill", result)

    def analyze(self, budget: int, profile_name: str, years: int,
                portfolio_path: Path | None = settings.PORTFOLIO_PATH) -> int:
        current = PortfolioStore(portfolio_path, set(settings.FUNDS)).load() if portfolio_path else None
        if current:
            logger.info("Using current holdings from %s (%d funds)", portfolio_path.name, len(current.values_lkr))
        service = AnalysisService(
            settings.FUNDS, self.store, self.snapshots,
            PortfolioPlanner(settings.ELIGIBILITY, settings.FUNDS_PER_CLASS),
            ReportWriter(self.output_dir), settings.BENCHMARK_CODE,
            InflationAnalyzer(InflationStore(settings.INFLATION_PATH).load()),
            MarketContextAnalyzer(IndicatorStore(settings.INDICATORS_PATH).load(),
                                  IndexHistoryStore(settings.ASPI_PATH).series()))
        report = service.run(settings.RISK_PROFILES[profile_name], budget, years, current)
        print_console_safe(report)
        logger.info("Reports written to %s", self.output_dir)
        return 0

    def _report_collection(self, label: str, result: CollectionResult) -> int:
        logger.info("%s: %d day(s) requested, %d price(s) added/corrected, %d failed",
                    label, result.days_requested, result.prices_changed, len(result.failed_days))
        if result.failed_days:
            logger.warning("Failed days: %s", ", ".join(d.isoformat() for d in result.failed_days[:20]))
        if result.unknown_codes:
            logger.info("Untracked fund codes in API (add to settings.FUNDS to track): %s",
                        ", ".join(sorted(result.unknown_codes)))
        return 0 if result.ok else 1


def print_console_safe(value: str) -> None:
    """Print Unicode text even when Windows stdout uses a legacy code page."""
    try:
        print(value)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(value.encode(encoding, errors="replace").decode(encoding))


def add_analysis_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--budget", type=int, default=90_000, help="monthly budget in LKR (default 90000)")
    parser.add_argument("--risk-profile", choices=settings.RISK_PROFILES, default="balanced")
    parser.add_argument("--years", type=int, default=5, help="projection horizon in years (default 5)")
    parser.add_argument("--output-dir", type=Path, default=settings.OUTPUT_DIR)
    parser.add_argument("--portfolio", type=Path, default=settings.PORTFOLIO_PATH,
                        help="JSON of current holdings (default: portfolio.local.json, git-ignored)")
    parser.add_argument("--no-portfolio", action="store_true", help="ignore current holdings")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scrape-only", action="store_true", help="alias for the `update` command")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("update", help="fetch recent prices into data/nav_history.csv")
    backfill = sub.add_parser("backfill", help="fetch historical prices")
    backfill.add_argument("--since", type=date.fromisoformat, default=date(2014, 1, 1))
    backfill.add_argument("--step-days", type=int, default=1)
    backfill.add_argument("--workers", type=int, default=4)
    add_analysis_args(sub.add_parser("analyze", help="analyse stored prices"))
    add_analysis_args(sub.add_parser("run", help="update then analyse (default)"))
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    command = "update" if args.scrape_only else (args.command or "run")

    if command in ("analyze", "run") and getattr(args, "budget", 1) <= 0:
        logger.error("--budget must be positive")
        return 2

    app = Application(output_dir=getattr(args, "output_dir", settings.OUTPUT_DIR))
    if command == "update":
        return app.update()
    if command == "backfill":
        return app.backfill(args.since, args.step_days, args.workers)
    portfolio = None if getattr(args, "no_portfolio", False) else getattr(args, "portfolio", settings.PORTFOLIO_PATH)
    if command == "analyze":
        return app.analyze(args.budget, args.risk_profile, args.years, portfolio)

    # run: defaults apply when invoked with no sub-command
    budget = getattr(args, "budget", 90_000)
    profile = getattr(args, "risk_profile", "balanced")
    years = getattr(args, "years", 5)
    status = app.update()
    if status != 0:
        logger.warning("Price update failed; analysing the data already stored.")
    return app.analyze(budget, profile, years, portfolio) or status


if __name__ == "__main__":
    raise SystemExit(main())
