import { NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import type { AnalysisPayload, DashboardData, FundPoint, FundSeries } from '../../../types';

export const dynamic = 'force-dynamic';

const REPO_ROOT = path.resolve(process.cwd(), '..');
const DATA_DIR = path.join(REPO_ROOT, 'data');
const ANALYSIS_PATH = path.join(REPO_ROOT, 'output', 'analysis', 'analysis.json');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output');

const FUND_CODES: Record<string, string> = {
  Investment_Grade_Fund: 'IGF',
  CAL_Income_Fund: 'IF',
  Quantitative_Equity_Fund: 'QEF',
  High_Yield_Fund: 'CAHYF',
  Capital_Alliance_Gilt_Fund: 'GF',
};

function parseNumber(value: string | undefined): number {
  if (!value) return 0;
  const parsed = Number(value.trim().replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function repairCsvText(text: string): string {
  return text.replace(/(?<=\d)(?=20\d{2}-\d{2}-\d{2})/g, ',');
}

function splitCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = '';
  let quoted = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const next = line[i + 1];

    if (char === '"' && quoted && next === '"') {
      current += '"';
      i += 1;
      continue;
    }

    if (char === '"') {
      quoted = !quoted;
      continue;
    }

    if (char === ',' && !quoted) {
      cells.push(current);
      current = '';
      continue;
    }

    current += char;
  }

  cells.push(current);
  return cells;
}

function fundNameFromFile(file: string): string {
  return file.replace(/\.csv$/i, '').replace(/_/g, ' ');
}

function readFundCsv(file: string): FundSeries {
  const stem = file.replace(/\.csv$/i, '');
  const fullPath = path.join(DATA_DIR, file);
  const lines = repairCsvText(fs.readFileSync(fullPath, 'utf8'))
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const points: FundPoint[] = [];
  for (const line of lines.slice(1)) {
    const row = splitCsvLine(line);
    if (row.length < 7) continue;

    const point: FundPoint = {
      scrapedDate: row[0],
      oldDate: row[1],
      oldPrice: parseNumber(row[2]),
      newDate: row[3],
      newPrice: parseNumber(row[4]),
      priceDifference: parseNumber(row[5]),
      priceGrowth: parseNumber(row[6]),
    };

    if (point.newDate && point.newPrice > 0) points.push(point);
  }

  points.sort((a, b) => `${a.newDate}-${a.scrapedDate}`.localeCompare(`${b.newDate}-${b.scrapedDate}`));

  return {
    code: FUND_CODES[stem] ?? stem,
    name: fundNameFromFile(file),
    file,
    observations: points.length,
    latest: points.at(-1) ?? null,
    points,
  };
}

function readAnalysis(): AnalysisPayload | null {
  if (!fs.existsSync(ANALYSIS_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(ANALYSIS_PATH, 'utf8')) as AnalysisPayload;
  } catch {
    return null;
  }
}

function readLatestRecommendation(): string | null {
  if (!fs.existsSync(OUTPUT_DIR)) return null;
  const files = fs.readdirSync(OUTPUT_DIR)
    .filter((file) => /^recommendation_.*\.txt$/i.test(file))
    .map((file) => ({ file, mtime: fs.statSync(path.join(OUTPUT_DIR, file)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);

  if (!files.length) return null;
  return fs.readFileSync(path.join(OUTPUT_DIR, files[0].file), 'utf8');
}

export async function GET() {
  const csvFiles = fs.existsSync(DATA_DIR)
    ? fs.readdirSync(DATA_DIR).filter((file) => file.endsWith('.csv')).sort()
    : [];

  const data: DashboardData = {
    refreshedAt: new Date().toISOString(),
    funds: csvFiles.map(readFundCsv),
    analysis: readAnalysis(),
    recommendationText: readLatestRecommendation(),
  };

  return NextResponse.json(data);
}
