export type FundPoint = {
  scrapedDate: string;
  oldDate: string;
  oldPrice: number;
  newDate: string;
  newPrice: number;
  priceDifference: number;
  priceGrowth: number;
};

export type FundSeries = {
  code: string;
  name: string;
  file: string;
  observations: number;
  latest: FundPoint | null;
  points: FundPoint[];
};

export type AnalysisFund = {
  name: string;
  file: string;
  observations: number;
  latest_date: string;
  latest_price: number;
  latest_period_return_pct: number;
  one_year_return_pct: number;
  recent_return_pct: number;
  short_period_volatility_pct: number;
  score: number;
  opportunity: string;
  allocation_lkr: number;
};

export type AnalysisPayload = {
  budget_lkr: number;
  risk_profile: string;
  recommended_funds: string[];
  generated_from: string;
  funds: AnalysisFund[];
};

export type DashboardData = {
  refreshedAt: string;
  funds: FundSeries[];
  analysis: AnalysisPayload | null;
  recommendationText: string | null;
};

export type RefreshResult = {
  ok: boolean;
  command: string;
  output: string;
  refreshedAt: string;
};
