# CAL Fund Analysis Project

## Project Overview

Automated weekly scraping and analysis of CAL (Capital Alliance) fund data for long-term investment decisions. Scrapes the CAL API, stores price data to CSVs, and generates investment recommendations.

## CSV File Structure

Each fund gets its own CSV file with columns:
```
scraped_date, old_date, old_price, new_date, new_price, price_difference, price_growth
```

Where:
- `scraped_date`: Today's date when data was collected
- `old_date`: Historical date (June 7, 2026) - reference point
- `old_price`: Price on old_date
- `new_date`: Latest available date (July 7, 2026)
- `new_price`: Price on new_date
- `price_difference`: new_price - old_price
- `price_growth`: percentage growth between old and new dates

## Target Funds (5 funds only)

1. Investment Grade Fund → Capital Alliance Investment Grade Fund (IGF)
2. CAL Income Fund → Capital Alliance Income Fund
3. Quantitative Equity Fund → Capital Alliance Quantitative Equity Fund
4. High Yield Fund → Capital Alliance High Yield Fund
5. Capital Alliance Gilt Fund → Capital Alliance Gilt Fund

## File Structure

```
D:/Personal/CAL Fund Analysis/
├── main.py              # Weekly scraper (runs Sundays)
├── analyze.py           # Analysis script (generates recommendations)
├── .env.example         # Configuration template
├── data/                # CSV files per fund
│   ├── Investment_Grade_Fund.csv
│   ├── CAL_Income_Fund.csv
│   ├── Quantitative_Equity_Fund.csv
│   ├── High_Yield_Fund.csv
│   └── Capital_Alliance_Gilt_Fund.csv
├── output/              # Recommendation outputs
│   └── recommendation_YYYYMMDD.txt
├── cache/
│   └── fund_data.json   # Cached API response
├── src/
│   ├── config/
│   │   └── settings.py
│   ├── services/
│   │   ├── csv_manager.py
│   │   └── main_utils.py
│   └── workers/
│       └── analyze_returns.py
└── .venv/               # Python virtual environment
```

## Running the Scripts

```bash
# Activate virtual environment
cd "D:/Personal/CAL Fund Analysis"
.venv\Scripts\activate

# Scrape weekly data
python main.py

# Analyze and generate recommendations (after 20+ weeks of data)
python analyze.py
```

## Analysis Requirements

- **Minimum data**: 20 weeks of historical data required for recommendations
- **Allocation**: Maximum 100,000 LKR monthly investment
- **WhatsApp ready**: Recommendations formatted for direct sharing

## Cron Job Setup (Windows Task Scheduler)

Run `main.py` every Sunday at 06:00 Sri Lanka time (weekly data collection)