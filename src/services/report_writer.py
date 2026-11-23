"""Writes analysis.json (for the dashboard), analysis.csv and a readable report."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.config.settings import RiskProfile
from src.models.fund import AssetClass, FundMetrics
from src.models.inflation import FundRealReturns, InflationPeriod
from src.models.portfolio import PortfolioReview
from src.services.market_context import MarketContext
from src.services.portfolio_planner import Plan

DISCLAIMER = (
    "This is a screening tool built on CAL's published unit prices, not personal "
    "investment advice. Past returns do not predict future returns. Check the fund "
    "fact sheets for fees, exit loads, tax (10% WHT on realised interest) and liquidity "
    "terms, and consider a licensed adviser before investing."
)

CLASS_LABEL = {
    AssetClass.LIQUID.value: "Money market / liquidity",
    AssetClass.INCOME.value: "Fixed income",
    AssetClass.GROWTH.value: "Equity / balanced",
}


class ReportWriter:
    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir

    def write(self, metrics: list[FundMetrics], plan: Plan, profile: RiskProfile,
              benchmark_code: str, insights: list[str], review: PortfolioReview | None = None,
              real: dict[str, FundRealReturns] | None = None,
              inflation: list[InflationPeriod] | None = None,
              market: MarketContext | None = None) -> str:
        real = real or {}
        inflation = inflation or []
        self._dir.mkdir(parents=True, exist_ok=True)
        ordered = sorted(metrics, key=lambda m: (m.asset_class, m.rank_in_class or 99, m.code))
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": 2,
            "budget_lkr": plan.budget_lkr,
            "risk_profile": profile.name,
            "risk_profile_description": profile.description,
            "risk_profile_weights": {k.value: v for k, v in profile.weights.items()},
            "benchmark": benchmark_code,
            "recommended_funds": [h.name for h in plan.holdings],
            "holdings": [asdict(h) for h in plan.holdings],
            "projections": [{**asdict(p), "gain_lkr": p.gain_lkr} for p in plan.projections],
            "insights": insights,
            "notes": plan.notes,
            "starting_value_lkr": plan.starting_value_lkr,
            "current_portfolio": asdict(review) if review else None,
            "inflation": [{**asdict(i), "period_end": i.period_end.isoformat()} for i in inflation],
            "market_context": asdict(market) if market else None,
            "real_returns": {code: {**asdict(r), "years_beaten": r.years_beaten} for code, r in real.items()},
            "disclaimer": DISCLAIMER,
            "funds": [asdict(m) for m in ordered],
        }
        (self._dir / "analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        with (self._dir / "analysis.csv").open("w", newline="", encoding="utf-8") as handle:
            rows = [{**asdict(m), "data_breaks": " | ".join(m.data_breaks),
                     "eligibility_notes": " | ".join(m.eligibility_notes)} for m in ordered]
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        text = self._render_text(ordered, plan, profile, benchmark_code, insights, review, real, inflation, market)
        (self._dir / "analysis_report.txt").write_text(text, encoding="utf-8")
        return text

    @staticmethod
    def _render_text(metrics: list[FundMetrics], plan: Plan, profile: RiskProfile,
                     benchmark_code: str, insights: list[str],
                     review: PortfolioReview | None, real: dict[str, FundRealReturns],
                     inflation: list[InflationPeriod], market: MarketContext | None) -> str:
        latest = max((m.latest_date for m in metrics), default="-")
        lines = [
            f"CAL Unit Trust Analysis | prices to {latest} | budget LKR {plan.budget_lkr:,}/month "
            f"| profile: {profile.name}",
            f"Profile: {profile.description}  Split: "
            + ", ".join(f"{CLASS_LABEL[c.value]} {w:.0%}" for c, w in profile.weights.items()),
        ]
        if review:
            lines += ["", f"YOUR CURRENT PORTFOLIO (as of {review.as_of or '-'}): LKR {review.total_lkr:,.2f}"]
            for p in review.positions:
                rank = (f"#{p.rank_in_class}/{p.peers_in_class} in {p.asset_class}"
                        if p.rank_in_class else f"not ranked ({p.asset_class})")
                lines.append(f"  {p.code:<6} LKR {p.value_lkr:>12,.2f} {p.weight_pct:>5.1f}%  "
                             f"30d {_p(p.yield_30d_ann):>7}  1Y {_p(p.return_1y):>7}  {rank}")
            lines.append("  Mix now: " + ", ".join(f"{CLASS_LABEL[c]} {v:.0f}%"
                                                  for c, v in review.class_weights_pct.items())
                         + "  | target: " + ", ".join(f"{CLASS_LABEL[c]} {v:.0f}%"
                                                      for c, v in review.target_weights_pct.items()))
            if review.weighted_yield_pct is not None:
                lines.append(f"  Blended running yield {review.weighted_yield_pct:.2f}% "
                             f"~ LKR {review.est_annual_income_lkr:,}/year before tax at today's rates")
            lines += [f"  - {n}" for n in review.notes]
        lines += ["", "SUGGESTED ALLOCATION OF THIS MONTH'S BUDGET"]
        for h in plan.holdings:
            lines.append(f"  {h.code:<6} {h.name:<44} LKR {h.allocation_lkr:>9,}  ({h.weight_pct:.0f}%)")
        lines.append(f"  {'':<6} {'Total':<44} LKR {sum(h.allocation_lkr for h in plan.holdings):>9,}")
        lines += [f"  note: {n}" for n in plan.notes]

        if plan.projections:
            p0 = plan.projections[0]
            start = (f"LKR {plan.starting_value_lkr:,.0f} held now + " if plan.starting_value_lkr else "")
            lines += ["", f"ILLUSTRATIVE VALUE AFTER {p0.years} YEARS ({start}LKR {plan.budget_lkr:,}/month "
                          "invested as above; after buy/sell spread, before tax)"]
            for p in plan.projections:
                lines.append(f"  {p.scenario:<36} {p.annual_return_pct:>6.2f}%/yr -> LKR "
                             f"{p.projected_value_lkr:>12,}  (gain {p.gain_lkr:,})")

        if insights:
            lines += ["", "WHAT THE DATA SAYS"] + [f"  - {i}" for i in insights]

        header = (f"  {'Code':<6} {'Score':>5} {'30d ann':>8} {'1Y':>7} {'3Y CAGR':>8} {'5Y CAGR':>8} "
                  f"{'Vol 1Y':>7} {'MaxDD 3Y':>9} {'Worst 1Y':>9} {'vs MMF':>7} {'AUM LKR':>9}  Status")
        for asset_class in (AssetClass.LIQUID, AssetClass.INCOME, AssetClass.GROWTH):
            group = [m for m in metrics if m.asset_class == asset_class.value]
            if not group:
                continue
            lines += ["", f"{CLASS_LABEL[asset_class.value].upper()} (scored against each other only)", header]
            for m in group:
                status = (f"#{m.rank_in_class}" if m.eligible else "excluded: " + "; ".join(m.eligibility_notes))
                if m.allocation_lkr:
                    status += f"  -> LKR {m.allocation_lkr:,}"
                lines.append(
                    f"  {m.code:<6} {_f(m.score, 1):>5} {_p(m.yield_30d_ann):>8} {_p(m.return_1y):>7} "
                    f"{_p(m.cagr_3y):>8} {_p(m.cagr_5y):>8} {_p(m.volatility_1y):>7} "
                    f"{_p(m.max_drawdown_3y):>9} {_p(m.worst_rolling_1y):>9} "
                    f"{_p(m.excess_1y_vs_benchmark):>7} {_aum(m.aum_lkr):>9}  {status}")

        lines += ReportWriter._render_real(metrics, review, real, inflation)
        lines += ReportWriter._render_market(market)

        breaks = [(m.code, b) for m in metrics for b in m.data_breaks]
        if breaks:
            lines += ["", "DATA QUALITY"] + [f"  {code}: {b}" for code, b in breaks]

        lines += [
            "",
            "Definitions: '30d ann' = last-30-day return x 365/30 (same method as CAL's calculator); "
            "1Y = exact 365-day return; CAGR = compound annual growth; Vol = annualised std-dev of "
            "weekly returns; MaxDD = worst peak-to-trough fall; Worst 1Y = worst rolling 1-year return "
            f"in the history; vs MMF = 1Y return minus {benchmark_code} (money market) 1Y return.",
            "",
            DISCLAIMER,
        ]
        return "\n".join(lines) + "\n"


    @staticmethod
    def _render_real(metrics: list[FundMetrics], review: PortfolioReview | None,
                     real: dict[str, FundRealReturns], inflation: list[InflationPeriod]) -> list[str]:
        if not real or not inflation:
            return []
        held = {p.code for p in review.positions} if review else set()
        codes = [m.code for m in metrics if (m.eligible or m.code in held) and real.get(m.code)
                 and real[m.code].periods]
        if not codes:
            return []
        lines = ["", "RETURNS AFTER SRI LANKA INFLATION (real return = fund return adjusted for CCPI, "
                     "same 12 months; * = you hold it)",
                 f"  {'Period':<16} {'CCPI':>7} " + " ".join(f"{c + ('*' if c in held else ''):>7}" for c in codes)]
        for period in inflation:
            cells = []
            for code in codes:
                match = next((p for p in real[code].periods if p.label == period.label), None)
                cells.append(f"{match.real_pct:>+7.1f}" if match else f"{'':>7}")
            lines.append(f"  {period.label:<16} {period.ccpi_yoy_pct:>6.1f}% " + " ".join(cells))
        beat = []
        for code in codes:
            full = [p for p in real[code].periods if p.label.isdigit()]
            beat.append(f"{sum(p.beat_inflation for p in full)}/{len(full)}" if full else "-")
        lines.append(f"  {'Years beaten':<16} {'':>7} " + " ".join(f"{b:>7}" for b in beat))
        lines.append(f"  {'Cumul. real':<16} {'':>7} " + " ".join(
            f"{real[c].cumulative_real_pct:>+6.0f}%" if real[c].cumulative_real_pct is not None else f"{'-':>7}"
            for c in codes))
        lines.append("  Cumul. real = total inflation-adjusted growth over every full calendar year the fund "
                     "has clean history for (start year differs by fund).")
        return lines


    @staticmethod
    def _render_market(market: MarketContext | None) -> list[str]:
        if not market:
            return []
        labels = {"policy_rate_opr": "Policy rate (OPR)", "tbill_91d": "3-month T-bill",
                  "tbill_182d": "6-month T-bill", "tbill_364d": "12-month T-bill",
                  "fd_12m_avg": "12-month FD (avg)"}
        lines = ["", "INTEREST RATES & ALTERNATIVES (data/market_indicators.csv - update when rates change)"]
        for key, label in labels.items():
            if key in market.rates:
                r = market.rates[key]
                lines.append(f"  {label:<20} {r['value']:>6.2f}%   as of {r['date']}")
        if market.rate_comparisons:
            lines.append(f"  {'Fund':<6} {'30d ann':>8} {'vs T-bill':>10} {'vs FD':>8}")
            for c in market.rate_comparisons:
                lines.append(f"  {c.code:<6} {c.yield_30d_ann:>7.2f}% {_pp(c.vs_tbill_364d_pp):>10} "
                             f"{_pp(c.vs_fd_12m_pp):>8}")
        if market.equity_vs_index and market.index_latest:
            lines += ["", f"EQUITY FUNDS VS CSE ASPI (index {market.index_latest['value']:,.2f} "
                          f"on {market.index_latest['date']})"]
            for e in market.equity_vs_index:
                beta = "-" if e.beta is None else e.beta
                corr = "-" if e.correlation is None else e.correlation
                lines.append(f"  {e.code:<6} since {e.since}: fund {e.fund_return_pct:+.2f}%  "
                             f"ASPI {e.index_return_pct:+.2f}%  beta {beta}  corr {corr}")
        if market.usd_returns:
            lines += ["", "IN US DOLLAR TERMS (fund return adjusted for the rupee's move vs USD)"]
            for u in market.usd_returns:
                lines.append(f"  {u.code:<6} {u.label:<16} LKR {u.lkr_return_pct:+6.2f}%  "
                             f"rupee {u.lkr_vs_usd_pct:+6.2f}%  -> USD {u.usd_return_pct:+6.2f}%")
        return lines


def _pp(value: float | None) -> str:
    return "-" if value is None else f"{value:+.2f}pp"


def _p(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def _f(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _aum(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value / 1e9:.1f}B" if value >= 1e9 else f"{value / 1e6:.0f}M"
