# margin-loan-research

Local-first research collector for Binance Margin available inventory. The project stores raw inventory snapshots in PostgreSQL, derives pool-change metrics, and now derives research-only borrow-pressure metrics valued in USDT from direct spot `ASSETUSDT` prices.

## Scope

- Local Python collector run from `.venv`.
- PostgreSQL in Docker.
- Core data:
  - `margin_pool_snapshots`
  - `pool_metrics`
  - `spot_price_snapshots`
  - `borrow_pressure_metrics`
- Optional helper cache:
  - `price_klines`
- Out of scope:
  - web dashboard
  - Telegram
  - trading / borrow / repay actions

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r collector\requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres
python -m collector.main --once
```

## Run modes

One cycle:

```powershell
python -m collector.main --once
```

Loop mode:

```powershell
python -m collector.main --loop
```

Health report:

```powershell
python -m collector.main --health-report
```

## Configuration

Recommended `.env.example` block:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=margin_research
POSTGRES_USER=margin_user
POSTGRES_PASSWORD=change_me

BINANCE_API_KEY=
BINANCE_API_SECRET=

WATCHLIST_ASSETS=BTC,ETH,ARKM
KLINE_INTERVAL=15m
COLLECTOR_INTERVAL_SECONDS=900
POOL_TYPE=MARGIN
COLLECT_MARGIN_ASSETS=false
PRICE_COLLECTION_MODE=scheduled
SPOT_PRICE_COLLECTION_MODE=scheduled
SCHEDULER_MODE=aligned
ALIGNMENT_MINUTES=15
COLLECTION_DELAY_SECONDS=20
```

Key flags:

- `COLLECT_MARGIN_ASSETS=false`: skip `/sapi/v1/margin/allAssets`. This is non-critical for the MVP.
- `PRICE_COLLECTION_MODE=disabled|scheduled`: control `price_klines` collection.
- `SPOT_PRICE_COLLECTION_MODE=disabled|scheduled`: control direct spot USDT snapshot collection from `/api/v3/ticker/price`.
- `SCHEDULER_MODE=interval|aligned`: legacy interval sleeping or aligned time-grid scheduling.

## Borrow Pressure Proxy

The collector treats a decrease in available inventory as a borrow-pressure proxy:

- `borrow_pressure_units = max(0, previous_pool - current_pool)`
- `recovery_units = max(0, current_pool - previous_pool)`

Research timeframes:

- `15m`
- `30m`
- `1h`
- `4h`

USDT valuation rules:

- Only direct spot `ASSETUSDT` prices are used.
- Futures prices are not used.
- Synthetic or indirect conversion paths are not used.
- If there is no direct spot pair, `price_available=false` and `borrow_pressure_usdt` / `recovery_usdt` stay `NULL`.

This project produces research metrics, not trading signals.

## Collector v0.3 flow

After a successful `available-inventory` collection cycle:

1. Insert `margin_pool_snapshots`.
2. If `SPOT_PRICE_COLLECTION_MODE=scheduled`, fetch `/api/v3/ticker/price` and store direct `*USDT` pairs in `spot_price_snapshots`.
3. Update legacy `pool_metrics`.
4. Calculate `borrow_pressure_metrics` for `15m`, `30m`, `1h`, `4h`.

The collector logs:

- `spot_prices fetched=N inserted=N`
- `borrow_pressure_metrics calculated=N`
- `calculated_by_timeframe={15m: N, 30m: N, 1h: N, 4h: N}`
- `price_unavailable_count=N`

If history is still missing for `30m`, `1h`, or `4h`, low or zero counts are expected.

## Health report

`python -m collector.main --health-report` now shows:

- row counts for `margin_pool_snapshots`, `pool_metrics`, `spot_price_snapshots`, `borrow_pressure_metrics`
- latest snapshot blocks
- latest `borrow_pressure_metrics` block per timeframe
- top Borrow Pressure USDT by timeframe
- top Borrow Pressure % by timeframe
- top Recovery USDT by timeframe
- top Recovery % by timeframe

Expected report shape:

