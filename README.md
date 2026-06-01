# margin-loan-research

Local-first Data Core MVP для збору Binance Margin Available Inventory (Available Pool) у PostgreSQL.

## MVP scope

- Collector запускається локально через `.venv`.
- PostgreSQL працює в Docker.
- Головна цінність: `available-inventory` snapshots + `pool_metrics`.
- `price_klines` — допоміжний кеш (опційно).
- Немає web dashboard, backend API, Telegram, trading/borrow/repay.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r collector\requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres
python -m collector.main --once
```

## Основні режими запуску

Один цикл:
```powershell
python -m collector.main --once
```

Loop режим:
```powershell
python -m collector.main --loop
```

Health/report:
```powershell
python -m collector.main --health-report
```

## Конфігурація (.env)

Базові:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- `WATCHLIST_ASSETS`, `KLINE_INTERVAL`, `POOL_TYPE`

Collector v0.2:
- `COLLECTOR_INTERVAL_SECONDS=900`
- `COLLECT_MARGIN_ASSETS=false`
- `PRICE_COLLECTION_MODE=scheduled` (`scheduled` або `disabled`)
- `SCHEDULER_MODE=aligned` (`aligned` або `interval`)
- `ALIGNMENT_MINUTES=15`
- `COLLECTION_DELAY_SECONDS=20`

Рекомендований блок `.env.example` (без secrets):

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
SCHEDULER_MODE=aligned
ALIGNMENT_MINUTES=15
COLLECTION_DELAY_SECONDS=20
```

## Пояснення v0.2

### `COLLECT_MARGIN_ASSETS`
- `false` (default): не викликає `/sapi/v1/margin/allAssets`.
- `true`: викликає `allAssets`, але його помилка non-critical.

Це прибирає перехід у `partial_success` через non-blocking `allAssets`.

### `PRICE_COLLECTION_MODE`
- `disabled`: collector не збирає klines (це не помилка).
- `scheduled`: збір klines працює як раніше.

### `SCHEDULER_MODE`
- `interval`: старий режим — sleep після завершення циклу.
- `aligned`: запуск на часовій сітці.
  - Для `ALIGNMENT_MINUTES=15`, `COLLECTION_DELAY_SECONDS=20`:
    - `00:00:20`, `00:15:20`, `00:30:20`, `00:45:20`

У логах:
- `scheduler_mode`
- `next_run_at`
- `alignment_minutes`
- `collection_delay_seconds`
- `actual_started_at`
- `delay_from_schedule_seconds`

## Non-blocking issue

`GET /sapi/v1/margin/allAssets` може повертати HTTP 400 (`code=-2014`) у певному оточенні.
Для MVP це non-blocking, бо основний endpoint `available-inventory` працює.
За замовчуванням `COLLECT_MARGIN_ASSETS=false`.

## SQL перевірки

```sql
SELECT collector_name, started_at, finished_at, status, records_collected, error_message
FROM collector_runs
ORDER BY started_at DESC
LIMIT 10;

SELECT COUNT(*) FROM symbols;
SELECT COUNT(*) FROM assets;
SELECT COUNT(*) FROM margin_pool_snapshots;
SELECT COUNT(*) FROM price_klines;
SELECT COUNT(*) FROM pool_metrics;
```

Часові блоки snapshots:

```sql
SELECT date_trunc('minute', collected_at) AS minute, COUNT(*) AS rows
FROM margin_pool_snapshots
GROUP BY minute
ORDER BY minute DESC
LIMIT 10;
```

Кількість snapshots по asset:

```sql
SELECT asset, COUNT(*) AS snapshots, MIN(collected_at) AS first_seen, MAX(collected_at) AS last_seen
FROM margin_pool_snapshots
GROUP BY asset
ORDER BY snapshots DESC
LIMIT 20;
```

## Top pool changes report (research-only)

Це технічний research-report по змінах Available Pool, не торгові сигнали.

Top decreases:

```sql
SELECT asset, available_inventory, previous_available_inventory, pool_change, pool_change_percent, pool_decrease, created_at
FROM pool_metrics
WHERE previous_available_inventory IS NOT NULL
ORDER BY pool_decrease DESC, created_at DESC
LIMIT 20;
```

Top recoveries:

```sql
SELECT asset, available_inventory, previous_available_inventory, pool_change, pool_change_percent, pool_recovery, created_at
FROM pool_metrics
WHERE previous_available_inventory IS NOT NULL
ORDER BY pool_recovery DESC, created_at DESC
LIMIT 20;
```

Top absolute percent changes:

```sql
SELECT asset, pool_change_percent, available_inventory, previous_available_inventory, created_at
FROM pool_metrics
WHERE previous_available_inventory IS NOT NULL
  AND pool_change_percent IS NOT NULL
ORDER BY ABS(pool_change_percent) DESC, created_at DESC
LIMIT 20;
```

## Безпека

- Не комітити `.env`, `.venv`, `data/`, backups, logs.
- Не логувати API secret.
- Працювати тільки з офіційними Binance endpoints.
