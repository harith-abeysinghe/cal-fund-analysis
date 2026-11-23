"""Builds and maintains the daily unit-price history from the CAL API."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from src.models.fund import FundSnapshot
from src.services.cal_api_client import CalApiClient, CalApiError
from src.services.nav_history_store import NavHistoryStore, SnapshotStore

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    days_requested: int = 0
    prices_changed: int = 0
    failed_days: list[date] = field(default_factory=list)
    unknown_codes: set[str] = field(default_factory=set)
    snapshots: list[FundSnapshot] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.days_requested > 0 and len(self.failed_days) < self.days_requested


class NavCollector:
    def __init__(self, client: CalApiClient, store: NavHistoryStore,
                 snapshot_store: SnapshotStore, known_codes: set[str],
                 workers: int = 4) -> None:
        self._client = client
        self._store = store
        self._snapshot_store = snapshot_store
        self._known_codes = known_codes
        self._workers = max(1, workers)

    def update(self, lookback_days: int, today: date | None = None) -> CollectionResult:
        """Fill everything from shortly before the last stored day up to today."""
        today = today or date.today()
        last = self._store.last_date()
        start = (last - timedelta(days=lookback_days)) if last else today - timedelta(days=400)
        return self.collect(start, today)

    def backfill(self, since: date, until: date | None = None, step_days: int = 1) -> CollectionResult:
        return self.collect(since, until or date.today(), step_days)

    def collect(self, start: date, end: date, step_days: int = 1) -> CollectionResult:
        days = [start + timedelta(days=i) for i in range(0, (end - start).days + 1, step_days)]
        result = CollectionResult(days_requested=len(days))
        latest_records: list[dict[str, Any]] = []
        latest_records_day: date | None = None

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {pool.submit(self._client.fetch_rates, day): day for day in days}
            for done, future in enumerate(as_completed(futures), 1):
                day = futures[future]
                try:
                    records = future.result()
                except CalApiError as exc:
                    logger.error("%s", exc)
                    result.failed_days.append(day)
                    continue
                result.prices_changed += self._ingest(day, records, result)
                # The response with the most funds (ties -> latest day) carries
                # the freshest AUM / latest-price fields for the snapshot.
                if records and (latest_records_day is None
                                or (len(records), day) > (len(latest_records), latest_records_day)):
                    latest_records, latest_records_day = records, day
                if done % 250 == 0:
                    logger.info("  %d/%d days fetched", done, len(days))
                    self._store.save()  # checkpoint long backfills

        self._store.save()
        if latest_records:
            result.snapshots = self._build_snapshots(latest_records)
            self._snapshot_store.save(result.snapshots)
        result.failed_days.sort()
        return result

    def _ingest(self, day: date, records: list[dict[str, Any]], result: CollectionResult) -> int:
        changed = 0
        for record in records:
            code = str(record.get("FUND", "")).strip()
            if code not in self._known_codes:
                if code:
                    result.unknown_codes.add(code)
                continue
            # The API omits funds with no price on `day`; guard anyway.
            if str(record.get("OLD_DATE", "")) != day.isoformat():
                continue
            try:
                price = float(record.get("OLD_PRICE", 0))
            except (TypeError, ValueError):
                continue
            changed += self._store.upsert(code, day, price)
        return changed

    def _build_snapshots(self, records: list[dict[str, Any]]) -> list[FundSnapshot]:
        snapshots: list[FundSnapshot] = []
        for record in records:
            code = str(record.get("FUND", "")).strip()
            if code not in self._known_codes:
                continue
            try:
                latest_date = str(record["LATEST_DATE"])
                snapshots.append(FundSnapshot(
                    code=code,
                    api_name=str(record.get("FUND_NAME", code)).strip(),
                    latest_date=latest_date,
                    latest_price=float(record["LATEST_PRICE"]),
                    series_price=self._store.price_on(code, date.fromisoformat(latest_date)),
                    aum_lkr=float(record.get("PORTFOLIO") or 0),
                    rate_period_days=int(record.get("RATE_PERIOD") or 30),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping snapshot for %s: %s", code, exc)
        return snapshots
