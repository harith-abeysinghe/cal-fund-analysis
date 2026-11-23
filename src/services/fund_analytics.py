"""Turns a daily unit-price series into return and risk metrics."""

from __future__ import annotations

import bisect
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from src.models.fund import AssetClass, FundInfo, FundMetrics, FundSnapshot, PricePoint

# A one-day move larger than this is not market movement for that asset class;
# it is a distribution, unit split or data error. Returns spanning it are invalid.
JUMP_THRESHOLD: dict[AssetClass, float] = {
    AssetClass.LIQUID: 0.03,
    AssetClass.INCOME: 0.05,
    AssetClass.GROWTH: 0.15,
}


@dataclass
class CleanSeries:
    points: list[PricePoint]
    breaks: list[str]


class PriceSeries:
    """Sorted price series with at-or-before lookups."""

    def __init__(self, points: list[PricePoint]) -> None:
        self.points = points
        self._days = [p.day for p in points]

    @property
    def start(self) -> date:
        return self._days[0]

    @property
    def end(self) -> date:
        return self._days[-1]

    @property
    def latest(self) -> PricePoint:
        return self.points[-1]

    def at_or_before(self, day: date, tolerance_days: int = 7) -> PricePoint | None:
        """Price on `day`, or the closest earlier price within `tolerance_days`."""
        index = bisect.bisect_right(self._days, day) - 1
        if index < 0:
            return None
        point = self.points[index]
        return point if (day - point.day).days <= tolerance_days else None

    def window(self, since: date) -> list[PricePoint]:
        return self.points[bisect.bisect_left(self._days, since):]


class SeriesCleaner:
    """Removes one-day spikes that revert, and cuts history at structural breaks."""

    MAX_GLITCH_POINTS = 10  # a bad patch that reverts within this many points is dropped

    @classmethod
    def clean(cls, points: list[PricePoint], threshold: float) -> CleanSeries:
        if len(points) < 3:
            return CleanSeries(points, [])
        kept: list[PricePoint] = [points[0]]
        breaks: list[str] = []
        i = 1
        while i < len(points):
            prev, cur = kept[-1], points[i]
            move = cur.price / prev.price - 1.0
            if abs(move) <= threshold:
                kept.append(cur)
                i += 1
                continue
            revert = next((j for j in range(i + 1, min(i + 1 + cls.MAX_GLITCH_POINTS, len(points)))
                           if abs(points[j].price / prev.price - 1.0) <= threshold / 2), None)
            if revert is not None:
                breaks.append(f"{cur.day}: ignored {revert - i} day(s) of bad prices ({move:+.1%}, then reverted)")
                i = revert
                continue
            breaks.append(f"{cur.day}: price jump {move:+.1%} (distribution/split?) - history before this is excluded")
            kept = [cur]
            i += 1
        return CleanSeries(kept, breaks)


