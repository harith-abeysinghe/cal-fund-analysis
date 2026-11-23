"""Orchestrates: price history -> metrics -> eligibility/scoring -> plan -> report."""

from __future__ import annotations

import statistics
from datetime import date

from src.config.settings import RiskProfile
from src.models.fund import AssetClass, FundInfo, FundMetrics
from src.models.inflation import FundRealReturns
from src.models.portfolio import CurrentPortfolio, PortfolioReview
from src.services.fund_analytics import FundAnalytics
from src.services.inflation_analyzer import InflationAnalyzer
from src.services.market_context import MarketContextAnalyzer
from src.services.nav_history_store import NavHistoryStore, SnapshotStore
from src.services.portfolio_planner import PortfolioPlanner
from src.services.report_writer import ReportWriter


class InsightBuilder:
    """Plain-language observations a reader should weigh before acting."""

    @staticmethod
    def build(metrics: list[FundMetrics], benchmark_code: str) -> list[str]:
        out: list[str] = []
        by_code = {m.code: m for m in metrics}
        bench = by_code.get(benchmark_code)
        income = [m for m in metrics if m.asset_class == AssetClass.INCOME.value and m.eligible]
        growth = [m for m in metrics if m.asset_class == AssetClass.GROWTH.value]

        if bench and bench.return_1y is not None:
            out.append(f"Hurdle rate: the money market fund ({benchmark_code}) returned {bench.return_1y:.2f}% "
                       f"over 1Y and is currently running at {bench.yield_30d_ann or 0:.2f}% annualised. "
                       "A riskier fund should beat this to justify its risk.")
            laggards = [m.code for m in metrics if m.eligible and m.code != benchmark_code
                        and m.excess_1y_vs_benchmark is not None and m.excess_1y_vs_benchmark < 0]
            if laggards:
                out.append(f"Did not beat money market over 1Y: {', '.join(laggards)}.")

        trends = [m.yield_trend_pp for m in income if m.yield_trend_pp is not None]
        if trends:
            avg = statistics.mean(trends)
            direction = "falling" if avg < -0.25 else "rising" if avg > 0.25 else "roughly flat"
            out.append(f"Fixed-income running yields are {direction}: 30-day annualised yield changed "
                       f"{avg:+.2f} pp on average versus 90 days ago. Today's yield is the best guide to "
                       "near-term returns for these funds, so expect returns to follow this direction.")

        for m in growth:
            parts = [f"{m.code}: 1Y {m.return_1y:+.2f}%" if m.return_1y is not None else m.code]
            if m.cagr_3y is not None:
                parts.append(f"3Y CAGR {m.cagr_3y:+.2f}%")
            if m.current_drawdown is not None and m.current_drawdown < -5:
                parts.append(f"{abs(m.current_drawdown):.1f}% below its 3-year high")
            if m.worst_rolling_1y is not None:
                parts.append(f"worst 1Y in history {m.worst_rolling_1y:+.2f}%")
            if m.pct_positive_rolling_1y is not None:
                parts.append(f"positive in {m.pct_positive_rolling_1y:.0f}% of 1Y periods")
            out.append(", ".join(parts) + ". Equity needs a 5+ year horizon; judge it on long-run CAGR, "
                       "not the last 12 months.")

        costly = [m for m in metrics if (m.price_spread_pct or 0) > 0.5]
        for m in costly:
            out.append(f"{m.code} has a {m.price_spread_pct:.2f}% gap between its buy and sell prices "
                       "- a round trip costs about that much, so short holding periods can lose money.")

        small = [f"{m.code} (LKR {m.aum_lkr / 1e6:,.0f}M)" for m in metrics
                 if m.aum_lkr is not None and any(n.startswith("small fund") for n in m.eligibility_notes)]
        if small:
            out.append("Excluded as too small to rely on: " + ", ".join(small) + ".")

        if len(income) >= 2:
            best = max(income, key=lambda m: m.return_1y or -99)
            worst = min(income, key=lambda m: m.return_1y or 99)
            out.append(f"Within fixed income the 1Y spread is {best.code} {best.return_1y:.2f}% vs "
                       f"{worst.code} {worst.return_1y:.2f}% - on LKR 1,000,000 that is "
                       f"LKR {(best.return_1y - worst.return_1y) * 10_000:,.0f} a year.")
        return out


