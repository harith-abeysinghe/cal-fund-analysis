#!/usr/bin/env python3
"""Rank the unit trusts in data/ and build a monthly LKR allocation.

The input files contain point-in-time prices and return observations.  This
script is deliberately heuristic: it ranks observed performance and
consistency; it does not predict future returns or replace a licensed adviser.

Examples:
    python analyze.py
    python analyze.py --budget 90000 --risk-profile conservative
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


EXPECTED_COLUMNS = {
    "scraped_date", "old_date", "old_price", "new_date", "new_price",
    "price_difference", "price_growth",
}

RISK_PROFILES = {
    "conservative": {"Quantitative Equity Fund": 0.10, "High Yield Fund": 0.15,
                     "Investment Grade Fund": 0.30, "CAL Income Fund": 0.25,
                     "Capital Alliance Gilt Fund": 0.20},
    "balanced": {"Quantitative Equity Fund": 0.20, "High Yield Fund": 0.20,
                 "Investment Grade Fund": 0.25, "CAL Income Fund": 0.20,
                 "Capital Alliance Gilt Fund": 0.15},
    "growth": {"Quantitative Equity Fund": 0.35, "High Yield Fund": 0.25,
               "Investment Grade Fund": 0.15, "CAL Income Fund": 0.15,
               "Capital Alliance Gilt Fund": 0.10},
}


@dataclass
class FundAnalysis:
    name: str
    file: str
    observations: int
    latest_date: str
    latest_price: float
    latest_period_return_pct: float
    one_year_return_pct: float
    recent_return_pct: float
    short_period_volatility_pct: float
    score: float = 0.0
    opportunity: str = ""
    allocation_lkr: int = 0


def fund_name(path: Path) -> str:
    return path.stem.replace("_", " ")


def repaired_lines(path: Path) -> list[str]:
    """Read lines and insert a comma when a date was concatenated to a number."""
    text = path.read_text(encoding="utf-8-sig")
    return [re.sub(r"(?<=\d)(?=20\d{2}-\d{2}-\d{2})", ",", line)
            for line in text.splitlines() if line.strip()]


def read_rows(path: Path) -> list[dict[str, str]]:
    lines = repaired_lines(path)
    rows = list(csv.DictReader(lines))
    valid = []
    for row in rows:
        if not EXPECTED_COLUMNS.issubset(row):
            continue
        try:
            row["scraped_date_obj"] = date.fromisoformat(row["scraped_date"])
            row["old_date_obj"] = date.fromisoformat(row["old_date"])
            row["new_date_obj"] = date.fromisoformat(row["new_date"])
            row["old_price_num"] = float(row["old_price"])
            row["new_price_num"] = float(row["new_price"])
            row["price_growth_num"] = float(row["price_growth"])
        except (TypeError, ValueError):
            continue
        if row["new_price_num"] > 0 and row["old_price_num"] > 0:
            valid.append(row)
    return valid


def minmax(values: list[float]) -> dict[float, float]:
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return {v: 0.5 for v in values}
    return {v: (v - low) / (high - low) for v in values}


def analyze_fund(path: Path) -> FundAnalysis:
    rows = read_rows(path)
    if not rows:
        raise ValueError(f"No valid observations in {path}")
    rows.sort(key=lambda r: (r["new_date_obj"], r["scraped_date_obj"]))
    latest = rows[-1]
    annual = [r for r in rows if 300 <= (r["new_date_obj"] - r["old_date_obj"]).days <= 430]
    annual.sort(key=lambda r: r["new_date_obj"])
    one_year = annual[-1] if annual else latest
    recent = [r for r in rows if 0 < (r["new_date_obj"] - r["old_date_obj"]).days <= 45]
    recent_growth = statistics.mean(r["price_growth_num"] for r in recent) if recent else latest["price_growth_num"]
    vol = statistics.pstdev(r["price_growth_num"] for r in recent) if len(recent) > 1 else 0.0
    return FundAnalysis(
        name=fund_name(path), file=path.name, observations=len(rows),
        latest_date=latest["new_date"], latest_price=latest["new_price_num"],
        latest_period_return_pct=latest["price_growth_num"],
        one_year_return_pct=one_year["price_growth_num"],
        recent_return_pct=recent_growth, short_period_volatility_pct=vol,
    )


def rank_funds(funds: list[FundAnalysis]) -> None:
    annual = minmax([f.one_year_return_pct for f in funds])
    recent = minmax([f.recent_return_pct for f in funds])
    stability_raw = [1 / (1 + f.short_period_volatility_pct) for f in funds]
    stability = minmax(stability_raw)
    for f, stable_value in zip(funds, stability_raw):
        f.score = round(100 * (0.55 * annual[f.one_year_return_pct]
                               + 0.25 * recent[f.recent_return_pct]
                               + 0.20 * stability[stable_value]), 2)
    funds.sort(key=lambda f: (f.score, f.one_year_return_pct), reverse=True)
    for index, f in enumerate(funds):
        f.opportunity = "Strong candidate" if index == 0 else "Worth considering" if index < 3 else "Diversifier / monitor"


def allocate(funds: list[FundAnalysis], budget: int, profile: str) -> None:
    targets = RISK_PROFILES[profile]
    # Blend the data score with a risk-aware target so a single strong period
    # cannot make the portfolio entirely one fund.
    score_total = sum(max(f.score, 1.0) for f in funds)
    raw = {f.name: 0.60 * (max(f.score, 1.0) / score_total) + 0.40 * targets.get(f.name, 0.0)
           for f in funds}
    floor = budget * 0.10 / budget  # 10% floor per tracked fund
    weights = {name: max(weight, floor) for name, weight in raw.items()}
    total_weight = sum(weights.values())
    amounts = {name: int(budget * weight / total_weight / 1000) * 1000 for name, weight in weights.items()}
    remainder = budget - sum(amounts.values())
    for f in sorted(funds, key=lambda x: x.score, reverse=True):
        if remainder <= 0:
            break
        amounts[f.name] += 1000
        remainder -= 1000
    for f in funds:
        f.allocation_lkr = amounts[f.name]


def write_outputs(funds: list[FundAnalysis], selected: list[FundAnalysis], budget: int,
                  profile: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"budget_lkr": budget, "risk_profile": profile,
               "recommended_funds": [f.name for f in selected],
               "generated_from": "data/*.csv", "funds": [asdict(f) for f in funds]}
    (output_dir / "analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (output_dir / "analysis.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=asdict(funds[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(f) for f in funds)
    lines = [f"CAL Unit Trust Analysis | Budget: {budget:,} LKR/month | Profile: {profile}",
             "", "Recommended funds (top 3):"]
    for i, f in enumerate(selected, 1):
        lines.append(f"{i}. {f.name}: {f.allocation_lkr:,} LKR/month")
    lines += ["", "Full ranking (heuristic score: 55% one-year return, 25% recent return, 20% stability):"]
    for i, f in enumerate(funds, 1):
        lines.append(f"{i}. {f.name}: score {f.score:.2f} | 1Y {f.one_year_return_pct:.2f}% | "
                     f"recent {f.recent_return_pct:.2f}% | volatility {f.short_period_volatility_pct:.2f}% | "
                     f"{f.opportunity} | suggested {f.allocation_lkr:,} LKR")
    lines += ["", f"Total suggested allocation: {sum(f.allocation_lkr for f in selected):,} LKR",
              "", "Important: this is a data-based screening tool, not personal investment advice. "
              "Review fees, liquidity, tax, risk tolerance, and the latest fund documents before investing."]
    (output_dir / "analysis_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=90_000, help="Monthly budget in LKR (default: 90000)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/analysis"))
    parser.add_argument("--risk-profile", choices=RISK_PROFILES, default="balanced")
    parser.add_argument("--top-n", type=int, default=3,
                        help="Number of top-ranked funds to recommend (default: 3)")
    args = parser.parse_args()
    if args.budget <= 0:
        parser.error("--budget must be positive")
    funds = [analyze_fund(path) for path in sorted(args.data_dir.glob("*.csv"))]
    if not funds:
        raise SystemExit(f"No CSV files found in {args.data_dir}")
    if not 1 <= args.top_n <= len(funds):
        parser.error(f"--top-n must be between 1 and {len(funds)}")
    rank_funds(funds)
    selected = funds[:args.top_n]
    allocate(selected, args.budget, args.risk_profile)
    write_outputs(funds, selected, args.budget, args.risk_profile, args.output_dir)
    print((args.output_dir / "analysis_report.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
