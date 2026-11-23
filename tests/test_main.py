import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.config.settings import ELIGIBILITY, FUNDS_PER_CLASS, RISK_PROFILES
from src.models.fund import AssetClass, FundInfo, FundSnapshot, PricePoint
from src.models.inflation import InflationPeriod
from src.models.portfolio import CurrentPortfolio
from src.services.cal_api_client import CalApiClient
from src.services.fund_analytics import FundAnalytics, SeriesCleaner
from src.services.inflation_analyzer import InflationAnalyzer
from src.services.nav_collector import NavCollector
from src.services.nav_history_store import NavHistoryStore, SnapshotStore
from src.services.portfolio_planner import PortfolioPlanner
from src.services.portfolio_store import PortfolioStore

END = date(2026, 11, 22)


def accrual_series(annual_pct: float, days: int = 6 * 365, start_price: float = 10.0) -> list[PricePoint]:
    """Smooth daily-accruing price, like a fixed income fund."""
    start = END - timedelta(days=days)
    daily = (1 + annual_pct / 100) ** (1 / 365)
    return [PricePoint(start + timedelta(days=i), start_price * daily ** i) for i in range(days + 1)]


class FakeClient(CalApiClient):
    def __init__(self, prices: dict[str, dict[date, float]]) -> None:
        super().__init__("https://example.test", "x")
        self.prices = prices
        self.calls: list[date] = []

    def fetch_rates(self, value_date: date) -> list[dict]:
        self.calls.append(value_date)
        return [{"FUND": code, "FUND_NAME": code, "OLD_DATE": value_date.isoformat(),
                 "OLD_PRICE": str(series[value_date]), "LATEST_DATE": "2026-11-22",
                 "LATEST_PRICE": str(series[max(series)]), "PORTFOLIO": "500000000", "RATE_PERIOD": "30"}
                for code, series in self.prices.items() if value_date in series]


class AnalyticsTests(unittest.TestCase):
    def test_cal_calculator_style_30_day_annualised(self):
        # CAL calculator: IGF 30-day annualised 10.43% <=> Rs 8,576.43 on Rs 1,000,000.
        info = FundInfo("IGF", "IGF", AssetClass.INCOME)
        points = [PricePoint(END - timedelta(days=30), 100.0), PricePoint(END, 100.857643)]
        analytics = FundAnalytics(info, points, None, today=END)
        self.assertAlmostEqual(analytics.simple_annualized(30), 10.43, places=2)

    def test_one_year_is_exactly_365_days_and_cagr(self):
        info = FundInfo("IF", "IF", AssetClass.INCOME)
        metrics = FundAnalytics(info, accrual_series(10.0), None, today=END).metrics()
        self.assertAlmostEqual(metrics.return_1y, 10.0, places=1)
        self.assertAlmostEqual(metrics.cagr_3y, 10.0, places=1)
        self.assertAlmostEqual(metrics.cagr_5y, 10.0, places=1)
        self.assertEqual(metrics.max_drawdown_3y, 0.0)
        self.assertEqual(metrics.pct_positive_rolling_1y, 100.0)

    def test_drawdown_and_excess_return_vs_benchmark(self):
        equity = FundInfo("QEF", "QEF", AssetClass.GROWTH)
        start = END - timedelta(days=800)
        points = [PricePoint(start + timedelta(days=i), 100.0 + (i if i < 400 else 800 - i) * 0.05)
                  for i in range(801)]
        bench = FundAnalytics(FundInfo("GMMF", "GMMF", AssetClass.LIQUID), accrual_series(8.0), None, END)
        metrics = FundAnalytics(equity, points, None, today=END).metrics(bench)
        self.assertAlmostEqual(metrics.max_drawdown_3y, -16.67, places=1)  # 120 -> 100
        self.assertLess(metrics.excess_1y_vs_benchmark, 0)

    def test_cleaner_drops_reverting_spike_and_cuts_at_distribution(self):
        d = [END - timedelta(days=5 - i) for i in range(6)]
        points = [PricePoint(d[0], 10.0), PricePoint(d[1], 10.01), PricePoint(d[2], 15.0),
                  PricePoint(d[3], 10.02), PricePoint(d[4], 4.0), PricePoint(d[5], 4.01)]
        cleaned = SeriesCleaner.clean(points, 0.03)
        self.assertEqual([p.price for p in cleaned.points], [4.0, 4.01])
        self.assertEqual(len(cleaned.breaks), 2)

    def test_cleaner_drops_multi_day_glitch(self):
        prices = [10.0, 10.01, 5.5, 5.5, 5.5, 10.03, 10.04]  # e.g. GF Dec 2015
        points = [PricePoint(END - timedelta(days=len(prices) - i), p) for i, p in enumerate(prices)]
        cleaned = SeriesCleaner.clean(points, 0.05)
        self.assertEqual([p.price for p in cleaned.points], [10.0, 10.01, 10.03, 10.04])


