'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DashboardData, FundSeries, RefreshResult } from '../types';

type Metric = 'priceGrowth' | 'newPrice';

const COLORS = ['#38bdf8', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#14b8a6', '#f97316'];

function number(value: number, digits = 2): string {
  return new Intl.NumberFormat('en-LK', { maximumFractionDigits: digits }).format(value);
}

function currency(value: number): string {
  return `LKR ${new Intl.NumberFormat('en-LK', { maximumFractionDigits: 0 }).format(value)}`;
}

function compact(value: number): string {
  return new Intl.NumberFormat('en-LK', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function normalizeDate(date: string): string {
  return date || '1900-01-01';
}

function latestFunds(funds: FundSeries[]) {
  return funds
    .map((fund) => ({
      name: fund.name,
      code: fund.code,
      latestDate: fund.latest?.newDate ?? '-',
      price: fund.latest?.newPrice ?? 0,
      growth: fund.latest?.priceGrowth ?? 0,
      observations: fund.observations,
    }))
    .sort((a, b) => b.growth - a.growth);
}

function metricLabel(metric: Metric): string {
  return metric === 'priceGrowth' ? 'Growth %' : 'Unit Price';
}

function formatMetric(value: number, metric: Metric): string {
  return metric === 'priceGrowth' ? `${number(value)}%` : number(value, 4);
}

function datesFromFunds(funds: FundSeries[]): string[] {
  return Array.from(new Set(funds.flatMap((fund) => fund.points.map((point) => point.newDate))))
    .filter(Boolean)
    .sort();
}

function filterFundPoints(fund: FundSeries, fromDate: string, toDate: string) {
  return fund.points.filter((point) => {
    const date = normalizeDate(point.newDate);
    return date >= fromDate && date <= toDate;
  });
}

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshLog, setRefreshLog] = useState('');
  const [metric, setMetric] = useState<Metric>('priceGrowth');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  const loadData = async () => {
    const response = await fetch('/api/dashboard', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Dashboard data failed: ${response.status}`);
    const dashboardData = await response.json() as DashboardData;
    setData(dashboardData);
    const dates = datesFromFunds(dashboardData.funds);
    setFromDate((current) => current || dates[0] || '');
    setToDate((current) => current || dates.at(-1) || '');
  };

  useEffect(() => {
    loadData()
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load dashboard'))
      .finally(() => setLoading(false));
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    setRefreshLog('Running CAL scraper and analysis...');

    try {
      const response = await fetch('/api/refresh', { method: 'POST' });
      const result = await response.json() as RefreshResult;
      setRefreshLog(result.output || 'Refresh completed.');
      if (!response.ok || !result.ok) throw new Error(result.output || 'Refresh failed');
      await loadData();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const allDates = useMemo(() => datesFromFunds(data?.funds ?? []), [data]);
  const ranking = useMemo(() => latestFunds(data?.funds ?? []), [data]);
  const latestDate = ranking[0]?.latestDate ?? '-';
  const analysisFunds = data?.analysis?.funds ?? [];
  const allocationPie = analysisFunds
    .filter((fund) => fund.allocation_lkr > 0)
    .map((fund) => ({ name: fund.name, value: fund.allocation_lkr }))
    .sort((a, b) => b.value - a.value);

  const combinedTrend = useMemo(() => {
    const rows = new Map<string, Record<string, string | number>>();
    (data?.funds ?? []).forEach((fund) => {
      filterFundPoints(fund, fromDate || '1900-01-01', toDate || '9999-12-31').forEach((point) => {
        const row = rows.get(point.newDate) ?? { date: point.newDate };
        row[fund.code] = point[metric];
        rows.set(point.newDate, row);
      });
    });
    return Array.from(rows.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [data, fromDate, toDate, metric]);

  if (loading) return <main className="page"><div className="state-card">Loading CAL fund dashboard...</div></main>;
  if (!data) return <main className="page"><div className="state-card error">No dashboard data found.</div></main>;

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">CAL Fund Analysis</p>
          <h1>Fund Performance Dashboard</h1>
          <p className="subtitle">Charts from the tracked CAL fund CSV files, with one-click refresh through the existing Python scripts.</p>
        </div>
        <div className="hero-actions">
          <div className="refresh-box"><span>Latest fund date</span><strong>{latestDate}</strong></div>
          <button className="primary-button" type="button" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? 'Running Python...' : 'Run CAL Update'}
          </button>
        </div>
      </section>

      {error && <div className="state-card error compact-error">{error}</div>}

      <section className="filters">
        <label>
          <span>From date</span>
          <select value={fromDate} onChange={(event) => setFromDate(event.target.value)}>
            {allDates.map((date) => <option key={date} value={date}>{date}</option>)}
          </select>
        </label>
        <label>
          <span>To date</span>
          <select value={toDate} onChange={(event) => setToDate(event.target.value)}>
            {allDates.map((date) => <option key={date} value={date}>{date}</option>)}
          </select>
        </label>
        <label>
          <span>Metric</span>
          <select value={metric} onChange={(event) => setMetric(event.target.value as Metric)}>
            <option value="priceGrowth">Return / Growth %</option>
            <option value="newPrice">Unit Price</option>
          </select>
        </label>
      </section>

      <section className="kpi-grid">
        {ranking.map((fund, index) => (
          <div className="kpi" key={fund.code}>
            <span>{fund.code}</span>
            <strong>{fund.name}</strong>
            <small>Latest growth <b style={{ color: fund.growth >= 0 ? '#22c55e' : '#fb7185' }}>{number(fund.growth)}%</b></small>
            <small>Price {number(fund.price, 4)} | {fund.observations} rows</small>
            <em>Rank #{index + 1}</em>
          </div>
        ))}
      </section>

      <section className="grid two">
        <div className="card wide">
          <div className="card-title"><h2>All Funds - {metricLabel(metric)}</h2><p>Combined comparison across the selected date range</p></div>
          <ResponsiveContainer width="100%" height={390}>
            <LineChart data={combinedTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(value) => metric === 'priceGrowth' ? `${value}%` : compact(Number(value))} />
              <Tooltip formatter={(value) => formatMetric(Number(value), metric)} contentStyle={{ background: '#020617', border: '1px solid #1e293b' }} />
              <Legend />
              {data.funds.map((fund, index) => (
                <Line key={fund.code} type="monotone" dataKey={fund.code} name={fund.code} stroke={COLORS[index % COLORS.length]} strokeWidth={2.5} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title"><h2>Recommended Allocation</h2><p>From output/analysis/analysis.json</p></div>
          <ResponsiveContainer width="100%" height={330}>
            <PieChart>
              <Tooltip formatter={(value) => currency(Number(value))} contentStyle={{ background: '#020617', border: '1px solid #1e293b' }} />
              <Pie data={allocationPie} dataKey="value" nameKey="name" innerRadius={64} outerRadius={112} paddingAngle={2}>
                {allocationPie.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
              </Pie>
              <Legend layout="vertical" verticalAlign="middle" align="right" />
            </PieChart>
          </ResponsiveContainer>
          <div className="analysis-meta">
            <span>Budget: {currency(data.analysis?.budget_lkr ?? 0)}</span>
            <span>Risk: {data.analysis?.risk_profile ?? '-'}</span>
          </div>
        </div>
      </section>

      <section className="fund-grid">
        {data.funds.map((fund, fundIndex) => {
          const filtered = filterFundPoints(fund, fromDate || '1900-01-01', toDate || '9999-12-31');
          const latest = fund.latest;
          return (
            <div className="card fund-card" key={fund.file}>
              <div className="card-title row-title">
                <div>
                  <h2>{fund.code} - {fund.name}</h2>
                  <p>{filtered.length} selected points | latest {latest?.newDate ?? '-'}</p>
                </div>
                <span className="badge">{latest ? `${number(latest.priceGrowth)}%` : '-'}</span>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={filtered}>
                  <defs><linearGradient id={`g-${fund.code}`} x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={COLORS[fundIndex % COLORS.length]} stopOpacity={0.34}/><stop offset="95%" stopColor={COLORS[fundIndex % COLORS.length]} stopOpacity={0}/></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="newDate" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" tickFormatter={(value) => metric === 'priceGrowth' ? `${value}%` : compact(Number(value))} />
                  <Tooltip formatter={(value) => formatMetric(Number(value), metric)} contentStyle={{ background: '#020617', border: '1px solid #1e293b' }} />
                  <Area type="monotone" dataKey={metric} name={metricLabel(metric)} stroke={COLORS[fundIndex % COLORS.length]} fill={`url(#g-${fund.code})`} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </section>

      <section className="grid two">
        <div className="card table-card">
          <div className="card-title"><h2>Analysis Ranking</h2><p>Heuristic score from analyze.py</p></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Fund</th><th>Score</th><th>1Y</th><th>Recent</th><th>Volatility</th><th>Allocation</th></tr></thead>
              <tbody>
                {analysisFunds.map((fund) => (
                  <tr key={fund.file}>
                    <td>{fund.name}</td>
                    <td>{number(fund.score)}</td>
                    <td>{number(fund.one_year_return_pct)}%</td>
                    <td>{number(fund.recent_return_pct)}%</td>
                    <td>{number(fund.short_period_volatility_pct)}%</td>
                    <td>{currency(fund.allocation_lkr)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card log-card">
          <div className="card-title"><h2>Refresh Output</h2><p>Console output from the Python run appears here</p></div>
          <pre>{refreshLog || data.recommendationText || 'Click Run CAL Update to scrape fresh data and rebuild analysis.'}</pre>
        </div>
      </section>
    </main>
  );
}
