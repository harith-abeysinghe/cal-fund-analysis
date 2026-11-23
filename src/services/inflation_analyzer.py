"""Compares each fund's return in every inflation period with Sri Lanka's CCPI inflation."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.models.inflation import FundRealReturns, InflationPeriod, PeriodReturn
from src.services.fund_analytics import FundAnalytics


class InflationStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[InflationPeriod]:
        if not self._path.exists():
            return []
        with self._path.open(newline="", encoding="utf-8") as handle:
            periods = [InflationPeriod(date.fromisoformat(row["period_end"]), row["label"],
                                       float(row["ccpi_yoy_pct"]), row.get("source", ""))
                       for row in csv.DictReader(handle)]
        return sorted(periods, key=lambda p: p.period_end)


class InflationAnalyzer:
    """Real return = (1 + fund return) / (1 + inflation) - 1, period by period.

    Each period is the 12 months ending on the inflation figure's date (calendar
    years end 31 Dec; the latest period ends on the latest CCPI release month),
    so the fund return and the inflation rate cover exactly the same months.
    """

    def __init__(self, periods: list[InflationPeriod]) -> None:
        self._periods = periods

    @property
    def periods(self) -> list[InflationPeriod]:
        return self._periods

    def analyze(self, fund: FundAnalytics) -> FundRealReturns:
        result = FundRealReturns(fund.info.code)
        nominal_growth = real_growth = 1.0
        for period in self._periods:
            start_day = date(period.period_end.year - 1, period.period_end.month, period.period_end.day)
            start = fund.series.at_or_before(start_day, tolerance_days=10)
            end = fund.series.at_or_before(period.period_end, tolerance_days=10)
            if start is None or end is None or start.day < fund.series.start:
                continue
            nominal = end.price / start.price - 1.0
            inflation = period.ccpi_yoy_pct / 100.0
            real = (1.0 + nominal) / (1.0 + inflation) - 1.0
            result.periods.append(PeriodReturn(period.label, round(nominal * 100, 2),
                                               period.ccpi_yoy_pct, round(real * 100, 2)))
            # Cumulative over consecutive calendar years only (a trailing 12-month
            # period overlaps the last calendar year, so it is excluded).
            if period.period_end.month == 12:
                result.cumulative_since = result.cumulative_since or period.label
                nominal_growth *= 1.0 + nominal
                real_growth *= 1.0 + real
        if result.cumulative_since:
            result.cumulative_nominal_pct = round((nominal_growth - 1.0) * 100, 1)
            result.cumulative_real_pct = round((real_growth - 1.0) * 100, 1)
        return result
