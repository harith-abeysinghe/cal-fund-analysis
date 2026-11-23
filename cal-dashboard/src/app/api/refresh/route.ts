import { NextResponse } from 'next/server';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import type { RefreshResult } from '../../../types';

export const dynamic = 'force-dynamic';

const execFileAsync = promisify(execFile);
const REPO_ROOT = path.resolve(process.cwd(), '..');
const VENV_CANDIDATES = [
  path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
  path.join(REPO_ROOT, '.venv', 'bin', 'python'),
];
const PYTHON = VENV_CANDIDATES.find((candidate) => fs.existsSync(candidate)) ?? 'python';
const PROFILES = new Set(['conservative', 'balanced', 'growth']);

type RefreshRequest = { budget?: unknown; riskProfile?: unknown; years?: unknown; skipUpdate?: unknown };

function parseRequest(body: RefreshRequest): { args: string[] } | { error: string } {
  const budget = Number(body.budget ?? 90_000);
  const years = Number(body.years ?? 5);
  const profile = String(body.riskProfile ?? 'balanced');
  if (!Number.isInteger(budget) || budget < 1 || budget > 1_000_000_000) return { error: 'Budget must be a whole number of LKR.' };
  if (!Number.isInteger(years) || years < 1 || years > 40) return { error: 'Years must be between 1 and 40.' };
  if (!PROFILES.has(profile)) return { error: 'Unknown risk profile.' };
  const command = body.skipUpdate === true ? 'analyze' : 'run';
  return { args: ['-m', 'src.main', command, '--budget', String(budget), '--risk-profile', profile, '--years', String(years)] };
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as RefreshRequest;
  const parsed = parseRequest(body);
  if ('error' in parsed) {
    return NextResponse.json(
      { ok: false, command: '', output: parsed.error, refreshedAt: new Date().toISOString() } satisfies RefreshResult,
      { status: 400 },
    );
  }
  const command = `${PYTHON} ${parsed.args.join(' ')}`;
  try {
    const { stdout, stderr } = await execFileAsync(PYTHON, parsed.args, {
      cwd: REPO_ROOT,
      timeout: 300_000,
      windowsHide: true,
      maxBuffer: 1024 * 1024 * 8,
    });
    return NextResponse.json({
      ok: true, command, output: [stdout, stderr].filter(Boolean).join('\n').trim(), refreshedAt: new Date().toISOString(),
    } satisfies RefreshResult);
  } catch (error: unknown) {
    const err = error as { stdout?: string; stderr?: string; message?: string };
    return NextResponse.json(
      {
        ok: false,
        command,
        output: [err.stdout, err.stderr, err.message ?? 'Refresh failed'].filter(Boolean).join('\n').trim(),
        refreshedAt: new Date().toISOString(),
      } satisfies RefreshResult,
      { status: 500 },
    );
  }
}
