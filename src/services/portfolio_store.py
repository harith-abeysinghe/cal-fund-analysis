"""Loads the investor's current holdings from a local JSON file that is never committed.

Format (see portfolio.example.json):
    {"as_of": "YYYY-MM-DD", "holdings": {"CAHYF": 100000.00, "IF": 50000.00}}
Keys are CAL fund codes; values are current market values in LKR.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.models.portfolio import CurrentPortfolio

logger = logging.getLogger(__name__)


class PortfolioStore:
    def __init__(self, path: Path, known_codes: set[str]) -> None:
        self._path = path
        self._known_codes = known_codes

    def load(self) -> CurrentPortfolio | None:
        if not self._path.exists():
            return None
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        values: dict[str, float] = {}
        for code, value in (raw.get("holdings") or {}).items():
            code = str(code).strip().upper()
            if code not in self._known_codes:
                logger.warning("Ignoring unknown fund code in %s: %s", self._path.name, code)
                continue
            values[code] = values.get(code, 0.0) + float(value)
        portfolio = CurrentPortfolio(as_of=str(raw.get("as_of", "")), values_lkr=values)
        return None if portfolio.is_empty() else portfolio
