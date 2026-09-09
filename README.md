# CAL Fund Analysis

Collects five CAL unit-trust fund prices into CSV files, ranks their historical
performance, and serves the results through an optional Next.js dashboard.

## Setup

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

## Commands

```bash
# Update data/*.csv and generate a recommendation file.
python -m src.main

# Update only data/*.csv (the command used by GitHub Actions).
python -m src.main --scrape-only

# Analyze the collected data.
python analyze.py --budget 90000 --risk-profile balanced
```

Each fund CSV contains:

```text
scraped_date,old_date,old_price,new_date,new_price,price_difference,price_growth
```

The analysis command accepts `conservative`, `balanced`, and `growth` risk
profiles. Its generated files are written under `output/`, which is intentionally
ignored by Git.

## Automated data updates

`.github/workflows/update-fund-data.yml` runs Tuesday through Saturday at 18:00
in Sri Lanka (12:30 UTC) and can also be started manually from the Actions tab. It installs the Python
dependency, runs the scraper-only command, and commits changed `data/*.csv` files
with the GitHub Actions bot identity. The workflow requires repository Actions to
have write permission to contents; a protected default branch may require a pull
request-based variant instead.

## Dashboard

```bash
cd cal-dashboard
npm install
npm run dev
```

The dashboard reads `data/*.csv` and generated analysis files from the parent
directory. Its refresh button runs the full scraper and analysis commands.
