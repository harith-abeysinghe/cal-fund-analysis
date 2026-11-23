"""Relates fund performance to the main external drivers of unit prices:
interest rates (policy rate, T-bills, fixed deposits), the stock market (ASPI)
and the rupee exchange rate."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.models.fund import AssetClass, FundMetrics, PricePoint
from src.services.fund_analytics import FundAnalytics, PriceSeries
from src.services.market_data import Indicator, IndicatorStore


@dataclass
class RateComparison:
    code: str
    yield_30d_ann: float
    vs_tbill_364d_pp: float | None
    vs_fd_12m_pp: float | None


@dataclass
class EquityVsIndex:
    code: str
    fund_return_pct: float
    index_return_pct: float
    since: str
    correlation: float | None
    beta: float | None


@dataclass
class UsdReturn:
    code: str
    label: str
    lkr_return_pct: float
    lkr_vs_usd_pct: float
    usd_return_pct: float


@dataclass
class MarketContext:
    rates: dict[str, dict[str, object]] = field(default_factory=dict)
    rate_comparisons: list[RateComparison] = field(default_factory=list)
    equity_vs_index: list[EquityVsIndex] = field(default_factory=list)
    usd_returns: list[UsdReturn] = field(default_factory=list)
    index_latest: dict[str, object] | None = None
    insights: list[str] = field(default_factory=list)


class MarketContextAnalyzer:
    RATE_KEYS = ("policy_rate_opr", "tbill_91d", "tbill_182d", "tbill_364d", "fd_12m_avg")

    def __init__(self, indicators: list[Indicator], index_points: list[PricePoint]) -> None:
        self._indicators = indicators
        self._index = PriceSeries(index_points) if index_points else None

    EQUITY_PREMIUM_PP = 3.0

    def equity_base_rate(self) -> float | None:
        """Base-case equity return: 12-month T-bill + a modest equity risk premium."""
        tbill = IndicatorStore.latest(self._indicators, "tbill_364d")
        return round(tbill.value + self.EQUITY_PREMIUM_PP, 2) if tbill else None

    def analyze(self, metrics: list[FundMetrics], analytics: dict[str, FundAnalytics],
                relevant_codes: set[str]) -> MarketContext:
        ctx = MarketContext()
        latest = {k: IndicatorStore.latest(self._indicators, k) for k in self.RATE_KEYS}
        ctx.rates = {k: {"value": i.value, "date": i.day.isoformat(), "note": i.note, "source": i.source}
                     for k, i in latest.items() if i}
        tbill, fd, opr = latest["tbill_364d"], latest["fd_12m_avg"], latest["policy_rate_opr"]

        for m in metrics:
            if (m.code in relevant_codes and m.asset_class != AssetClass.GROWTH.value
                    and m.yield_30d_ann is not None):
                ctx.rate_comparisons.append(RateComparison(
                    m.code, m.yield_30d_ann,
                    round(m.yield_30d_ann - tbill.value, 2) if tbill else None,
                    round(m.yield_30d_ann - fd.value, 2) if fd else None))

        if self._index:
            ctx.index_latest = {"date": self._index.end.isoformat(), "value": self._index.latest.price}
            for m in metrics:
                if m.asset_class == AssetClass.GROWTH.value and m.code in analytics:
                    row = self._vs_index(analytics[m.code])
                    if row:
                        ctx.equity_vs_index.append(row)

        ctx.usd_returns = self._usd_returns(analytics, relevant_codes)
        ctx.insights = self._insights(ctx, tbill, fd, opr)
        return ctx

    def _vs_index(self, fund: FundAnalytics) -> EquityVsIndex | None:
        index = self._index
        start = max(index.start, fund.series.start)
        end = min(index.end, fund.series.end)
        if (end - start).days < 120:
            return None
        f0, f1 = fund.series.at_or_before(start), fund.series.at_or_before(end)
        i0, i1 = index.at_or_before(start), index.at_or_before(end)
        if not (f0 and f1 and i0 and i1):
            return None
        fr, ir = [], []
        day = start
        prev_f, prev_i = f0.price, i0.price
        while day + timedelta(days=7) <= end:
            day += timedelta(days=7)
            fp, ip = fund.series.at_or_before(day), index.at_or_before(day)
            if fp and ip:
                fr.append(math.log(fp.price / prev_f))
                ir.append(math.log(ip.price / prev_i))
                prev_f, prev_i = fp.price, ip.price
        corr = beta = None
        if len(fr) >= 15 and statistics.pstdev(ir) > 0:
            corr = round(statistics.correlation(fr, ir), 2)
            beta = round(statistics.covariance(fr, ir) / statistics.variance(ir), 2)
        return EquityVsIndex(fund.info.code, round((f1.price / f0.price - 1) * 100, 2),
                             round((i1.price / i0.price - 1) * 100, 2), start.isoformat(), corr, beta)

    def _usd_returns(self, analytics: dict[str, FundAnalytics], codes: set[str]) -> list[UsdReturn]:
        fx = sorted((i for i in self._indicators if i.name == "usd_lkr"), key=lambda i: i.day)
        periods: list[tuple[str, date, date, float]] = []
        for a, b in zip(fx, fx[1:]):
            periods.append((str(b.day.year), a.day, b.day, (a.value / b.value - 1) * 100))
        ytd = IndicatorStore.latest(self._indicators, "lkr_ytd_change_pct")
        if ytd and fx and fx[-1].day.year == ytd.day.year - 1:
            periods.append((f"{ytd.day.year} to {ytd.day:%d-%b}", fx[-1].day, ytd.day, ytd.value))
        out: list[UsdReturn] = []
        for code in sorted(codes):
            fund = analytics.get(code)
            if not fund:
                continue
            for label, start, end, lkr_change in periods:
                p0 = fund.series.at_or_before(start, tolerance_days=10)
                p1 = fund.series.at_or_before(end, tolerance_days=10)
                if not (p0 and p1) or start < fund.series.start:
                    continue
                r = p1.price / p0.price - 1
                usd = (1 + r) * (1 + lkr_change / 100) - 1
                out.append(UsdReturn(code, label, round(r * 100, 2), round(lkr_change, 2), round(usd * 100, 2)))
        return out

    @staticmethod
    def _insights(ctx: MarketContext, tbill: Indicator | None, fd: Indicator | None,
                  opr: Indicator | None) -> list[str]:
        out: list[str] = []
        if opr:
            out.append(f"Interest rates: {opr.note} ({opr.day}). Rate hikes push up T-bill and deposit "
                       "rates; money market funds reprice within weeks, while bond-heavy funds can dip "
                       "briefly (bond prices fall when yields rise) before their yields catch up.")
        if tbill and ctx.rate_comparisons:
            below = [r.code for r in ctx.rate_comparisons if r.vs_tbill_364d_pp is not None and r.vs_tbill_364d_pp < 0]
            above = [f"{r.code} {r.vs_tbill_364d_pp:+.2f}" for r in ctx.rate_comparisons
                     if r.vs_tbill_364d_pp is not None and r.vs_tbill_364d_pp >= 0]
            text = f"Alternatives: 12-month T-bill {tbill.value:.2f}%"
            if fd:
                text += f", average 12-month FD {fd.value:.2f}%"
            text += ". Fund running yield minus T-bill (pp): " + (", ".join(above) if above else "none ahead")
            if below:
                text += f"; below the T-bill: {', '.join(below)}"
            out.append(text + ". Funds stay liquid (redeem any day) while an FD/T-bill locks the money in; "
                              "compare after the same 10% WHT.")
        for e in ctx.equity_vs_index:
            text = (f"{e.code} vs CSE ASPI since {e.since}: fund {e.fund_return_pct:+.2f}% vs index "
                    f"{e.index_return_pct:+.2f}%")
            if e.beta is not None:
                text += f" (beta {e.beta}, correlation {e.correlation})"
            out.append(text + ". The fund mostly follows the local stock market; it is not diversified "
                              "away from it.")
        for label in sorted({u.label for u in ctx.usd_returns}):
            rows = [u for u in ctx.usd_returns if u.label == label]
            change = rows[0].lkr_vs_usd_pct
            out.append(f"In US dollar terms ({label}, rupee {change:+.1f}% vs USD): "
                       + ", ".join(f"{u.code} {u.usd_return_pct:+.1f}%" for u in rows) + ".")
        return out
