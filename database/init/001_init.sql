CREATE TABLE IF NOT EXISTS assets (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL UNIQUE,
  is_borrowable BOOLEAN,
  is_mortgageable BOOLEAN,
  user_min_borrow NUMERIC,
  user_min_repay NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL,
  symbol TEXT NOT NULL UNIQUE,
  quote_asset TEXT NOT NULL,
  market_type TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS margin_pool_snapshots (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL,
  pool_type TEXT NOT NULL,
  available_inventory NUMERIC NOT NULL,
  binance_update_time TIMESTAMPTZ,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT NOT NULL,
  raw_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_margin_pool_asset_type_time
  ON margin_pool_snapshots(asset, pool_type, collected_at DESC);

CREATE TABLE IF NOT EXISTS price_klines (
  id BIGSERIAL PRIMARY KEY,
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  open_time TIMESTAMPTZ NOT NULL,
  close_time TIMESTAMPTZ NOT NULL,
  open NUMERIC NOT NULL,
  high NUMERIC NOT NULL,
  low NUMERIC NOT NULL,
  close NUMERIC NOT NULL,
  volume NUMERIC NOT NULL,
  quote_volume NUMERIC NOT NULL,
  number_of_trades INTEGER NOT NULL,
  taker_buy_base_volume NUMERIC NOT NULL,
  taker_buy_quote_volume NUMERIC NOT NULL,
  source TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(symbol, interval, open_time)
);

CREATE TABLE IF NOT EXISTS pool_metrics (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL,
  pool_type TEXT NOT NULL,
  "timestamp" TIMESTAMPTZ NOT NULL,
  available_inventory NUMERIC NOT NULL,
  previous_available_inventory NUMERIC,
  pool_change NUMERIC,
  pool_change_percent NUMERIC,
  pool_decrease NUMERIC NOT NULL,
  pool_recovery NUMERIC NOT NULL,
  borrow_pressure_proxy NUMERIC NOT NULL,
  repay_or_refill_proxy NUMERIC NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pool_metrics_asset_type_ts
  ON pool_metrics(asset, pool_type, "timestamp");

CREATE TABLE IF NOT EXISTS spot_price_snapshots (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL,
  symbol TEXT NOT NULL,
  price_usdt NUMERIC NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT NOT NULL,
  raw_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spot_price_snapshots_asset_time
  ON spot_price_snapshots(asset, collected_at DESC);

CREATE INDEX IF NOT EXISTS idx_spot_price_snapshots_symbol_time
  ON spot_price_snapshots(symbol, collected_at DESC);

CREATE TABLE IF NOT EXISTS borrow_pressure_metrics (
  id BIGSERIAL PRIMARY KEY,
  asset TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  current_available_inventory NUMERIC NOT NULL,
  previous_available_inventory NUMERIC NOT NULL,
  net_pool_change_units NUMERIC,
  net_pool_change_percent NUMERIC,
  borrow_pressure_units NUMERIC NOT NULL,
  borrow_pressure_percent NUMERIC,
  borrow_pressure_usdt NUMERIC,
  recovery_units NUMERIC NOT NULL,
  recovery_percent NUMERIC,
  recovery_usdt NUMERIC,
  spot_price_usdt NUMERIC,
  price_symbol TEXT,
  price_available BOOLEAN NOT NULL DEFAULT FALSE,
  current_snapshot_at TIMESTAMPTZ NOT NULL,
  previous_snapshot_at TIMESTAMPTZ NOT NULL,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_borrow_pressure_asset_tf_calc
  ON borrow_pressure_metrics(asset, timeframe, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_borrow_pressure_tf_calc
  ON borrow_pressure_metrics(timeframe, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_borrow_pressure_tf_usdt
  ON borrow_pressure_metrics(timeframe, borrow_pressure_usdt DESC);

CREATE INDEX IF NOT EXISTS idx_borrow_pressure_tf_percent
  ON borrow_pressure_metrics(timeframe, borrow_pressure_percent DESC);

CREATE INDEX IF NOT EXISTS idx_borrow_pressure_tf_recovery_usdt
  ON borrow_pressure_metrics(timeframe, recovery_usdt DESC);

CREATE TABLE IF NOT EXISTS collector_runs (
  id BIGSERIAL PRIMARY KEY,
  collector_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  records_collected INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  raw_error JSONB
);

CREATE INDEX IF NOT EXISTS idx_collector_runs_started_at
  ON collector_runs(started_at DESC);
