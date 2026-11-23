'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { AnalysisFund, DashboardData, MarketContext, RefreshResult } from '../types';

type Metric = 'growth' | 'rolling1y' | 'price';
type ClassFilter = 'all' | 'liquid' | 'income' | 'growth' | 'held';

const COLORS = ['#38bdf8', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#14b8a6', '#f97316', '#eab308', '#ec4899', '#84cc16', '#6366f1', '#06b6d4', '#fb7185', '#a3e635', '#c084fc'];
const CLASS_LABEL: Record<string, string> = { liquid: 'Money market', income: 'Fixed income', growth: 'Equity / balanced' };
const TOOLTIP_STYLE = { background: '#020617', border: '1px solid #1e293b' };

const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? '-' : new Intl.NumberFormat('en-LK', { maximumFractionDigits: d, minimumFractionDigits: d }).format(v));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? '-' : `${num(v)}%`);
const lkr = (v: number | null | undefined) => (v === null || v === undefined ? '-' : `LKR ${new Intl.NumberFormat('en-LK', { maximumFractionDigits: 0 }).format(v)}`);
const aum = (v: number | null) => (v === null ? '-' : v >= 1e9 ? `${num(v / 1e9, 1)}B` : `${num(v / 1e6, 0)}M`);
const tone = (v: number | null | undefined) => ({ color: v === null || v === undefined ? undefined : v >= 0 ? '#86efac' : '#fda4af' });

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshLog, setRefreshLog] = useState('');
  const [metric, setMetric] = useState<Metric>('growth');
  const [classFilter, setClassFilter] = useState<ClassFilter>('all');
  const [range, setRange] = useState('3');
  const [budget, setBudget] = useState('90000');
  const [riskProfile, setRiskProfile] = useState('balanced');
  const [years, setYears] = useState('5');

  const loadData = async () => {
    const response = await fetch('/api/dashboard', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Dashboard data failed: ${response.status}`);
    const payload = await response.json() as DashboardData;
    setData(payload);
    if (payload.analysis) {
      setBudget(String(payload.analysis.budget_lkr));
      setRiskProfile(payload.analysis.risk_profile);
      setYears(String(payload.analysis.projections[0]?.years ?? 5));
    }
  };

  useEffect(() => {
    loadData()
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load dashboard'))
      .finally(() => setLoading(false));
  }, []);

  const runPython = async (skipUpdate: boolean) => {
    setRefreshing(true);
    setError(null);
    setRefreshLog(skipUpdate ? 'Re-running analysis...' : 'Fetching CAL prices and re-running analysis...');
    try {
      const response = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ budget: Number(budget), riskProfile, years: Number(years), skipUpdate }),
      });
      const result = await response.json() as RefreshResult;
      setRefreshLog(result.output || 'Done.');
      if (!response.ok || !result.ok) throw new Error('Python run failed - see the output panel.');
      await loadData();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const analysis = data?.analysis ?? null;
  const fundsByCode = useMemo(() => new Map((analysis?.funds ?? []).map((f) => [f.code, f])), [analysis]);
  const heldCodes = useMemo(() => new Set((analysis?.current_portfolio?.positions ?? []).map((p) => p.code)), [analysis]);
  const codes = useMemo(() => (data?.funds ?? []).map((f) => f.code).filter((code) => {
    if (classFilter === 'all') return true;
    if (classFilter === 'held') return heldCodes.has(code);
    return fundsByCode.get(code)?.asset_class === classFilter;
  }), [data, classFilter, fundsByCode, heldCodes]);

  const chartRows = useMemo(() => {
    const grid = data?.grid ?? [];
    if (!grid.length) return [];
    const last = grid.at(-1)!.date;
    const cutoff = range === 'all' ? '' : `${Number(last.slice(0, 4)) - Number(range)}${last.slice(4)}`;
    const byDate = new Map(grid.map((row, i) => [row.date, i]));
    const visible = grid.filter((row) => row.date >= cutoff);
    const base: Record<string, number> = {};
    return visible.map((row) => {
      const out: Record<string, number | string> = { date: row.date };
      for (const code of codes) {
        const price = row[code];
        if (typeof price !== 'number') continue;
        if (metric === 'price') out[code] = price;
        else if (metric === 'growth') {
          base[code] ??= price;
          out[code] = (price / base[code]) * 100;
        } else {
          const idx = byDate.get(row.date)! - 52;
          const prior = idx >= 0 ? grid[idx][code] : undefined;
          if (typeof prior === 'number') out[code] = (price / prior - 1) * 100;
        }
      }
      return out;
    });
  }, [data, codes, metric, range]);

  if (loading) return <main className="page"><div className="state-card">Loading CAL fund dashboard...</div></main>;
  if (!data) return <main className="page"><div className="state-card error">{error ?? 'No dashboard data found.'}</div></main>;

  const portfolio = analysis?.current_portfolio ?? null;
  const latestDate = data.funds.reduce((max, f) => (f.lastDate > max ? f.lastDate : max), '-');
  const groups = (['liquid', 'income', 'growth'] as const).map((cls) => ({
    cls,
    funds: (analysis?.funds ?? []).filter((f) => f.asset_class === cls)
      .sort((a, b) => (a.rank_in_class ?? 99) - (b.rank_in_class ?? 99)),
  }));
  const pie = (analysis?.holdings ?? []).map((h) => ({ name: h.code, value: h.allocation_lkr }));
  const metricLabel = metric === 'growth' ? 'Growth of LKR 100' : metric === 'rolling1y' ? 'Rolling 1-year return %' : 'Unit price (LKR)';

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">CAL Fund Analysis</p>
          <h1>Unit Trust Decision Dashboard</h1>
          <p className="subtitle">Daily CAL unit prices since 2014, risk-adjusted peer rankings, and where this month&apos;s money should go for your profile.</p>
        </div>
        <div className="hero-actions">
          <div className="refresh-box"><span>Latest price date</span><strong>{latestDate}</strong></div>
          <button className="primary-button" type="button" onClick={() => runPython(false)} disabled={refreshing}>
            {refreshing ? 'Running Python...' : 'Fetch prices + analyse'}
          </button>
        </div>
      </section>

      {error && <div className="state-card error compact-error">{error}</div>}
      {data.analysisError && <div className="state-card error compact-error">{data.analysisError}</div>}

      <section className="filters">
        <label><span>Monthly budget (LKR)</span>
          <input type="number" min={1000} step={1000} value={budget} onChange={(e) => setBudget(e.target.value)} />
        </label>
        <label><span>Risk profile</span>
          <select value={riskProfile} onChange={(e) => setRiskProfile(e.target.value)}>
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="growth">Growth</option>
          </select>
        </label>
        <label><span>Projection years</span>
          <input type="number" min={1} max={40} value={years} onChange={(e) => setYears(e.target.value)} />
        </label>
        <button className="primary-button" type="button" onClick={() => runPython(true)} disabled={refreshing}>Re-plan</button>
      </section>

      {analysis && (
        <section className="grid two">
          <div className="card">
            <div className="card-title">
              <h2>This month: {lkr(analysis.budget_lkr)} ({analysis.risk_profile})</h2>
              <p>{analysis.risk_profile_description}</p>
            </div>
            <div className="split">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Tooltip formatter={(v) => lkr(Number(v))} contentStyle={TOOLTIP_STYLE} />
                  <Pie data={pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                    {pie.map((p, i) => <Cell key={p.name} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <ul className="plain-list">
                {analysis.holdings.map((h, i) => (
                  <li key={h.code}><b style={{ color: COLORS[i % COLORS.length] }}>{h.code}</b> {h.name}<br /><span>{lkr(h.allocation_lkr)} | {CLASS_LABEL[h.asset_class]}</span></li>
                ))}
              </ul>
            </div>
            {analysis.notes.map((n) => <p key={n} className="note">{n}</p>)}
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>After {analysis.projections[0]?.years} yrs if...</th><th>Rate</th><th>Value</th><th>Gain</th></tr></thead>
                <tbody>
                  {analysis.projections.map((p) => (
                    <tr key={p.scenario}><td>{p.scenario}</td><td>{pct(p.annual_return_pct)}</td><td>{lkr(p.projected_value_lkr)}</td><td>{lkr(p.gain_lkr)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note">Invested: {lkr(analysis.projections[0]?.contributed_lkr)} (incl. current holdings). Back-looking illustrations, not forecasts.</p>
          </div>

          <div className="card">
            <div className="card-title"><h2>What the data says</h2><p>Generated {analysis.generated_at.replace('T', ' ')}</p></div>
            <ul className="insights">{analysis.insights.map((i) => <li key={i}>{i}</li>)}</ul>
          </div>
        </section>
      )}

      {portfolio && (
        <section className="card table-card section-gap">
          <div className="card-title">
            <h2>Your portfolio: {lkr(portfolio.total_lkr)}</h2>
            <p>
              From portfolio.local.json (as of {portfolio.as_of || '-'}, kept out of git).
              {portfolio.weighted_yield_pct !== null && ` Blended running yield ${pct(portfolio.weighted_yield_pct)} ≈ ${lkr(portfolio.est_annual_income_lkr)}/yr before tax.`}
            </p>
          </div>
          <div className="analysis-meta">
            {Object.entries(portfolio.class_weights_pct).map(([cls, v]) => (
              <span key={cls}>{CLASS_LABEL[cls]}: {num(v, 0)}% (target {num(portfolio.target_weights_pct[cls] ?? 0, 0)}%)</span>
            ))}
          </div>
          <div className="table-wrap section-gap">
            <table>
              <thead><tr><th>Fund</th><th>Value</th><th>Weight</th><th>30d ann.</th><th>1Y</th><th>Rank in class</th><th>Gap vs best</th></tr></thead>
              <tbody>
                {portfolio.positions.map((p) => (
                  <tr key={p.code}>
                    <td><b>{p.code}</b> {p.name}</td><td>{lkr(p.value_lkr)}</td><td>{pct(p.weight_pct)}</td>
                    <td>{pct(p.yield_30d_ann)}</td><td>{pct(p.return_1y)}</td>
                    <td>{p.rank_in_class ? `#${p.rank_in_class} of ${p.peers_in_class}` : '-'}</td>
                    <td style={tone(p.yield_gap_vs_best_pp)}>{p.yield_gap_vs_best_pp === null ? '-' : `${num(p.yield_gap_vs_best_pp)} pp vs ${p.best_peer_code}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {portfolio.notes.map((n) => <p key={n} className="note">{n}</p>)}
        </section>
      )}

      <section className="card wide section-gap">
        <div className="card-title row-title">
          <div><h2>{metricLabel}</h2><p>Weekly points from data/nav_history.csv</p></div>
          <div className="inline-filters">
            <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
              <option value="growth">Growth of LKR 100</option>
              <option value="rolling1y">Rolling 1-year return</option>
              <option value="price">Unit price</option>
            </select>
            <select value={classFilter} onChange={(e) => setClassFilter(e.target.value as ClassFilter)}>
              <option value="all">All funds</option>
              {portfolio && <option value="held">Funds I hold</option>}
              <option value="liquid">Money market</option>
              <option value="income">Fixed income</option>
              <option value="growth">Equity / balanced</option>
            </select>
            <select value={range} onChange={(e) => setRange(e.target.value)}>
              <option value="1">1 year</option><option value="3">3 years</option>
              <option value="5">5 years</option><option value="all">All history</option>
            </select>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={chartRows}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="date" stroke="#94a3b8" minTickGap={40} />
            <YAxis stroke="#94a3b8" domain={['auto', 'auto']} tickFormatter={(v) => (metric === 'rolling1y' ? `${v}%` : num(Number(v), 0))} />
            <Tooltip formatter={(v) => (metric === 'rolling1y' ? pct(Number(v)) : num(Number(v)))} contentStyle={TOOLTIP_STYLE} />
            <Legend />
            {codes.map((code) => (
              <Line key={code} type="monotone" dataKey={code} stroke={COLORS[data.funds.findIndex((f) => f.code === code) % COLORS.length]}
                strokeWidth={heldCodes.has(code) ? 3 : 1.6} dot={false} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="note">Watch out: money market and some fixed income funds show price drops on distribution/split dates. The analysis ignores history before those breaks; the raw chart does not.</p>
      </section>

      {analysis && analysis.inflation?.length > 0 && <InflationSection analysis={analysis} heldCodes={heldCodes} />}

      {analysis?.market_context && <MarketSection market={analysis.market_context} heldCodes={heldCodes} />}

      {groups.map(({ cls, funds }) => funds.length > 0 && (
        <section className="card table-card section-gap" key={cls}>
          <div className="card-title"><h2>{CLASS_LABEL[cls]}</h2><p>Ranked only against each other. Score blends return, consistency and risk for this asset class.</p></div>
          <div className="table-wrap tall">
            <table>
              <thead><tr><th>Fund</th><th>Status</th><th>Score</th><th>30d ann.</th><th>Trend</th><th>1Y</th><th>3Y CAGR</th><th>5Y CAGR</th><th>Vol 1Y</th><th>Max DD 3Y</th><th>Worst 1Y</th><th>vs MMF</th><th>Spread</th><th>AUM</th><th>This month</th></tr></thead>
              <tbody>{funds.map((f) => <FundRow key={f.code} fund={f} held={heldCodes.has(f.code)} />)}</tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="card log-card section-gap">
        <div className="card-title"><h2>Python output</h2><p>{analysis?.disclaimer}</p></div>
        <pre>{refreshLog || 'Use "Fetch prices + analyse" to pull the latest CAL prices, or "Re-plan" to re-run the analysis with new inputs.'}</pre>
      </section>
    </main>
  );
}

function MarketSection({ market, heldCodes }: { market: MarketContext; heldCodes: Set<string> }) {
  const labels: Record<string, string> = {
    policy_rate_opr: 'Policy rate (OPR)', tbill_91d: '3-month T-bill', tbill_182d: '6-month T-bill',
    tbill_364d: '12-month T-bill', fd_12m_avg: '12-month FD (avg)',
  };
  const usdLabels = Array.from(new Set(market.usd_returns.map((u) => u.label)));
  const usdCodes = Array.from(new Set(market.usd_returns.map((u) => u.code)));
  return (
    <section className="grid two">
      <div className="card table-card">
        <div className="card-title">
          <h2>Interest rates &amp; alternatives</h2>
          <p>Rates drive money market and bond fund returns. Edit data/market_indicators.csv when they change.</p>
        </div>
        <div className="analysis-meta">
          {Object.entries(labels).filter(([k]) => market.rates[k]).map(([k, label]) => (
            <span key={k} title={market.rates[k].note}>
              <a href={market.rates[k].source} target="_blank" rel="noreferrer">{label}</a>: <b>{pct(market.rates[k].value)}</b> ({market.rates[k].date})
            </span>
          ))}
        </div>
        <div className="table-wrap section-gap">
          <table>
            <thead><tr><th>Fund</th><th>30d running yield</th><th>vs 12m T-bill</th><th>vs 12m FD</th></tr></thead>
            <tbody>
              {market.rate_comparisons.map((r) => (
                <tr key={r.code}>
                  <td><b>{r.code}</b>{heldCodes.has(r.code) ? ' ★' : ''}</td><td>{pct(r.yield_30d_ann)}</td>
                  <td style={tone(r.vs_tbill_364d_pp)}>{r.vs_tbill_364d_pp === null ? '-' : `${num(r.vs_tbill_364d_pp)} pp`}</td>
                  <td style={tone(r.vs_fd_12m_pp)}>{r.vs_fd_12m_pp === null ? '-' : `${num(r.vs_fd_12m_pp)} pp`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {market.equity_vs_index.length > 0 && (
          <div className="table-wrap section-gap">
            <table>
              <thead><tr><th>Equity fund vs CSE ASPI</th><th>Since</th><th>Fund</th><th>ASPI</th><th>Beta</th><th>Correlation</th></tr></thead>
              <tbody>
                {market.equity_vs_index.map((e) => (
                  <tr key={e.code}>
                    <td><b>{e.code}</b></td><td>{e.since}</td>
                    <td style={tone(e.fund_return_pct)}>{pct(e.fund_return_pct)}</td>
                    <td style={tone(e.index_return_pct)}>{pct(e.index_return_pct)}</td>
                    <td>{num(e.beta)}</td><td>{num(e.correlation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="card table-card">
        <div className="card-title">
          <h2>Returns in US dollar terms</h2>
          <p>Fund return adjusted for the rupee&apos;s move against the USD: what your savings are worth in hard currency.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Fund</th>{usdLabels.map((l) => <th key={l}>{l}</th>)}</tr></thead>
            <tbody>
              <tr className="muted">
                <td>Rupee vs USD</td>
                {usdLabels.map((l) => {
                  const change = market.usd_returns.find((u) => u.label === l)?.lkr_vs_usd_pct;
                  return <td key={l} style={tone(change)}>{pct(change)}</td>;
                })}
              </tr>
              {usdCodes.map((code) => (
                <tr key={code}>
                  <td><b>{code}</b>{heldCodes.has(code) ? ' ★' : ''}</td>
                  {usdLabels.map((l) => {
                    const u = market.usd_returns.find((x) => x.code === code && x.label === l);
                    return <td key={l} style={tone(u?.usd_return_pct)} title={u ? `LKR return ${pct(u.lkr_return_pct)}` : ''}>{u ? pct(u.usd_return_pct) : '-'}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">Only years with a verified year-end exchange rate are shown. Hover a cell for the rupee return.</p>
      </div>
    </section>
  );
}

function InflationSection({ analysis, heldCodes }: { analysis: NonNullable<DashboardData['analysis']>; heldCodes: Set<string> }) {
  const codes = analysis.funds
    .filter((f) => (f.eligible || heldCodes.has(f.code)) && analysis.real_returns[f.code]?.periods.length)
    .map((f) => f.code);
  const [shown, setShown] = useState<string[]>(() => {
    const held = codes.filter((c) => heldCodes.has(c));
    return held.length ? held : codes.slice(0, 4);
  });
  const rows = analysis.inflation.map((period) => {
    const row: Record<string, number | string> = { label: period.label, CCPI: period.ccpi_yoy_pct };
    for (const code of codes) {
      const match = analysis.real_returns[code].periods.find((p) => p.label === period.label);
      if (match) row[code] = match.nominal_pct;
    }
    return row;
  });
  const cell = (code: string, label: string) => analysis.real_returns[code].periods.find((p) => p.label === label);
  return (
    <section className="card section-gap">
      <div className="card-title row-title">
        <div>
          <h2>Returns vs Sri Lanka inflation (CCPI)</h2>
          <p>Bars: CCPI inflation, Dec-to-Dec, except the latest bar, which is the 12 months to the latest release. Lines: each fund&apos;s nominal return over the same 12 months.</p>
        </div>
        <div className="chip-row">
          {codes.map((code) => (
            <button key={code} type="button" className={shown.includes(code) ? 'chip on' : 'chip'}
              onClick={() => setShown((cur) => (cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]))}>
              {code}{heldCodes.has(code) ? ' ★' : ''}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="label" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" tickFormatter={(v) => `${v}%`} />
          <Tooltip formatter={(v) => pct(Number(v))} contentStyle={TOOLTIP_STYLE} />
          <Legend />
          <Bar dataKey="CCPI" name="CCPI inflation" fill="#ef4444" fillOpacity={0.45} />
          {shown.map((code) => (
            <Line key={code} type="monotone" dataKey={code} stroke={COLORS[codes.indexOf(code) % COLORS.length]} strokeWidth={2.4} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="table-wrap tall section-gap">
        <table>
          <thead>
            <tr><th>Period</th><th>CCPI</th>{codes.map((c) => <th key={c}>{c}{heldCodes.has(c) ? ' ★' : ''} real</th>)}</tr>
          </thead>
          <tbody>
            {analysis.inflation.map((period) => (
              <tr key={period.label}>
                <td><a href={period.source} target="_blank" rel="noreferrer">{period.label}</a></td>
                <td>{pct(period.ccpi_yoy_pct)}</td>
                {codes.map((code) => {
                  const p = cell(code, period.label);
                  return <td key={code} style={tone(p?.real_pct)} title={p ? `nominal ${pct(p.nominal_pct)}` : ''}>{p ? pct(p.real_pct) : '-'}</td>;
                })}
              </tr>
            ))}
            <tr>
              <td><b>Years beaten</b></td><td />
              {codes.map((code) => {
                const full = analysis.real_returns[code].periods.filter((p) => /^\d{4}$/.test(p.label));
                return <td key={code}>{full.filter((p) => p.real_pct > 0).length}/{full.length}</td>;
              })}
            </tr>
            <tr>
              <td><b>Cumulative real</b></td><td />
              {codes.map((code) => {
                const r = analysis.real_returns[code];
                return <td key={code} style={tone(r.cumulative_real_pct)} title={`since ${r.cumulative_since}`}>{r.cumulative_real_pct === null ? '-' : `${num(r.cumulative_real_pct, 0)}% (from ${r.cumulative_since})`}</td>;
              })}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="note">Real return = (1 + fund return) / (1 + inflation) − 1. Hover a cell for the nominal return. The 2022 crisis (57% inflation) still dominates long-run real results.</p>
    </section>
  );
}

function FundRow({ fund: f, held }: { fund: AnalysisFund; held: boolean }) {
  const status = f.eligible ? `#${f.rank_in_class}` : f.eligibility_notes.join('; ');
  return (
    <tr title={f.data_breaks.join('\n')}>
      <td><b>{f.code}</b>{held && ' ★'} <span className="muted">{f.name}</span></td>
      <td className={f.eligible ? '' : 'muted'}>{status}</td>
      <td>{num(f.score, 1)}</td>
      <td>{pct(f.yield_30d_ann)}</td>
      <td style={tone(f.yield_trend_pp)}>{f.yield_trend_pp === null ? '-' : `${f.yield_trend_pp > 0 ? '+' : ''}${num(f.yield_trend_pp)} pp`}</td>
      <td style={tone(f.return_1y)}>{pct(f.return_1y)}</td>
      <td style={tone(f.cagr_3y)}>{pct(f.cagr_3y)}</td>
      <td style={tone(f.cagr_5y)}>{pct(f.cagr_5y)}</td>
      <td>{pct(f.volatility_1y)}</td>
      <td style={tone(f.max_drawdown_3y)}>{pct(f.max_drawdown_3y)}</td>
      <td style={tone(f.worst_rolling_1y)}>{pct(f.worst_rolling_1y)}</td>
      <td style={tone(f.excess_1y_vs_benchmark)}>{f.excess_1y_vs_benchmark === null ? '-' : `${num(f.excess_1y_vs_benchmark)} pp`}</td>
      <td>{pct(f.price_spread_pct)}</td>
      <td>{aum(f.aum_lkr)}</td>
      <td>{f.allocation_lkr ? lkr(f.allocation_lkr) : '-'}</td>
    </tr>
  );
}
