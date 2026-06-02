# HANDOFF CURRENT STATE

## Project

- Name: `margin-loan-research`
- Path: `C:\Projects\margin-loan-research`

## Current status

- Local-first Data Core MVP is working.
- Binance `available-inventory` snapshots are collected into `margin_pool_snapshots`.
- Legacy `pool_metrics` are still calculated per snapshot block.
- Milestone `v0.3` is now implemented: Spot USDT prices + Derived Borrow Pressure Metrics.
- Milestone `Backend API Scanner v0.1` is implemented as a read-only FastAPI API.
- Next milestone: API verification and UI/dashboard planning, if needed.

## v0.3 changes

- Added direct spot USDT price collection from Binance public spot endpoint:
  - `GET /api/v3/ticker/price`
- Added table `spot_price_snapshots`.
- Added table `borrow_pressure_metrics`.
- Added runtime schema bootstrap in the collector so new tables are created on existing databases without rebuilding the container.
- Added collector integration to:
  1. collect inventory
  2. collect direct spot `ASSETUSDT` prices when enabled
  3. calculate borrow-pressure metrics for `15m`, `30m`, `1h`, `4h`
- Added `--health-report` output for:
  - `spot_price_snapshots`
  - `borrow_pressure_metrics`
  - latest blocks by timeframe
  - top Borrow Pressure USDT / %
  - top Recovery USDT / %

## v0.3 verified

- `python -m collector.main --once` completed successfully.
- `inventory fetched=414 inserted=414`.
- `spot_prices fetched=664 inserted=664`.
- `borrow_pressure_metrics calculated=1656`.
- Latest calculated block:
  - `15m`: 414 rows, 413 price_available, 1 price_unavailable.
  - `30m`: 414 rows, 413 price_available, 1 price_unavailable.
  - `1h`: 414 rows, 413 price_available, 1 price_unavailable.
  - `4h`: 414 rows, 413 price_available, 1 price_unavailable.
- The only asset without a direct spot price is `USDT`.
- Top Borrow Pressure USDT now returns rows.
- Example top `15m` Borrow Pressure USDT:
  - `USDC` approximately 2.61M USDT.
  - `XRP` approximately 571K USDT.
  - `BTC` approximately 514K USDT.
  - `TON` approximately 446K USDT.
  - `ETH` approximately 276K USDT.
- USDT valuation uses only direct spot `ASSETUSDT` prices.
- Futures prices are not used.
- Synthetic prices and indirect conversion are not used.
- Scanner note: stablecoins can appear in TOP results, so Backend/API/UI should support excluding stablecoins.
- Next milestone: `Backend API Scanner v0.1`.

## Backend API Scanner v0.1

Implemented files:

- `api/__init__.py`
- `api/main.py`
- `api/db.py`
- `api/settings.py`
- `api/schemas.py`
- `api/scanner.py`
- `smoke_check.py`
- `collector/requirements.txt`
- `README.md`
- `HANDOFF_CURRENT_STATE.md`

Implemented endpoints:

- `GET /health`
- `GET /api/overview`
- `GET /api/scanner/latest`
- `GET /api/assets`
- `GET /api/assets/{asset}/metrics-history`
- `GET /api/assets/{asset}/pool-history`

API rules:

- Read-only FastAPI API over existing PostgreSQL tables.
- DB connections use PostgreSQL `default_transaction_read_only=on`.
- No frontend, dashboard, Telegram, alerts, AI classification, Coinglass, z-score, anomaly score, or Binance write calls.
- No borrow, repay, or trading actions.
- No collector logic changes.
- No DB schema migrations.
- `.env` was not changed.

Scanner behavior:

- Supported timeframes: `15m`, `30m`, `1h`, `4h`.
- Supported metrics:
  - `borrow_pressure_usdt`
  - `borrow_pressure_percent`
  - `recovery_usdt`
  - `recovery_percent`
- `GET /api/scanner/latest` uses only the latest `calculated_at` block for the selected timeframe.
- Scanner default: `tf=15m`, `metric=borrow_pressure_usdt`, `limit=20`, `exclude_stables=true`.
- Stable filter is response/query level only and never deletes or changes raw DB data.
- Stable assets: `USDT`, `USDC`, `FDUSD`, `TUSD`, `DAI`, `USTC`.

Serialization:

- Decimal values are serialized as strings.
- Timestamps are returned as UTC ISO strings ending with `Z`.
- API responses are research metrics, not trading signals.

Assumptions:

- Existing v0.3 tables are present and populated by the collector.
- API runs locally from the same `.venv` and reads the same PostgreSQL settings as the collector.
- `collector/requirements.txt` is the project dependency file for this milestone.