class InflationInsights:
    """Observations about returns after Sri Lanka inflation."""

    @staticmethod
    def build(metrics: list[FundMetrics], real: dict[str, FundRealReturns],
              inflation: InflationAnalyzer | None, review: PortfolioReview | None) -> list[str]:
        if not inflation or not real:
            return []
        out: list[str] = []
        latest = inflation.periods[-1]
        relevant = [m for m in metrics if m.eligible or (review and m.code in {p.code for p in review.positions})]
        beat = []
        for m in relevant:
            r = real.get(m.code)
            if r and r.periods:
                full_years = [p for p in r.periods if p.label.isdigit()]
                beat.append(f"{m.code} {sum(p.beat_inflation for p in full_years)}/{len(full_years)}")
        if beat:
            out.append("Calendar years each fund beat CCPI inflation: " + ", ".join(beat) + ".")
        hit = [p for p in inflation.periods if p.ccpi_yoy_pct >= 20]
        for period in hit:
            losses = [f"{code} {p.real_pct:+.1f}%" for code, r in real.items()
                      for p in r.periods if p.label == period.label and code in {m.code for m in relevant}]
            if losses:
                out.append(f"{period.label}: inflation was {period.ccpi_yoy_pct:.1f}% - real returns were "
                           + ", ".join(losses) + ". A single inflation shock can wipe out several years "
                           "of real gains in fixed income.")
        out.append(f"Inflation is rising again: CCPI {latest.ccpi_yoy_pct:.1f}% for the {latest.label} "
                   "(Central Bank target 5% +/- 2%). Compare running yields with this, not with last year's "
                   "low inflation.")
        below = [f"{m.code} {m.yield_30d_ann:.2f}%" for m in relevant
                 if m.yield_30d_ann is not None and m.yield_30d_ann < latest.ccpi_yoy_pct]
        if below:
            out.append(f"Running yield below {latest.ccpi_yoy_pct:.1f}% inflation (losing purchasing power "
                       f"today): {', '.join(below)}. Keep only an emergency buffer in these; fixed income "
                       "funds can also be redeemed any day.")
        if review and review.weighted_yield_pct is not None:
            real_yield = ((1 + review.weighted_yield_pct / 100) / (1 + latest.ccpi_yoy_pct / 100) - 1) * 100
            out.append(f"Your blended running yield of {review.weighted_yield_pct:.2f}% is about "
                       f"{real_yield:+.2f}% after {latest.ccpi_yoy_pct:.1f}% inflation (before the 10% WHT, "
                       "which lowers it further).")
        return out


class AnalysisService:
    def __init__(self, funds: dict[str, FundInfo], store: NavHistoryStore, snapshots: SnapshotStore,
                 planner: PortfolioPlanner, writer: ReportWriter, benchmark_code: str,
                 inflation: InflationAnalyzer | None = None,
                 market: MarketContextAnalyzer | None = None) -> None:
        self._funds = funds
        self._store = store
        self._snapshots = snapshots
        self._planner = planner
        self._writer = writer
        self._benchmark_code = benchmark_code
        self._inflation = inflation if inflation and inflation.periods else None
        self._market = market

    def build_analytics(self, today: date | None = None) -> dict[str, FundAnalytics]:
        snapshots = self._snapshots.load()
        analytics: dict[str, FundAnalytics] = {}
        for code, info in self._funds.items():
            points = self._store.series(code)
            if points:
                analytics[code] = FundAnalytics(info, points, snapshots.get(code), today)
        if not analytics:
            raise RuntimeError("No price history found - run `python -m src.main backfill` first.")
        return analytics

    def compute_metrics(self, today: date | None = None) -> list[FundMetrics]:
        analytics = self.build_analytics(today)
        benchmark = analytics.get(self._benchmark_code)
        return [a.metrics(benchmark) for a in analytics.values()]

    def run(self, profile: RiskProfile, budget: int, years: int,
            current: CurrentPortfolio | None = None, today: date | None = None) -> str:
        analytics = self.build_analytics(today)
        benchmark = analytics.get(self._benchmark_code)
        metrics = [a.metrics(benchmark) for a in analytics.values()]
        self._planner.assess(metrics)
        review = self._planner.review(metrics, current, profile) if current else None
        plan = self._planner.allocate(metrics, profile, budget, current)
        equity_base = self._market.equity_base_rate() if self._market else None
        self._planner.project(plan, metrics, years, current, equity_base)
        real = {code: self._inflation.analyze(a) for code, a in analytics.items()} if self._inflation else {}
        insights = InsightBuilder.build(metrics, self._benchmark_code)
        insights += InflationInsights.build(metrics, real, self._inflation, review)
        market = None
        if self._market:
            relevant = {m.code for m in metrics if m.eligible}
            relevant |= {p.code for p in review.positions} if review else set()
            market = self._market.analyze(metrics, analytics, relevant)
            insights += market.insights
        return self._writer.write(metrics, plan, profile, self._benchmark_code, insights, review,
                                  real, self._inflation.periods if self._inflation else [], market)
