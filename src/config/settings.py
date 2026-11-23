"""Static configuration: API endpoint, file locations, fund catalogue and risk profiles.

Nothing here is secret (the CAL rates endpoint is public), so no .env is needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.models.fund import AssetClass, FundInfo

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
NAV_HISTORY_PATH: Path = DATA_DIR / "nav_history.csv"
SNAPSHOT_PATH: Path = DATA_DIR / "fund_snapshot.json"
# Sri Lanka CCPI year-on-year inflation (hand-maintained; add each new December / latest month).
INFLATION_PATH: Path = DATA_DIR / "sri_lanka_inflation.csv"
# Interest-rate / FX reference points (hand-maintained, each row dated and sourced).
INDICATORS_PATH: Path = DATA_DIR / "market_indicators.csv"
# CSE All Share Price Index, collected daily by `update`.
ASPI_PATH: Path = DATA_DIR / "market" / "aspi.csv"
CSE_CHART_URL: str = "https://www.cse.lk/api/chartData"
OUTPUT_DIR: Path = PROJECT_ROOT / "output" / "analysis"
# Personal holdings: git-ignored, never committed (see portfolio.example.json).
PORTFOLIO_PATH: Path = PROJECT_ROOT / "portfolio.local.json"

CAL_API_URL: str = "https://cal.lk/wp-admin/admin-ajax.php"
CAL_API_ACTION: str = "getUTFundRates"

# Each daily update re-reads this many recent days so late-published prices
# (funds publish on different lags) are captured rather than skipped forever.
UPDATE_LOOKBACK_DAYS: int = 10


# Fund catalogue. Codes are the FUND field returned by the CAL API.
# `open_ended=False` funds (closed-end) are tracked but never recommended,
# because they cannot be bought on demand.
FUNDS: dict[str, FundInfo] = {
    info.code: info
    for info in (
        FundInfo("GMMF", "CAL Money Market Fund", AssetClass.LIQUID),
        FundInfo("IMMF", "CAL Islamic Money Market Fund", AssetClass.LIQUID, shariah=True),
        FundInfo("CTF", "Capital Alliance Corporate Treasury Fund", AssetClass.LIQUID),
        FundInfo("IGF", "Capital Alliance Investment Grade Fund", AssetClass.INCOME),
        FundInfo("IF", "Capital Alliance Income Fund", AssetClass.INCOME),
        FundInfo("GF", "Capital Alliance Gilt Fund", AssetClass.INCOME),
        FundInfo("GTF", "Capital Alliance Gilt Trading Fund", AssetClass.INCOME),
        FundInfo("CDGTF", "CAL Fixed Income Opportunities Fund", AssetClass.INCOME),
        FundInfo("CAHYF", "Capital Alliance High Yield Fund", AssetClass.INCOME),
        FundInfo("MRDF", "Capital Alliance Medium Risk Debt Fund", AssetClass.INCOME),
        FundInfo("BF", "Capital Alliance Balanced Fund", AssetClass.GROWTH),
        FundInfo("QEF", "Capital Alliance Quantitative Equity Fund", AssetClass.GROWTH),
        FundInfo("FYOF", "CAL Five Year Optimum Fund", AssetClass.INCOME, open_ended=False),
        FundInfo("FYCF", "CAL Five Year Closed End Fund", AssetClass.INCOME, open_ended=False),
        FundInfo("TYCF", "CAL Three Year Closed End Fund", AssetClass.INCOME, open_ended=False),
    )
}

# The money market fund's return is the hurdle every other fund must beat
# (stand-in for the risk-free rate in excess-return / Sharpe calculations).
BENCHMARK_CODE: str = "GMMF"


@dataclass(frozen=True)
class RiskProfile:
    """Target split of the monthly budget across asset classes."""

    name: str
    description: str
    weights: dict[AssetClass, float] = field(default_factory=dict)


RISK_PROFILES: dict[str, RiskProfile] = {
    "conservative": RiskProfile(
        "conservative",
        "Capital preservation: money market + fixed income only.",
        {AssetClass.LIQUID: 0.10, AssetClass.INCOME: 0.90, AssetClass.GROWTH: 0.00},
    ),
    "balanced": RiskProfile(
        "balanced",
        "Mostly fixed income with a measured equity sleeve.",
        {AssetClass.LIQUID: 0.05, AssetClass.INCOME: 0.75, AssetClass.GROWTH: 0.20},
    ),
    "growth": RiskProfile(
        "growth",
        "Long horizon (5y+); accepts equity drawdowns for higher expected return.",
        {AssetClass.LIQUID: 0.05, AssetClass.INCOME: 0.50, AssetClass.GROWTH: 0.45},
    ),
}

# How many funds each asset class is split across (diversifies manager/credit risk).
FUNDS_PER_CLASS: dict[AssetClass, int] = {
    AssetClass.LIQUID: 1,
    AssetClass.INCOME: 2,
    AssetClass.GROWTH: 1,
}


@dataclass(frozen=True)
class EligibilityRules:
    """Filters a fund must pass before it can be recommended."""

    min_aum_lkr: float = 100_000_000.0  # tiny funds carry concentration / liquidity risk
    max_stale_days: int = 7             # price not updated for a week => investigate first
    min_history_days: int = 365


ELIGIBILITY = EligibilityRules()
