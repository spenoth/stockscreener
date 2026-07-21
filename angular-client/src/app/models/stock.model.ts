export interface Stock {
  symbol: string;
  exchange: string;
}

export interface SupertrendPath {
  timestamp?: string;
  path: number[];
  path_percent?: number[];
  endpoint_positive: boolean;
  mean_positive: boolean;
  endpoint?: number;
  mean?: number;
}

export interface SupertrendStats {
  total_signals: number;
  bmsb_above: number;
  bmsb_below_or_unknown: number;
}

export interface TradeMetric {
  timestamp: string;
  final_return: number;
  mean_return: number;
  mfe: number;
  mae: number;
  time_to_mfe: number;
  time_to_mae: number;
  recovery_factor: number | null;
  winner_final: boolean;
  winner_mean: boolean;
}

export interface SupertrendSummary {
  num_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  avg_mfe: number;
  avg_drawdown_winners: number;
  avg_drawdown_losers: number;
  expectancy: number;
}

export interface DrawdownPercentiles {
  '50%': number;
  '75%': number;
  '90%': number;
  '95%': number;
  '99%': number;
}

export interface MeanPathSummary {
  mean: number[];
  median: number[];
  std: number[];
  q25: number[];
  q75: number[];
  q10: number[];
  q90: number[];
}

export interface SupertrendAnalysisResponse {
  ticker?: string;
  timeframe?: string;
  max_hours?: number;
  stats?: SupertrendStats;
  paths: SupertrendPath[];
  metrics?: TradeMetric[];
  summary?: SupertrendSummary;
  drawdown_percentiles?: DrawdownPercentiles;
  mean_path?: MeanPathSummary;
}
