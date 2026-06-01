# HANDOFF CURRENT STATE

## Проєкт
- Назва: `margin-loan-research`
- Шлях: `C:\Projects\margin-loan-research`

## Current status
- Local-first Data Core MVP is working.
- Binance available-inventory is collected cyclically.
- `margin_pool_snapshots` and `pool_metrics` accumulate over time.
- `allAssets` 400 remains non-blocking.
- Next milestone: Data Collection Hardening v0.2.

## Latest loop test results
- Extended loop test підтвердив стабільне накопичення Binance Available Inventory.
- `COUNT(margin_pool_snapshots)=5796`.
- `COUNT(pool_metrics)=5796`.
- Це відповідає 14 циклам по 414 assets: `414 * 14 = 5796`.
- У `margin_pool_snapshots` видно 14 часових блоків по 414 rows кожен.
- Перший зафіксований блок: `2026-06-01 12:58 UTC` — 414 rows.
- Останній зафіксований блок: `2026-06-01 16:32 UTC` — 414 rows.
- По кожному asset у вибірці `snapshots=14`.
- Це підтверджує, що snapshots накопичуються, не перезаписуються і unique constraints не блокують нові записи.
- `pool_metrics` також накопичуються синхронно з snapshots.
- Local-first Data Core MVP вважаємо підтвердженим.

## Поточна архітектура
Local-first MVP:
- Python collector запускається локально у VS Code через `.venv`.
- PostgreSQL працює у Docker.
- Web dashboard ще не реалізований.
- Backend API ще не реалізований.
- Telegram ще не реалізований.
- Trading / borrow / repay дій немає і не повинно бути.
- Основна цінність collector-а: збір Binance Margin Available Inventory / Available Pool.
- Price klines збираються як допоміжний кеш, не як головна цінність MVP.

## Поточні робочі компоненти
- `.venv` створений і працює.
- PostgreSQL Docker container працює.
- Таблиці створені:
  - `assets`
  - `symbols`
  - `margin_pool_snapshots`
  - `price_klines`
  - `pool_metrics`
  - `collector_runs`
- `symbols` створюються з `WATCHLIST_ASSETS`.
- `price_klines` збираються.
- Binance `available-inventory` signed request працює після додавання `BINANCE_API_KEY/BINANCE_API_SECRET` у локальний `.env`.
- `margin_pool_snapshots` заповнюється.
- `pool_metrics` рахується.
- Collector не падає через помилки margin endpoint-ів, а записує `partial_success`.

## Останні підтверджені результати
- `inventory fetched=414 inserted=414`
- `pool_metrics calculated=414`
- `COUNT(margin_pool_snapshots)=414`
- `COUNT(pool_metrics)=414`
- `price_klines` також заповнюється.
- Для першого snapshot у `pool_metrics`:
  - `previous_available_inventory = NULL`
  - `pool_change = NULL`
  - `pool_change_percent = NULL`
  - це прийнято як коректна поведінка першого спостереження.
- `run_status=partial_success`, бо `allAssets` повертає 400, але це не блокує inventory та klines.

## Відоме non-blocking issue
`GET /sapi/v1/margin/allAssets` продовжує повертати HTTP 400 Binance code `-2014` (`"API-key format invalid"`).

Важливе уточнення:
- Для `allAssets` public request код не відправляє `X-MBX-APIKEY`, якщо ключ порожній.
- Діагностика показувала `sent_api_key_header=False` та `signed=False`.
- Це issue зараз non-blocking, бо основний endpoint `available-inventory` працює.
- У наступному milestone `allAssets` треба зробити optional/disabled by default, щоб не переводити успішні inventory runs у `partial_success`.
- Watchlist symbols формуються з `.env`, тому `allAssets` не критичний для поточного MVP.

## Поточний пріоритет
Дати collector-у попрацювати в loop mode для перевірки накопичення `margin_pool_snapshots` блоками кожні 15 хвилин.

## Loop режим
- Команда: `python -m collector.main --loop`
- Інтервал: `COLLECTOR_INTERVAL_SECONDS=900`
- Один цикл кожні 15 хвилин.

## Операційні команди
Activate venv:
```powershell
.\.venv\Scripts\Activate.ps1
```

Start PostgreSQL:
```powershell
docker compose up -d postgres
```

Run one collector cycle:
```powershell
python -m collector.main --once
```

Run collector loop:
```powershell
python -m collector.main --loop
```

Open psql:
```powershell
docker compose exec postgres psql -U margin_user -d margin_research
```

Disable psql pager:
```sql
\pset pager off
```

## Корисні SQL-перевірки
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

SELECT
  date_trunc('minute', collected_at) AS minute,
  COUNT(*) AS rows
FROM margin_pool_snapshots
GROUP BY minute
ORDER BY minute DESC
LIMIT 10;

SELECT
  asset,
  COUNT(*) AS snapshots,
  MIN(collected_at) AS first_seen,
  MAX(collected_at) AS last_seen
FROM margin_pool_snapshots
GROUP BY asset
ORDER BY snapshots DESC
LIMIT 20;

SELECT
  asset,
  pool_type,
  available_inventory,
  previous_available_inventory,
  pool_change,
  pool_change_percent,
  pool_decrease,
  pool_recovery,
  created_at
FROM pool_metrics
WHERE previous_available_inventory IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;
```

## Що перевірити після 1-2 годин loop mode
1. `COUNT(*) FROM margin_pool_snapshots` зростає.
2. `COUNT(*) FROM pool_metrics` зростає.
3. У `date_trunc('minute', collected_at)` видно блоки приблизно по 414 рядків на цикл.
4. Для кожного asset кількість snapshots стає 2, 3, 4 і більше.
5. У `pool_metrics` для наступних циклів з’являється `previous_available_inventory IS NOT NULL`.

## Наступний milestone
Data Collection Hardening v0.2:
1. Зробити `allAssets` optional або disabled by default.
2. Додати `PRICE_COLLECTION_MODE=disabled/scheduled`.
3. Зробити Available Pool основним collector режимом.
4. Додати health/report script або команду для SQL-перевірок.
5. Додати top pool changes report.
6. Оновити `README.md`.
7. Підтримувати `HANDOFF_CURRENT_STATE.md` актуальним.

## Обмеження та безпека
- Не змінювати код collector-а в межах цього handoff.
- Не змінювати schema БД.
- Не змінювати `docker-compose.yml`.
- Не запускати destructive DB commands.
- Не додавати secrets.
- Не копіювати в цей файл `BINANCE_API_KEY`, `BINANCE_API_SECRET` або вміст `.env`.
- `.env`, `.venv`, `data/`, backups мають залишатись поза git.