class FundAnalytics:
    """Computes FundMetrics for one fund."""

    def __init__(self, info: FundInfo, points: list[PricePoint],
                 snapshot: FundSnapshot | None, today: date | None = None) -> None:
        cleaned = SeriesCleaner.clean(points, JUMP_THRESHOLD[info.asset_class])
        if not cleaned.points:
            raise ValueError(f"No price history for {info.code}")
        self.info = info
        self.series = PriceSeries(cleaned.points)
        self.breaks = cleaned.breaks
        self.snapshot = snapshot
        self.today = today or date.today()

    # ---- return helpers -------------------------------------------------
    def total_return(self, days: int, end: date | None = None) -> float | None:
        """Absolute % return over `days` calendar days ending at `end`."""
        end_point = self.series.at_or_before(end or self.series.end)
        if end_point is None:
            return None
        start_point = self.series.at_or_before(end_point.day - timedelta(days=days))
        if start_point is None or start_point.day == end_point.day:
            return None
        return (end_point.price / start_point.price - 1.0) * 100.0

    def simple_annualized(self, days: int, end: date | None = None) -> float | None:
        """CAL-calculator style: period return x 365 / actual days."""
        end_point = self.series.at_or_before(end or self.series.end)
        if end_point is None:
            return None
        start_point = self.series.at_or_before(end_point.day - timedelta(days=days))
        if start_point is None or start_point.day == end_point.day:
            return None
        elapsed = (end_point.day - start_point.day).days
        return (end_point.price / start_point.price - 1.0) * 365.0 / elapsed * 100.0

    def cagr(self, years: int) -> float | None:
        end_point = self.series.latest
        start_point = self.series.at_or_before(end_point.day - timedelta(days=round(365.25 * years)))
        if start_point is None:
            return None
        elapsed_years = (end_point.day - start_point.day).days / 365.25
        return ((end_point.price / start_point.price) ** (1.0 / elapsed_years) - 1.0) * 100.0

    def return_ytd(self) -> float | None:
        start = self.series.at_or_before(date(self.series.end.year - 1, 12, 31), tolerance_days=10)
        if start is None:
            return None
        return (self.series.latest.price / start.price - 1.0) * 100.0

    # ---- risk helpers ----------------------------------------------------
    def weekly_prices(self, weeks: int) -> list[float]:
        end = self.series.end
        prices: list[float] = []
        for w in range(weeks, -1, -1):
            point = self.series.at_or_before(end - timedelta(weeks=w))
            if point is None:
                return []  # not enough history for this window
            prices.append(point.price)
        return prices

    def volatility(self, years: int) -> float | None:
        prices = self.weekly_prices(52 * years)
        if len(prices) < 10:
            return None
        log_returns = [math.log(b / a) for a, b in zip(prices, prices[1:])]
        return statistics.stdev(log_returns) * math.sqrt(52) * 100.0

    def drawdowns(self, years: int) -> tuple[float | None, float | None]:
        window = self.series.window(self.series.end - timedelta(days=round(365.25 * years)))
        if len(window) < 2:
            return None, None
        peak, worst = window[0].price, 0.0
        for point in window:
            peak = max(peak, point.price)
            worst = min(worst, point.price / peak - 1.0)
        return worst * 100.0, (window[-1].price / peak - 1.0) * 100.0

    def rolling_one_year(self) -> tuple[float | None, float | None]:
        """Worst rolling 1Y return and share of positive 1Y periods (weekly sampling)."""
        first_end = self.series.start + timedelta(days=365)
        returns: list[float] = []
        day = self.series.end
        while day >= first_end:
            value = self.total_return(365, day)
            if value is not None:
                returns.append(value)
            day -= timedelta(days=7)
        if not returns:
            return None, None
        positive = sum(1 for r in returns if r > 0) / len(returns) * 100.0
        return min(returns), positive

    # ---- assembly --------------------------------------------------------
    def metrics(self, benchmark: "FundAnalytics | None" = None) -> FundMetrics:
        latest = self.series.latest
        accrual_fund = self.info.asset_class != AssetClass.GROWTH
        # Annualising a month of stock-market moves is noise, so equity gets no "yield".
        y30 = self.simple_annualized(30) if accrual_fund else None
        y30_prev = self.simple_annualized(30, latest.day - timedelta(days=90)) if accrual_fund else None
        ret_1y = self.total_return(365)
        cagr_3y = self.cagr(3)
        vol_3y = self.volatility(3)
        max_dd, cur_dd = self.drawdowns(3)
        worst_1y, pct_pos = self.rolling_one_year()

        excess = sharpe = None
        if benchmark is not None and benchmark is not self:
            bench_1y = benchmark.total_return(365)
            if ret_1y is not None and bench_1y is not None:
                excess = ret_1y - bench_1y
            bench_3y = benchmark.cagr(3)
            if cagr_3y is not None and bench_3y is not None and vol_3y:
                sharpe = (cagr_3y - bench_3y) / vol_3y

        snap = self.snapshot
        return FundMetrics(
            code=self.info.code,
            name=self.info.name,
            asset_class=self.info.asset_class.value,
            open_ended=self.info.open_ended,
            latest_date=latest.day.isoformat(),
            latest_price=latest.price,
            history_start=self.series.start.isoformat(),
            history_days=(latest.day - self.series.start).days,
            stale_days=(self.today - latest.day).days,
            aum_lkr=snap.aum_lkr if snap else None,
            price_spread_pct=snap.price_spread_pct if snap else None,
            yield_30d_ann=_r(y30),
            yield_90d_ann=_r(self.simple_annualized(90)) if accrual_fund else None,
            yield_trend_pp=_r(y30 - y30_prev) if y30 is not None and y30_prev is not None else None,
            return_3m=_r(self.total_return(91)),
            return_6m=_r(self.total_return(182)),
            return_ytd=_r(self.return_ytd()),
            return_1y=_r(ret_1y),
            cagr_3y=_r(cagr_3y),
            cagr_5y=_r(self.cagr(5)),
            volatility_1y=_r(self.volatility(1)),
            volatility_3y=_r(vol_3y),
            max_drawdown_3y=_r(max_dd),
            current_drawdown=_r(cur_dd),
            worst_rolling_1y=_r(worst_1y),
            pct_positive_rolling_1y=_r(pct_pos, 1),
            excess_1y_vs_benchmark=_r(excess),
            sharpe_3y=_r(sharpe),
            data_breaks=list(self.breaks),
        )


def _r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)
