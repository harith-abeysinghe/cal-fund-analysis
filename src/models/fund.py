"""Domain models shared by the collector, analytics and planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class AssetClass(str, Enum):
    LIQUID = "liquid"   # money market / treasury: near-cash, lowest risk
    INCOME = "income"   # fixed income: bonds, deposits, gilts
    GROWTH = "growth"   # equity / balanced: volatile, higher long-run return


@dataclass(frozen=True)
class FundInfo:
    code: str
    name: str
    asset_class: AssetClass
    open_ended: bool = True
    shariah: bool = False


@dataclass(frozen=True)
class FundSnapshot:
    """Latest point-in-time facts from the API that are not part of the price series."""

    code: str
    api_name: str
    latest_date: str
    latest_price: float
    series_price: float | None  # historical-series price on latest_date, if known
    aum_lkr: float
    rate_period_days: int

    @property
    def price_spread_pct(self) -> float | None:
        """Gap between the two published prices on the same day.

        For equity/balanced funds CAL's historical series runs ~2% above the
        'latest' price, consistent with a buy/sell (creation/redemption) spread.
        """
        if not self.series_price or not self.latest_price:
            return None
        return round((self.series_price / self.latest_price - 1.0) * 100.0, 4)


@dataclass
class FundMetrics:
    code: str
    name: str
    asset_class: str
    open_ended: bool
    latest_date: str
    latest_price: float
    history_start: str
    history_days: int
    stale_days: int
    aum_lkr: float | None
    price_spread_pct: float | None
    # Returns (percent). Short windows are simple-annualized the way CAL's
    # calculator shows them; long windows are compound annual growth rates.
    yield_30d_ann: float | None
    yield_90d_ann: float | None
    yield_trend_pp: float | None  # 30d yield now minus 30d yield 90 days ago
    return_3m: float | None
    return_6m: float | None
    return_ytd: float | None
    return_1y: float | None
    cagr_3y: float | None
    cagr_5y: float | None
    # Risk
    volatility_1y: float | None
    volatility_3y: float | None
    max_drawdown_3y: float | None
    current_drawdown: float | None
    worst_rolling_1y: float | None
    pct_positive_rolling_1y: float | None
    excess_1y_vs_benchmark: float | None
    sharpe_3y: float | None
    data_breaks: list[str] = field(default_factory=list)
    # Filled by the planner
    eligible: bool = False
    eligibility_notes: list[str] = field(default_factory=list)
    score: float | None = None
    rank_in_class: int | None = None
    allocation_lkr: int = 0


@dataclass(frozen=True)
class PricePoint:
    day: date
    price: float