class InflationTests(unittest.TestCase):
    def test_real_return_per_calendar_year_and_cumulative(self):
        fund = FundAnalytics(FundInfo("IF", "IF", AssetClass.INCOME), accrual_series(10.0), None, END)
        periods = [InflationPeriod(date(2023, 12, 31), "2023", 10.0, ""),
                   InflationPeriod(date(2024, 12, 31), "2024", 0.0, ""),
                   InflationPeriod(date(2026, 10, 31), "12m to Oct-2026", 21.0, "")]
        result = InflationAnalyzer(periods).analyze(fund)
        by_label = {p.label: p for p in result.periods}
        self.assertAlmostEqual(by_label["2023"].real_pct, 0.0, places=1)    # 10% vs 10% inflation
        self.assertAlmostEqual(by_label["2024"].real_pct, 10.0, places=1)
        self.assertAlmostEqual(by_label["12m to Oct-2026"].real_pct, -9.09, places=1)
        self.assertEqual(result.years_beaten, 1)
        self.assertAlmostEqual(result.cumulative_real_pct, 10.0, places=0)  # trailing period excluded

    def test_period_before_history_is_skipped(self):
        fund = FundAnalytics(FundInfo("IF", "IF", AssetClass.INCOME), accrual_series(10.0, days=400), None, END)
        result = InflationAnalyzer([InflationPeriod(date(2020, 12, 31), "2020", 4.2, "")]).analyze(fund)
        self.assertEqual(result.periods, [])


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = PortfolioPlanner(ELIGIBILITY, FUNDS_PER_CLASS)
        bench = FundAnalytics(FundInfo("GMMF", "MMF", AssetClass.LIQUID), accrual_series(8.0), None, END)
        specs = [("GMMF", AssetClass.LIQUID, 8.0, True), ("IGF", AssetClass.INCOME, 9.5, True),
                 ("CAHYF", AssetClass.INCOME, 11.0, True), ("IF", AssetClass.INCOME, 10.5, True),
                 ("QEF", AssetClass.GROWTH, 14.0, True), ("FYCF", AssetClass.INCOME, 12.0, False)]
        self.metrics = []
        for code, cls, rate, open_ended in specs:
            snap = FundSnapshot(code, code, END.isoformat(), 1.0, 1.0, 1e9, 30)
            fa = FundAnalytics(FundInfo(code, code, cls, open_ended), accrual_series(rate), snap, END)
            self.metrics.append(fa.metrics(bench))
        self.planner.assess(self.metrics)

    def test_closed_end_excluded_and_scored_within_class(self):
        by = {m.code: m for m in self.metrics}
        self.assertFalse(by["FYCF"].eligible)
        self.assertEqual(by["CAHYF"].rank_in_class, 1)
        self.assertEqual(by["QEF"].rank_in_class, 1)  # equity ranked only among growth funds

    def test_allocation_follows_profile_and_sums_to_budget(self):
        plan = self.planner.allocate(self.metrics, RISK_PROFILES["balanced"], 90_000)
        self.assertEqual(sum(h.allocation_lkr for h in plan.holdings), 90_000)
        by_class = {}
        for h in plan.holdings:
            by_class[h.asset_class] = by_class.get(h.asset_class, 0) + h.allocation_lkr
        self.assertEqual(by_class, {"liquid": 4_000, "income": 68_000, "growth": 18_000})
        self.assertEqual({h.code for h in plan.holdings}, {"GMMF", "CAHYF", "IF", "QEF"})

    def test_existing_holdings_steer_new_money_to_underweight_classes(self):
        current = CurrentPortfolio("2026-11-23", {"CAHYF": 300_000.0, "IF": 100_000.0})
        plan = self.planner.allocate(self.metrics, RISK_PROFILES["balanced"], 90_000, current)
        self.assertEqual(sum(h.allocation_lkr for h in plan.holdings), 90_000)
        self.assertNotIn("income", {h.asset_class for h in plan.holdings})  # income already overweight
        review = self.planner.review(self.metrics, current, RISK_PROFILES["balanced"])
        self.assertEqual(review.class_weights_pct["income"], 100.0)
        self.planner.project(plan, self.metrics, 5, current)
        self.assertGreater(plan.projections[0].projected_value_lkr, 90_000 * 60 + 400_000)


class StorageTests(unittest.TestCase):
    def test_collector_backfill_and_incremental_update(self):
        prices = {"IGF": {END - timedelta(days=i): 40.0 - i * 0.01 for i in range(20)}}
        with tempfile.TemporaryDirectory() as tmp:
            store = NavHistoryStore(Path(tmp) / "nav.csv")
            client = FakeClient(prices)
            collector = NavCollector(client, store, SnapshotStore(Path(tmp) / "snap.json"), {"IGF"}, workers=2)
            result = collector.backfill(END - timedelta(days=19), END)
            self.assertEqual(result.prices_changed, 20)

            reloaded = NavHistoryStore(Path(tmp) / "nav.csv")
            self.assertEqual(len(reloaded.series("IGF")), 20)
            self.assertEqual(reloaded.last_date(), END)

            client.calls.clear()
            again = NavCollector(client, reloaded, SnapshotStore(Path(tmp) / "snap.json"), {"IGF"}, 1)
            self.assertEqual(again.update(lookback_days=3, today=END).prices_changed, 0)
            self.assertEqual(min(client.calls), END - timedelta(days=3))
            snap = SnapshotStore(Path(tmp) / "snap.json").load()["IGF"]
            self.assertEqual(snap.aum_lkr, 500_000_000)

    def test_portfolio_store_ignores_unknown_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps({"as_of": "2026-11-23",
                                        "holdings": {"igf": 1000, "NOPE": 5}}), encoding="utf-8")
            portfolio = PortfolioStore(path, {"IGF"}).load()
            self.assertEqual(portfolio.values_lkr, {"IGF": 1000.0})
            self.assertIsNone(PortfolioStore(Path(tmp) / "missing.json", {"IGF"}).load())


if __name__ == "__main__":
    unittest.main()
