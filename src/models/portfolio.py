"""The investor's existing holdings (kept in a git-ignored local file)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentPortfolio:
    as_of: str
    values_lkr: dict[str, float] = field(default_factory=dict)  # fund code -> market value

    @property
    def total_lkr(self) -> float:
        return sum(self.values_lkr.values())

    def is_empty(self) -> bool:
        return self.total_lkr <= 0


@dataclass
class PositionReview:
    code: str
    name: str
    asset_class: str
    value_lkr: float
    weight_pct: float
    yield_30d_ann: float | None
    return_1y: float | None
    rank_in_class: int | None
    peers_in_class: int
    est_annual_income_lkr: float | None
    best_peer_code: str | None
    yield_gap_vs_best_pp: float | None


@dataclass
class PortfolioReview:
    total_lkr: float
    as_of: str
    positions: list[PositionReview]
    class_weights_pct: dict[str, float]
    target_weights_pct: dict[str, float]
    weighted_yield_pct: float | None
    est_annual_income_lkr: float | None
    notes: list[str] = field(default_factory=list)
