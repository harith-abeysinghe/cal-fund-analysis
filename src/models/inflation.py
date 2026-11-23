"""Sri Lanka consumer-price inflation and fund returns measured against it."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class InflationPeriod:
    """Year-on-year CCPI change for the 12 months ending `period_end`."""

    period_end: date
    label: str
    ccpi_yoy_pct: float
    source: str


@dataclass
class PeriodReturn:
    label: str
    nominal_pct: float
    inflation_pct: float
    real_pct: float  # (1 + nominal) / (1 + inflation) - 1

    @property
    def beat_inflation(self) -> bool:
        return self.real_pct > 0


@dataclass
class FundRealReturns:
    code: str
    periods: list[PeriodReturn] = field(default_factory=list)
    cumulative_nominal_pct: float | None = None
    cumulative_real_pct: float | None = None
    cumulative_since: str | None = None  # first period label in the cumulative figure

    @property
    def years_beaten(self) -> int:
        return sum(1 for p in self.periods if p.beat_inflation)