Limitations:

- API is not Dockerized in this milestone.
- No auth layer yet.
- No pagination cursor yet; endpoints use bounded `limit` query params.
- No frontend/UI yet.

Commands run:

- `git status --short` -> clean working tree before changes.
- `git diff --name-only` -> clean working tree before changes.
- `pip install -r collector\requirements.txt` -> installed FastAPI/Uvicorn dependencies.
- `python -m compileall .` -> passed.
- `python smoke_check.py` -> passed.
- FastAPI `TestClient` runtime checks against local PostgreSQL -> passed for:
  - `/health`
  - `/api/overview`
  - `/api/scanner/latest?tf=15m&metric=borrow_pressure_usdt&limit=5`
  - `/api/assets?limit=5`
  - `/api/assets/BTC/metrics-history?tf=15m&limit=5`
  - `/api/assets/BTC/pool-history?limit=5`

## New tables

### `spot_price_snapshots`

- Stores direct spot `ASSETUSDT` prices only.
- Important fields:
  - `asset`
  - `symbol`
  - `price_usdt`
  - `collected_at`
  - `source`
  - `raw_json`

### `borrow_pressure_metrics`

- Stores derived research metrics for:
  - `15m`
  - `30m`
  - `1h`
  - `4h`
- Important fields:
  - `current_available_inventory`
  - `previous_available_inventory`
  - `net_pool_change_units`
  - `net_pool_change_percent`
  - `borrow_pressure_units`
  - `borrow_pressure_percent`
  - `borrow_pressure_usdt`
  - `recovery_units`
  - `recovery_percent`
  - `recovery_usdt`
  - `spot_price_usdt`
  - `price_symbol`
  - `price_available`
  - `current_snapshot_at`
  - `previous_snapshot_at`
  - `calculated_at`

## Borrow-pressure valuation rules

- Borrow pressure is inferred from a drop in available inventory.
- Recovery is inferred from a rise in available inventory.
- USDT valuation uses only direct spot `ASSETUSDT` prices.
- Futures prices are not used.
- Synthetic or indirect conversion is not used.
- If a direct spot pair is missing:
  - `price_available=false`
  - `borrow_pressure_usdt=NULL`
  - `recovery_usdt=NULL`
  - percent metrics can still exist

## New env

- `SPOT_PRICE_COLLECTION_MODE=scheduled`

Related existing env:

- `COLLECT_MARGIN_ASSETS=false`
- `PRICE_COLLECTION_MODE=scheduled`
- `SCHEDULER_MODE=aligned`
- `ALIGNMENT_MINUTES=15`
- `COLLECTION_DELAY_SECONDS=20`

## Current architecture

- Local Python collector from `.venv`
- PostgreSQL in Docker
- No web dashboard
- No backend API yet
- No Telegram integration
- No trading / borrow / repay actions

## Operational commands

Activate venv:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start PostgreSQL:

```powershell
docker compose up -d postgres
```

Run one cycle:

```powershell
python -m collector.main --once
```

Run loop:

```powershell
python -m collector.main --loop
```

Run health report:

```powershell
python -m collector.main --health-report
```

Open psql:

```powershell
docker compose exec postgres psql -U margin_user -d margin_research
```

## Verification SQL

```sql
SELECT COUNT(*) FROM margin_pool_snapshots;
SELECT COUNT(*) FROM pool_metrics;
SELECT COUNT(*) FROM spot_price_snapshots;
SELECT COUNT(*) FROM borrow_pressure_metrics;
```

```sql
SELECT asset, symbol, price_usdt, collected_at
FROM spot_price_snapshots
ORDER BY collected_at DESC, asset
LIMIT 20;
```

```sql
SELECT timeframe, asset, borrow_pressure_units, borrow_pressure_percent, borrow_pressure_usdt, recovery_usdt, price_available, current_snapshot_at
FROM borrow_pressure_metrics
ORDER BY calculated_at DESC, timeframe, borrow_pressure_usdt DESC NULLS LAST
LIMIT 40;
```

## Known non-blocking issue

- `GET /sapi/v1/margin/allAssets` can still return HTTP 400 / `-2014` in some setups.
- This remains non-critical because the main collector value is `available-inventory`.
- `COLLECT_MARGIN_ASSETS=false` stays the recommended default.

## Constraints

- Do not commit `.env`.
- Do not commit `.venv`, `data/`, or `backups/`.
- Do not expose API secrets in logs or docs.
- Do not add trading behavior in this repository.
