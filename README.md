# CAL Fund Analysis

Tracks the daily unit prices of all 15 CAL (Capital Alliance) unit trusts, measures
return **and risk** for each one, ranks every fund only against others in its asset class,
and suggests how to invest a monthly budget for a chosen risk profile. It can also
take your current holdings into account. An optional Next.js dashboard charts the results.

> This is a screening tool, not investment advice. Past returns do not predict future returns.

## Setup

```bash
python -m venv .venv            # Python 3.14
python -m pip install -r requirements.txt
python -m src.main backfill     # one-time: daily prices since 2014 (~15 min, ~4,700 requests)
```

## Commands

```bash
python -m src.main                       # fetch recent prices, then analyse (default)
python -m src.main update                # fetch recent prices only (GitHub Actions uses this)
python -m src.main analyze --budget 90000 --risk-profile balanced --years 5
python -m src.main analyze --no-portfolio   # ignore your current holdings
python -m unittest -v                    # tests
```

`python analyze.py ...` still works and is the same as `python -m src.main analyze ...`.

Reports are written to `output/analysis/` (`analysis_report.txt`, `analysis.json`,
`analysis.csv`). The `output/` folder is ignored by Git.

## Data

| File | Contents |
| --- | --- |
| `data/nav_history.csv` | `date,fund,price`: one row per fund per priced day, from CAL's rates API |
| `data/fund_snapshot.json` | Latest fund size (AUM), latest published price, buy/sell price gap |
| `portfolio.local.json` | **Your holdings, ignored by Git.** Copy `portfolio.example.json` to create it |

For any `valuedate`, the CAL endpoint (`admin-ajax.php?action=getUTFundRates`)
returns each fund's price on that date (`OLD_PRICE`) plus the latest price.
The collector reads this for every calendar day. Each update re-reads the last 10 days,
because funds publish prices on different delays.

The old per-fund CSVs (`data/<Fund_Name>.csv`) are no longer updated. They only stored
"price ~376–407 days ago vs today" pairs, so they could not measure risk, and their
"1-year" return covered a variable window of more than a year.

## How funds are assessed

- **Asset classes**: money market (GMMF, IMMF, CTF), fixed income (IGF, IF, GF, GTF, CDGTF,
  CAHYF, MRDF), equity/balanced (QEF, BF). Each fund is scored only against funds in its own class.
- **Metrics**: 30/90-day annualised yield (calculated the same way as
  [CAL's calculator](https://cal.lk/unittrust/calculator/#calc)), yield trend, exact 1-year
  return, 3- and 5-year CAGR, annualised volatility, max drawdown, worst rolling 1-year
  return, return above the money market fund (the hurdle rate), and a Sharpe-style ratio.
- **Excluded from recommendations**: closed-end funds (FYOF, FYCF, TYCF), funds with
  AUM under LKR 100M, funds whose price is more than 7 days old, and funds with less
  than 1 year of clean history.
- **Data cleaning**: a one-day jump that reverses next day is dropped as a bad data point.
  A jump that persists is treated as a distribution or unit split, and history before it
  is excluded. These are listed under "Data quality" in the report.
- **Buy/sell spread**: QEF and BF publish two prices about 2% apart. The projections deduct this cost.
- **Risk profiles** (`src/config/settings.py`): conservative 10/90/0, balanced 5/75/20,
  growth 5/50/45 (money market / fixed income / equity). If holdings are given, the
  monthly budget goes to the classes furthest below their target, so the portfolio
  rebalances without selling anything.

## Automated data updates

`.github/workflows/update-fund-data.yml` runs Tuesday–Saturday at 18:00 Sri Lanka time
(12:30 UTC), or on demand. It runs the tests, then `python -m src.main update`, then
commits `data/nav_history.csv` and `data/fund_snapshot.json`. Your holdings file is
never used by, or available to, the workflow.

## Dashboard

```bash
cd cal-dashboard
npm install
npm run dev     # http://localhost:3020
```

The dashboard reads `data/nav_history.csv` and `output/analysis/analysis.json`. You can
set the budget, risk profile and projection years, then re-run the planner from the page.
