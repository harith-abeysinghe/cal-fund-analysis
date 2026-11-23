"""Eligibility, peer scoring and risk-profile allocation of a monthly budget."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.config.settings import EligibilityRules, RiskProfile
from src.models.fund import AssetClass, FundMetrics
from src.models.portfolio import CurrentPortfolio, PortfolioReview, PositionReview

# (metric attribute, weight, higher_is_better). Scored only against peers in
# the same asset class: an equity fund is never ranked against a bond fund.
SCORING: dict[AssetClass, list[tuple[str, float, bool]]] = {
    AssetClass.LIQUID: [
        ("yield_30d_ann", 0.45, True),   # running yield ~ next-month return for accrual funds
        ("return_1y", 0.35, True),
        ("volatility_1y", 0.20, False),
    ],
    AssetClass.INCOME: [
        ("yield_30d_ann", 0.30, True),
        ("return_1y", 0.25, True),
        ("cagr_3y", 0.15, True),
        ("worst_rolling_1y", 0.15, True),
        ("volatility_1y", 0.15, False),
    ],
    AssetClass.GROWTH: [
        ("cagr_3y", 0.25, True),
        ("cagr_5y", 0.15, True),
        ("sharpe_3y", 0.25, True),
        ("max_drawdown_3y", 0.20, True),   # less negative is better
        ("return_1y", 0.15, True),
    ],
}


@dataclass
class Holding:
    code: str
    name: str
    asset_class: str
    allocation_lkr: int
    weight_pct: float


@dataclass
class Projection:
    scenario: str
    annual_return_pct: float
    years: int
    contributed_lkr: int
    projected_value_lkr: int

    @property
    def gain_lkr(self) -> int:
        return self.projected_value_lkr - self.contributed_lkr


@dataclass
class Plan:
    profile: str
    budget_lkr: int
    holdings: list[Holding]
    projections: list[Projection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    starting_value_lkr: float = 0.0


class PortfolioPlanner:
    def __init__(self, rules: EligibilityRules, funds_per_class: dict[AssetClass, int]) -> None:
        self._rules = rules
        self._funds_per_class = funds_per_class

    # ---- eligibility & scoring ------------------------------------------
    def assess(self, metrics: list[FundMetrics]) -> None:
        for m in metrics:
            notes: list[str] = []
            if not m.open_ended:
                notes.append("closed-end fund (not available on demand)")
            if m.aum_lkr is not None and m.aum_lkr < self._rules.min_aum_lkr:
                notes.append(f"small fund: AUM LKR {m.aum_lkr / 1e6:,.1f}M")
            if m.stale_days > self._rules.max_stale_days:
                notes.append(f"price stale for {m.stale_days} days")
            if m.history_days < self._rules.min_history_days:
                notes.append(f"only {m.history_days} days of clean history")
            if m.return_1y is None:
                notes.append("no 1-year return")
            m.eligibility_notes = notes
            m.eligible = not notes

        for asset_class, rules in SCORING.items():
            peers = [m for m in metrics if m.asset_class == asset_class.value and m.eligible]
            self._score(peers, rules)
            for rank, m in enumerate(sorted(peers, key=lambda x: x.score or 0, reverse=True), 1):
                m.rank_in_class = rank

    @staticmethod
    def _score(peers: list[FundMetrics], rules: list[tuple[str, float, bool]]) -> None:
        for m in peers:
            m.score = 0.0
        for attr, weight, higher_better in rules:
            values = [getattr(m, attr) for m in peers if getattr(m, attr) is not None]
            low, high = (min(values), max(values)) if values else (0.0, 0.0)
            for m in peers:
                value = getattr(m, attr)
                if value is None or math.isclose(low, high):
                    norm = 0.5  # missing or no dispersion -> neutral
                else:
                    norm = (value - low) / (high - low)
                    norm = norm if higher_better else 1.0 - norm
                m.score += 100.0 * weight * norm
        for m in peers:
            m.score = round(m.score, 1)

    # ---- current holdings ---------------------------------------------------
    @staticmethod
    def review(metrics: list[FundMetrics], current: CurrentPortfolio, profile: RiskProfile) -> PortfolioReview:
        by_code = {m.code: m for m in metrics}
        total = current.total_lkr
        positions: list[PositionReview] = []
        class_values: dict[str, float] = {c.value: 0.0 for c in AssetClass}
        income_sum, income_known = 0.0, True
        for code, value in sorted(current.values_lkr.items(), key=lambda kv: -kv[1]):
            m = by_code.get(code)
            if m is None:
                continue
            class_values[m.asset_class] += value
            peers = [p for p in metrics if p.asset_class == m.asset_class and p.eligible]
            best = min(peers, key=lambda p: p.rank_in_class or 99) if peers else None
            rate = (m.cagr_3y if m.asset_class == AssetClass.GROWTH.value else m.yield_30d_ann)
            income = value * rate / 100.0 if rate is not None else None
            if income is None:
                income_known = False
            else:
                income_sum += income
            gap = (m.yield_30d_ann - best.yield_30d_ann
                   if best and best.code != m.code and m.yield_30d_ann is not None
                   and best.yield_30d_ann is not None else None)
            positions.append(PositionReview(
                code, m.name, m.asset_class, round(value, 2), round(value / total * 100.0, 1),
                m.yield_30d_ann, m.return_1y, m.rank_in_class, len(peers),
                None if income is None else round(income), best.code if best else None,
                None if gap is None else round(gap, 2)))

        notes: list[str] = []
        for p in positions:
            if p.yield_gap_vs_best_pp is not None and p.yield_gap_vs_best_pp < -0.25:
                extra = p.value_lkr * -p.yield_gap_vs_best_pp / 100.0
                notes.append(
                    f"{p.code} is running {abs(p.yield_gap_vs_best_pp):.2f} pp below {p.best_peer_code} "
                    f"(the top-ranked {p.asset_class} fund) - about LKR {extra:,.0f}/year on your "
                    f"LKR {p.value_lkr:,.0f}. A lower yield can reflect a shorter, lower-risk portfolio; "
                    "compare the fact sheets before switching.")
        targets = {c.value: round(w * 100.0, 1) for c, w in profile.weights.items()}
        actual = {c: round(v / total * 100.0, 1) for c, v in class_values.items()}
        for c, target in targets.items():
            if abs(actual.get(c, 0.0) - target) >= 5:
                notes.append(f"{c} is {actual.get(c, 0.0):.0f}% of your portfolio vs {target:.0f}% "
                             f"target for the {profile.name} profile.")
        weighted = income_sum / total * 100.0 if income_known and total else None
        return PortfolioReview(round(total, 2), current.as_of, positions, actual, targets,
                               None if weighted is None else round(weighted, 2),
                               round(income_sum) if income_known else None, notes)

    # ---- allocation -------------------------------------------------------
    def allocate(self, metrics: list[FundMetrics], profile: RiskProfile, budget: int,
                 current: CurrentPortfolio | None = None) -> Plan:
        """Split `budget` across the profile's classes. With `current` holdings,
        new money is steered toward classes that are below target (no selling)."""
        notes: list[str] = []
        picks: dict[AssetClass, list[FundMetrics]] = {}
        for asset_class, weight in profile.weights.items():
            if weight <= 0:
                continue
            ranked = sorted((m for m in metrics if m.asset_class == asset_class.value and m.eligible),
                            key=lambda m: m.score or 0, reverse=True)
            chosen = ranked[: self._funds_per_class.get(asset_class, 1)]
            if chosen:
                picks[asset_class] = chosen
            else:
                notes.append(f"No eligible {asset_class.value} fund; its {weight:.0%} share moved to other classes.")

        class_weight_total = sum(profile.weights[c] for c in picks)
        if not picks or class_weight_total <= 0:
            return Plan(profile.name, budget, [], notes=notes + ["No eligible funds to allocate."])

        class_share = {c: profile.weights[c] / class_weight_total for c in picks}
        if current is not None and not current.is_empty():
            by_code = {m.code: m for m in metrics}
            held = {c: 0.0 for c in AssetClass}
            for code, value in current.values_lkr.items():
                if code in by_code:
                    held[AssetClass(by_code[code].asset_class)] += value
            total_after = current.total_lkr + budget
            gaps = {c: max(class_share[c] * total_after - held[c], 0.0) for c in picks}
            if sum(gaps.values()) > 0:
                class_share = {c: g / sum(gaps.values()) for c, g in gaps.items()}
                notes.append("New money is directed to the asset classes furthest below target, "
                             "so your existing holdings are rebalanced without selling anything.")

        fund_weights: list[tuple[FundMetrics, float]] = []
        for asset_class, chosen in picks.items():
            share = class_share[asset_class]
            if share > 0:
                fund_weights += [(m, share / len(chosen)) for m in chosen]

        unit = 1000 if budget >= 10_000 else 100
        amounts = [int(budget * w // unit) * unit for _, w in fund_weights]
        remainder = budget - sum(amounts)
        order = sorted(range(len(fund_weights)), key=lambda i: fund_weights[i][1], reverse=True)
        i = 0
        while remainder >= unit:
            amounts[order[i % len(order)]] += unit
            remainder -= unit
            i += 1
        if remainder:
            amounts[order[0]] += remainder

        holdings = []
        for (m, _), amount in zip(fund_weights, amounts):
            m.allocation_lkr = amount
            holdings.append(Holding(m.code, m.name, m.asset_class, amount,
                                    round(amount / budget * 100.0, 1)))
        return Plan(profile.name, budget, holdings, notes=notes)

    # ---- projection -------------------------------------------------------
    def project(self, plan: Plan, metrics: list[FundMetrics], years: int,
                current: CurrentPortfolio | None = None, equity_base_pct: float | None = None) -> None:
        """Future value of existing holdings plus investing the plan every month,
        under three backward-looking scenarios. Illustrations, not forecasts."""
        if not plan.holdings:
            return
        by_code = {m.code: m for m in metrics}
        existing = {c: v for c, v in (current.values_lkr.items() if current else []) if c in by_code}
        plan.starting_value_lkr = round(sum(existing.values()), 2)
        # Equity has no "running yield"; in the base case assume it earns the risk-free
        # rate plus a modest premium instead of extrapolating a post-crisis rebound.
        risk_free = equity_base_pct if equity_base_pct is not None else 10.0
        scenarios = {
            f"Today's yields (equity {risk_free:.1f}%)": lambda m: risk_free
            if m.asset_class == AssetClass.GROWTH.value else (m.yield_30d_ann or m.return_1y),
            "Repeat of the last 1 year": lambda m: m.return_1y,
            "Repeat of the last 3 years (CAGR)": lambda m: m.cagr_3y if m.cagr_3y is not None else m.return_1y,
        }
        months = years * 12
        for label, rate_of in scenarios.items():
            future_value, weighted_rate = 0.0, 0.0
            for h in plan.holdings:
                m = by_code[h.code]
                rate = rate_of(m) or 0.0
                weighted_rate += rate * h.weight_pct / 100.0
                entry_cost = max(m.price_spread_pct or 0.0, 0.0) / 100.0
                monthly = (1.0 + rate / 100.0) ** (1.0 / 12.0) - 1.0
                net_contribution = h.allocation_lkr * (1.0 - entry_cost)
                future_value += sum(net_contribution * (1.0 + monthly) ** (months - k)
                                    for k in range(months))
            for code, value in existing.items():
                rate = rate_of(by_code[code]) or 0.0
                future_value += value * (1.0 + rate / 100.0) ** years
            plan.projections.append(Projection(
                label, round(weighted_rate, 2), years,
                round(plan.budget_lkr * months + plan.starting_value_lkr), round(future_value)))
