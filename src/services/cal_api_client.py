"""Thin client for CAL's public unit-trust rates endpoint."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

logger = logging.getLogger(__name__)


class CalApiError(RuntimeError):
    pass


class CalApiClient:
    """Fetches fund rates for a given value date.

    For `valuedate=D` the API returns, per fund that has a price on D:
      OLD_DATE/OLD_PRICE       -> the price on D (the historical series)
      LATEST_DATE/LATEST_PRICE -> the most recent published price
      PORTFOLIO                -> fund size (LKR)
      RATE_PERIOD              -> window CAL uses for its headline annualised rate
    Funds without a price on D are simply omitted.
    """

    def __init__(self, url: str, action: str, timeout_s: float = 20.0,
                 retries: int = 3, backoff_s: float = 2.0) -> None:
        self._url = url
        self._action = action
        self._timeout_s = timeout_s
        self._retries = retries
        self._backoff_s = backoff_s

    def fetch_rates(self, value_date: date) -> list[dict[str, Any]]:
        params = {"action": self._action, "valuedate": value_date.isoformat()}
        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                response = requests.get(self._url, params=params, timeout=self._timeout_s)
                response.raise_for_status()
                return self._parse(response.json())
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning("CAL API %s attempt %d/%d failed: %s",
                               value_date, attempt, self._retries, exc)
                if attempt < self._retries:
                    time.sleep(self._backoff_s * attempt)
        raise CalApiError(f"CAL API failed for {value_date}: {last_error}")

    @staticmethod
    def _parse(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):  # an empty result comes back as a bare []
            return payload
        if isinstance(payload, dict):
            funds = payload.get("UTMS_FUND", [])
            return funds if isinstance(funds, list) else []
        raise ValueError(f"Unexpected CAL API payload type: {type(payload).__name__}")
