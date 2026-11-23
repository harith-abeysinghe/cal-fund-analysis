export type FundSeries = {
  code: string;
  firstDate: string;
  lastDate: string;
  observations: number;
};

/** One row per weekly grid date: { date, <CODE>: price, ... } */
export type PriceGridRow = { date: string } & Record<string, number | string>;

export type AnalysisFund = {
  code: string;
  name: string;
  asset_class: 'liquid' | 'income' | 'growth';
  open_ended: boolean;
  latest_date: string;
  latest_price: number;
  history_start: string;
  stale_days: number;
  aum_lkr: number | null;
  price_spread_pct: number | null;
  yield_30d_ann: number | null;
  yield_90d_ann: number | null;
  yield_trend_pp: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_ytd: number | null;
  return_1y: number | null;
  cagr_3y: number | null;
  cagr_5y: number | null;
  volatility_1y: number | null;
  volatility_3y: number | null;
  max_drawdown_3y: number | null;
  current_drawdown: number | null;
  worst_rolling_1y: number | null;
  pct_positive_rolling_1y: number | null;
  excess_1y_vs_benchmark: number | null;
  sharpe_3y: number | null;
  data_breaks: string[];
  eligible: boolean;
  eligibility_notes: string[];
  score: number | null;
  rank_in_class: number | null;
  allocation_lkr: number;
};

export type Holding = {
  code: string;
  name: string;
  asset_class: string;
  allocation_lkr: number;
  weight_pct: number;
};

export type Projection = {
  scenario: string;
  annual_return_pct: number;
  years: number;
  contributed_lkr: number;
  projected_value_lkr: number;
  gain_lkr: number;
};

export type PositionReview = {
  code: string;
  name: string;
  asset_class: string;
  value_lkr: number;
  weight_pct: number;
  yield_30d_ann: number | null;
  return_1y: number | null;
  rank_in_class: number | null;
  peers_in_class: number;
  est_annual_income_lkr: number | null;
  best_peer_code: string | null;
  yield_gap_vs_best_pp: number | null;
};

export type PortfolioReview = {
  total_lkr: number;
  as_of: string;
  positions: PositionReview[];
  class_weights_pct: Record<string, number>;
  target_weights_pct: Record<string, number>;
  weighted_yield_pct: number | null;
  est_annual_income_lkr: number | null;
  notes: string[];
};

export type InflationPeriod = { period_end: string; label: string; ccpi_yoy_pct: number; source: string };

export type FundRealReturns = {
  code: string;
  periods: { label: string; nominal_pct: number; inflation_pct: number; real_pct: number }[];
  cumulative_nominal_pct: number | null;
  cumulative_real_pct: number | null;
  cumulative_since: string | null;
  years_beaten: number;
};

export type MarketContext = {
  rates: Record<string, { value: number; date: string; note: string; source: string }>;
  rate_comparisons: { code: string; yield_30d_ann: number; vs_tbill_364d_pp: number | null; vs_fd_12m_pp: number | null }[];
  equity_vs_index: { code: string; fund_return_pct: number; index_return_pct: number; since: string; correlation: number | null; beta: number | null }[];
  usd_returns: { code: string; label: string; lkr_return_pct: number; lkr_vs_usd_pct: number; usd_return_pct: number }[];
  index_latest: { date: string; value: number } | null;
  insights: string[];
};

export type AnalysisPayload = {
  generated_at: string;
  schema_version: number;
  budget_lkr: number;
  risk_profile: string;
  risk_profile_description: string;
  benchmark: string;
  holdings: Holding[];
  projections: Projection[];
  insights: string[];
  notes: string[];
  starting_value_lkr: number;
  current_portfolio: PortfolioReview | null;
  inflation: InflationPeriod[];
  real_returns: Record<string, FundRealReturns>;
  market_context: MarketContext | null;
  disclaimer: string;
  funds: AnalysisFund[];
};

export type DashboardData = {
  refreshedAt: string;
  funds: FundSeries[];
  grid: PriceGridRow[];
  analysis: AnalysisPayload | null;
  analysisError: string | null;
};

export type RefreshResult = {
  ok: boolean;
  command: string;
  output: string;
  refreshedAt: string;
};
