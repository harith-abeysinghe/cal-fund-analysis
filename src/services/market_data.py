"""Market drivers of unit prices: the CSE All Share Price Index (collected daily)
and hand-maintained interest-rate / exchange-rate reference points."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from src.models.fund import PricePoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Indicator:
    day: date
    name: str
    value: float
    note: str
    source: str


class CseIndexClient:
    """CSE public chart endpoint. period=5 returns roughly the last 12 months of daily closes,
    so history accumulates locally from the first run onward."""

    def __init__(self, url: str, chart_id: int = 1, timeout_s: float = 20.0) -> None:
        self._url = url
        self._chart_id = chart_id
        self._timeout_s = timeout_s

    def fetch_last_year(self) -> list[PricePoint]:
        response = requests.post(self._url, data={"chartId": self._chart_id, "period": 5},
                                 timeout=self._timeout_s)
        response.raise_for_status()
        by_day: dict[date, float] = {}
        for row in response.json():
            day = datetime.fromtimestamp(row["d"] / 1000, tz=timezone.utc).date()
            by_day[day] = float(row["v"])  # last value of the day wins
        return [PricePoint(d, v) for d, v in sorted(by_day.items()) if v > 0]


class IndexHistoryStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._values: dict[date, float] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    self._values[date.fromisoformat(row["date"])] = float(row["value"])

    def merge(self, points: list[PricePoint]) -> int:
        changed = 0
        for p in points:
            if self._values.get(p.day) != p.price:
                self._values[p.day] = p.price
                changed += 1
        if changed:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(("date", "value"))
                for d, v in sorted(self._values.items()):
                    writer.writerow((d.isoformat(), f"{v:.2f}"))
        return changed

    def series(self) -> list[PricePoint]:
        return [PricePoint(d, v) for d, v in sorted(self._values.items())]


class IndicatorStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[Indicator]:
        if not self._path.exists():
            return []
        with self._path.open(newline="", encoding="utf-8") as handle:
            return [Indicator(date.fromisoformat(r["date"]), r["indicator"], float(r["value"]),
                              r.get("note", ""), r.get("source", ""))
                    for r in csv.DictReader(handle)]

    @staticmethod
    def latest(indicators: list[Indicator], name: str) -> Indicator | None:
        matches = [i for i in indicators if i.name == name]
        return max(matches, key=lambda i: i.day) if matches else None
