"""Persistence for the daily unit-price history and the latest fund snapshot."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from src.models.fund import FundSnapshot, PricePoint


class NavHistoryStore:
    """Long-format CSV `date,fund,price` - one row per fund per priced day."""

    HEADER = ("date", "fund", "price")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._prices: dict[str, dict[date, float]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    day = date.fromisoformat(row["date"])
                    price = float(row["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    self._prices.setdefault(row["fund"], {})[day] = price

    def upsert(self, code: str, day: date, price: float) -> bool:
        """Insert or correct a price. Returns True when stored data changed."""
        if price <= 0:
            return False
        series = self._prices.setdefault(code, {})
        if series.get(day) == price:
            return False
        series[day] = price
        self._dirty = True
        return True

    def save(self) -> None:
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        rows = sorted((day, code, price) for code, series in self._prices.items()
                      for day, price in series.items())
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(self.HEADER)
            for day, code, price in rows:
                writer.writerow((day.isoformat(), code, f"{price:.4f}"))
        tmp.replace(self._path)
        self._dirty = False

    def codes(self) -> list[str]:
        return sorted(self._prices)

    def series(self, code: str) -> list[PricePoint]:
        return [PricePoint(day, price) for day, price in sorted(self._prices.get(code, {}).items())]

    def last_date(self) -> date | None:
        days = [max(series) for series in self._prices.values() if series]
        return max(days) if days else None

    def price_on(self, code: str, day: date) -> float | None:
        return self._prices.get(code, {}).get(day)


class SnapshotStore:
    """JSON file holding the latest FundSnapshot per fund."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, snapshots: list[FundSnapshot]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {s.code: {**asdict(s), "price_spread_pct": s.price_spread_pct}
                   for s in sorted(snapshots, key=lambda s: s.code)}
        self._path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def load(self) -> dict[str, FundSnapshot]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        fields = set(FundSnapshot.__dataclass_fields__)
        return {code: FundSnapshot(**{k: v for k, v in item.items() if k in fields})
                for code, item in raw.items()}
