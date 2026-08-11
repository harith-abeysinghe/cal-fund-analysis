"""README.md - CAL Fund Analysis Project Documentation"""

# CAL Fund Analysis Project

## Project Overview

Automated system for analyzing CAL Unit Trust fund returns and generating investment recommendations for HARITH's long-term investment strategy (debt elimination and wealth accumulation).

## Script Files

### main.py - Data Collection Script

**Purpose:** Scrape CAL website to collect fund data
**Execution:** Run weekly via cron job (every Sunday at 06:00)

**Features:**
- Scrapes 5 specific target funds from CAL website
- Implements smart caching to avoid re-scraping fund names unnecessarily
- Saves data to individual CSV files per fund
- Validates data authenticity before storage

**Key Commands:**
```bash
python main.py
```

### analyze.py - Investment Analysis & Recommendation Script

**Purpose:** Analyze historical data and generate investment recommendations
**Prerequisite:** Minimum 20 weeks of historical data required

**Features:**
- Analyzes all available fund CSV files
- Filters only the 5 tracked target funds
- Identifies top 3 performing funds based on latest returns
- Generates WhatsApp-ready recommendation messages
- Implements strategic allocation logic within 100,000 LKR limit

**Recommended Execution:**
```bash
# Run after main.py has collected sufficient data
python analyze.py
```

### src/services/main_utils.py - Market Pattern Allocation Engine

**Purpose:** Implements sophisticated pattern-based investment allocation strategies

**Features:**
- Market pattern recognition using historical performance data
- Strategic weights based on fund characteristics
- Allocation constraints: 10,000-60,000 LKR per fund, total 100,000 LKR
- Generates professional WhatsApp messages with strategic insights
- Decapitalizes fund names for readability

## Directory Structure

```
/appointments-calendar
├── main.py                    # Data collection script
├── analyze.py                 # Investment analysis script  
└── src/services/
    └── main_utils.py          # Pattern allocation engine
```

## Fund Files (Generated from scraping)

CSV files generated in DATA_DIR:
- Investment_Grade_Fund.csv
- CAL_Income_Fund.csv
- Quantitative_Equity_Fund.csv
- High_Yield_Fund.csv
- Capital_Alliance_Gilt_Fund.csv

## Configuration

**Target Funds (Static - Always Tracked):**
1. Investment Grade Fund
2. CAL Income Fund
3. Quantitative Equity Fund
4. High Yield Fund
5. Capital Alliance Gilt Fund

**Investment Rules:**
- Maximum monthly investment: 100,000 LKR
- Minimum allocation per fund: 10,000 LKR
- Maximum allocation per fund: 60,000 LKR
- Requirements: minimum 20 weeks of data for recommendations

## Execution and Scheduling

### Weekly Automation Setup

**Cron Job for Data Collection (main.py):**
```bash
0 6 * * 0 cd "D:/Personal/CAL Fund Analysis" && python main.py
```

**Manual Run for Analysis (analyze.py):**
```bash
cd "D:/Personal/CAL Fund Analysis" && python analyze.py
```

### System Flow

1. **Weekly:** `main.py` collects fresh data from CAL website
2. **At Analysis Time:** `analyze.py` processes historical data and generates recommendations
3. ** continuous:** `main_utils.py` provides strategic allocation algorithms

## Example Outputs

### Expected analyze.py Output (Recommendation File)

```
📊 Investment Recommendation - [DATE]

🏆 Top 3 Best Performing Funds:
• Investment Grade Fund: 50,000 LKR
• CAL Income Fund: 35,000 LKR  
• Quantitative Equity Fund: 15,000 LKR

💰 Total Allocation: 100,000 LKR or less

📊 Based on 20+ weeks of data
📈 Pattern: Growth Momentum Phase
```

## Pattern Analysis Guidelines

### Data Requirements

**Minimum Requirements:**
- 20+ weeks of historical data for each fund
- Consistent weekly return patterns
- Sufficient volume for pattern validation

**Investment Decisions Based on Patterns:**
- Early exponential growth patterns: Prioritize allocation
- Consistent income patterns: Strategic buffer allocation
- Interest rate sensitivity: Appropriate for risk diversification

## Troubleshooting

### Common Issues

1. **Insufficient Data Error:**
   - Ensure `main.py` has been run at least 20+ times
   - Check `data/` directory for >=5 CSV files
   - Minimum 20 weeks of data required per fund

2. **CSV Format Issues:**
   - Expected format: `date,return`
   - Date format: YYYY-MM-DD
   - Return format: Decimal (e.g., 10.5)

3. **Web Scraping Problems:**
   - Website structure changes may affect data extraction
   - Manual verification required for unusual data

### Verification Steps

1. **Data Integrity Check:**
   ```bash
   python main.py
   ```
   This ensures fresh data is collected correctly.

2. **Analysis Check:**
   ```bash
   python analyze.py
   ```
   Verifies weekly recommendations are generated.

3. **Manual Pattern Review:**
   - Manually verify key field values in output files
   - Compare with website data for accuracy
   - Review pattern strength indicators

### Deployment and Maintenance

**Key Files to Monitor:**
- `data/*.csv` - Collection integrity
- `output/*.txt` - Recommendation accuracy
- `cache/fund_names.json` - Pattern caching

**Regular Maintenance Tasks:**
- Weekly: Run `main.py` for fresh data collection
- Monthly: Review data quality and accuracy
- As Needed: Review investment allocation logic based on market conditions

## Next Steps

1. **Setup:** Create designated directory structure
2. **Test:** Run `main.py` to ensure data collection works
3. **Validate:** Run `analyze.py` once sufficient data is available
4. **Schedule:** Set up weekly cron job for `main.py`
5. **Monitor:** Regular review of investment recommendations

## Notes

- All fund tracking is limited to the 5 target funds
- Investment recommendations are based on market patterns recognized over minimum 20 weeks
- System implements strategic allocation within defined constraints
- Perfect for HARITH's long-term investment objectives (debt elimination, wealth accumulation)