```text
health_report: research metrics only, not trading signals
health_report: spot_price_snapshots_count=12345
health_report: borrow_pressure_metrics_count=6789
health_report: latest borrow_pressure_metrics blocks by timeframe
borrow_pressure_block: {'timeframe': '15m', 'latest_calculated_at': ..., 'rows_at_latest': 414}
health_report: top_borrow_pressure_usdt timeframe=15m
top_borrow_pressure_usdt: {'asset': 'BTC', 'borrow_pressure_usdt': ..., ...}
health_report: top_borrow_pressure_percent timeframe=15m
health_report: top_recovery_usdt timeframe=15m
health_report: top_recovery_percent timeframe=15m
```

## Read-only Backend API v0.1

The FastAPI API exposes existing PostgreSQL research data only. It does not call Binance write endpoints, does not borrow, repay, trade, alert, classify, or mutate raw collector tables.

Install dependencies:

```powershell
pip install -r collector\requirements.txt
```

Run locally:

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `GET /api/overview`
- `GET /api/scanner/latest`
- `GET /api/assets`
- `GET /api/assets/{asset}/metrics-history`
- `GET /api/assets/{asset}/pool-history`

Example requests:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/overview
curl "http://127.0.0.1:8000/api/scanner/latest?tf=15m&metric=borrow_pressure_usdt&limit=20&exclude_stables=true"
curl "http://127.0.0.1:8000/api/scanner/latest?tf=1h&metric=borrow_pressure_percent&limit=20"
curl "http://127.0.0.1:8000/api/assets?exclude_stables=false&limit=500"
curl "http://127.0.0.1:8000/api/assets/BTC/metrics-history?tf=15m&limit=200"
curl "http://127.0.0.1:8000/api/assets/BTC/pool-history?limit=500"
```

Scanner defaults:

- `tf=15m`
- `metric=borrow_pressure_usdt`
- `limit=20`
- `exclude_stables=true`

Supported scanner metrics:

- `borrow_pressure_usdt`
- `borrow_pressure_percent`
- `recovery_usdt`
- `recovery_percent`

The scanner ranks only the latest calculated block for the selected timeframe. Stable assets excluded by default in scanner responses: `USDT`, `USDC`, `FDUSD`, `TUSD`, `DAI`, `USTC`.

JSON rules:

- Decimal values are returned as strings.
- Timestamps are returned as UTC ISO strings ending with `Z`.
- API output is research data, not trading signals.

## SQL checks

Collector runs:

```sql
SELECT collector_name, started_at, finished_at, status, records_collected, error_message
FROM collector_runs
ORDER BY started_at DESC
LIMIT 10;
```

Counts:

```sql
SELECT COUNT(*) FROM margin_pool_snapshots;
SELECT COUNT(*) FROM price_klines;
SELECT COUNT(*) FROM pool_metrics;
SELECT COUNT(*) FROM spot_price_snapshots;
SELECT COUNT(*) FROM borrow_pressure_metrics;
```

Latest spot prices:

```sql
SELECT asset, symbol, price_usdt, collected_at
FROM spot_price_snapshots
ORDER BY collected_at DESC, asset
LIMIT 20;
```

Latest borrow pressure by timeframe:

```sql
SELECT timeframe, asset, borrow_pressure_units, borrow_pressure_percent, borrow_pressure_usdt, price_available, current_snapshot_at
FROM borrow_pressure_metrics
ORDER BY calculated_at DESC, timeframe, borrow_pressure_usdt DESC NULLS LAST
LIMIT 40;
```

Top borrow pressure USDT for one timeframe:

```sql
SELECT asset, borrow_pressure_usdt, borrow_pressure_units, spot_price_usdt, current_snapshot_at
FROM borrow_pressure_metrics
WHERE timeframe = '15m'
  AND price_available = TRUE
ORDER BY borrow_pressure_usdt DESC
LIMIT 20;
```

## Safety

- Do not commit `.env`, `.venv`, `data/`, or `backups/`.
- Do not log API secrets.
- Use only official Binance endpoints.
