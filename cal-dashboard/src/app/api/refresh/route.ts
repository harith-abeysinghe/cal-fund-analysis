import { NextResponse } from 'next/server';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import type { RefreshResult } from '../../../types';

export const dynamic = 'force-dynamic';

const execFileAsync = promisify(execFile);
const REPO_ROOT = path.resolve(process.cwd(), '..');
const VENV_PYTHON = path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe');
const PYTHON = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python';

async function runPython(args: string[]): Promise<string> {
  const { stdout, stderr } = await execFileAsync(PYTHON, args, {
    cwd: REPO_ROOT,
    timeout: 180_000,
    windowsHide: true,
    maxBuffer: 1024 * 1024 * 4,
  });
  return [stdout, stderr].filter(Boolean).join('\n');
}

export async function POST() {
  const output: string[] = [];

  try {
    output.push(`Running: ${PYTHON} -m src.main`);
    output.push(await runPython(['-m', 'src.main']));
    output.push('Running: analyze.py --budget 90000 --risk-profile balanced');
    output.push(await runPython(['analyze.py', '--budget', '90000', '--risk-profile', 'balanced']));

    const result: RefreshResult = {
      ok: true,
      command: `${PYTHON} -m src.main && ${PYTHON} analyze.py --budget 90000 --risk-profile balanced`,
      output: output.join('\n').trim(),
      refreshedAt: new Date().toISOString(),
    };

    return NextResponse.json(result);
  } catch (error: unknown) {
    const err = error as { stdout?: string; stderr?: string; message?: string };
    output.push(err.stdout ?? '');
    output.push(err.stderr ?? '');
    output.push(err.message ?? 'Refresh failed');

    return NextResponse.json(
      {
        ok: false,
        command: `${PYTHON} -m src.main && ${PYTHON} analyze.py --budget 90000 --risk-profile balanced`,
        output: output.filter(Boolean).join('\n').trim(),
        refreshedAt: new Date().toISOString(),
      } satisfies RefreshResult,
      { status: 500 },
    );
  }
}
