import { NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import type { AnalysisPayload, DashboardData, FundSeries, PriceGridRow } from '../../../types';

export const dynamic = 'force-dynamic';

const REPO_ROOT = path.resolve(process.cwd(), '..');
const NAV_PATH = path.join(REPO_ROOT, 'data', 'nav_history.csv');
const ANALYSIS_PATH = path.join(REPO_ROOT, 'output', 'analysis', 'analysis.json');
const DAY_MS = 86_400_000;

type Series = { days: number[]; prices: number[] };

function readNav(): Map<string, Series> {
  const series = new Map<string, Series>();
  if (!fs.existsSync(NAV_PATH)) return series;
  const lines = fs.readFileSync(NAV_PATH, 'utf8').split(/\r?\n/).slice(1);
  for (const line of lines) {
    const [date, code, priceText] = line.split(',');
    const price = Number(priceText);
    const day = Date.parse(`${date}T00:00:00Z`);
    if (!code || !Number.isFinite(price) || price <= 0 || Number.isNaN(day)) continue;
    const s = series.get(code) ?? { days: [], prices: [] };
    s.days.push(day);
    s.prices.push(price);
    series.set(code, s);
  }
  return series; // file is written sorted by date
}

/** Price on `day` or the latest earlier one within 7 days. */
function atOrBefore(s: Series, day: number): number | undefined {
  let lo = 0;
  let hi = s.days.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (s.days[mid] <= day) { found = mid; lo = mid + 1; } else { hi = mid - 1; }
  }
  if (found < 0 || day - s.days[found] > 7 * DAY_MS) return undefined;
  return s.prices[found];
}

/** Weekly grid aligned to the latest date so every fund shares the same x values. */
function buildGrid(series: Map<string, Series>): PriceGridRow[] {
  const all = [...series.values()].filter((s) => s.days.length);
  if (!all.length) return [];
  const end = Math.max(...all.map((s) => s.days.at(-1)!));
  const start = Math.min(...all.map((s) => s.days[0]));
  const rows: PriceGridRow[] = [];
  for (let day = end; day >= start; day -= 7 * DAY_MS) {
    const row: PriceGridRow = { date: new Date(day).toISOString().slice(0, 10) };
    for (const [code, s] of series) {
      const price = atOrBefore(s, day);
      if (price !== undefined) row[code] = price;
    }
    rows.push(row);
  }
  return rows.reverse();
}

function readAnalysis(): { analysis: AnalysisPayload | null; error: string | null } {
  if (!fs.existsSync(ANALYSIS_PATH)) return { analysis: null, error: 'No analysis yet - run the update.' };
  try {
    const parsed = JSON.parse(fs.readFileSync(ANALYSIS_PATH, 'utf8')) as AnalysisPayload;
    if (parsed.schema_version !== 2) return { analysis: null, error: 'Analysis file is from an older version - run the update.' };
    return { analysis: parsed, error: null };
  } catch {
    return { analysis: null, error: 'Could not read output/analysis/analysis.json' };
  }
}

export async function GET() {
  const series = readNav();
  const funds: FundSeries[] = [...series.entries()].map(([code, s]) => ({
    code,
    firstDate: new Date(s.days[0]).toISOString().slice(0, 10),
    lastDate: new Date(s.days.at(-1)!).toISOString().slice(0, 10),
    observations: s.days.length,
  }));
  const { analysis, error } = readAnalysis();
  const data: DashboardData = {
    refreshedAt: new Date().toISOString(),
    funds,
    grid: buildGrid(series),
    analysis,
    analysisError: error,
  };
  return NextResponse.json(data);
}
