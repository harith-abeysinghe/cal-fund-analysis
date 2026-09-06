CAL Fund Dashboard

Next.js + TypeScript dashboard for the existing CAL Fund Analysis repo.

Data source:
- Parent repo `data/*.csv`
- Parent repo `output/analysis/analysis.json` when present

Refresh button:
- Runs `python -m src.main`
- Then runs `python analyze.py --budget 90000 --risk-profile balanced`
- Reloads the dashboard data after completion

Run:

cd "D:/Personal/CAL Fund Analysis/cal-dashboard"
npm install
npm run dev

Open:

http://localhost:3020
