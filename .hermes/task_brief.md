# CAL Fund Analysis - Scraper Fix

## Objective
Fix the fund scraper to use the correct CAL AJAX endpoint for real-time data.

## Current Problem
- main.py and analyze.py exist but scraper uses wrong URL
- CSV files are not being updated with fresh data
- Need to use the AJAX endpoint: https://cal.lk/wp-admin/admin-ajax.php

## Required Changes

### 1. Update src/services/fund_scraper.py
- Change `self.url` to: `https://cal.lk/wp-admin/admin-ajax.php`
- Update `_fetch_page()` to:
  - Use params: `{'action': 'getUTFundRates', 'valuedate': <yesterday's date>}`
  - Parse JSON response: `{"UTMS_FUND": [...]}`
  - Extract: `FUND`, `FUND_NAME`, `LATEST_DATE`, `LATEST_PRICE`, `OLD_DATE`, `OLD_PRICE`
  - Calculate `price_growth` = ((LATEST_PRICE - OLD_PRICE) / OLD_PRICE) * 100

### 2. Map Fund Codes to Target Funds
- IGF → Investment Grade Fund
- IF → CAL Income Fund
- QEF → Quantitative Equity Fund
- CAHYF → High Yield Fund
- GF → Capital Alliance Gilt Fund

### 3. Update CSV Format
Current CSV columns: `scraped_date,old_date,old_price,new_date,new_price,price_difference,price_growth`
Use the actual values from the API response.

### 4. Update CSV Manager
Create `src/services/csv_manager.py` if missing:
- `record_returns(funds)` should append new rows to CSV files
- Use the format from `claude.md`

### 5. Update main.py entry point
- Wire together: Settings → FundScraper → CSVManager → InvestmentPlanner → WhatsAppNotifier

## Files to Modify/Create
1. `src/services/fund_scraper.py` - COMPLETE (already updated)
2. `src/services/csv_manager.py` - CREATE
3. `src/services/investment_planner.py` - CREATE
4. `src/services/whatsapp_notifier.py` - CREATE
5. `src/config/settings.py` - VERIFY
6. `main.py` (root) - VERIFY wiring

## Testing
- Run: `python main.py`
- Verify CSV files have new rows with today's date
- Run: `python analyze.py`
- Verify recommendation is generated

## Expected Output
- Updated CSV files in data/ directory
- Recommendation file in output/ directory
- Message printed to console for WhatsApp delivery