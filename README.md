# margin-loan-research

Локальний MVP-проєкт для збору Binance margin available inventory та spot klines у PostgreSQL.

## 1. Що це за проєкт

`margin-loan-research` — це Local Data Core MVP: локальний Python collector + PostgreSQL у Docker.

## 2. Мета MVP

Збирати:
- `margin/allAssets`
- `margin/available-inventory` (type=`MARGIN`)
- `spot klines` для watchlist активів

І зберігати ці дані у локальну БД для подальших досліджень.

## 3. Чому збираємо Available Inventory, а не Borrow/Repay

У цьому milestone ми будуємо безпечний read-only data core без торгових дій і без неофіційних endpoint-ів. `available-inventory` дає достатній сигнал для стартового аналізу пулу ліквідності.

## 4. Чому Available Inventory — це proxy, а не точний Borrow/Repay

Зміни `Available Pool` не дорівнюють напряму borrow/repay. На них можуть впливати різні фактори (поповнення пулу, внутрішні зміни ліквідності). Тому в БД використані назви:
- `pool_change`
- `borrow_pressure_proxy`
- `repay_or_refill_proxy`

## 5. Як створити проєкт у C:\Projects\margin-loan-research

1. Створити директорію (якщо ще не існує):  
   `mkdir C:\Projects\margin-loan-research`
2. Відкрити у VS Code цю папку.

## 6. Як створити Python virtual environment

```powershell
python -m venv .venv
```

## 7. Як активувати venv у PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

## 8. Як встановити залежності

```powershell
pip install -r collector\requirements.txt
```

## 9. Як створити .env з .env.example

```powershell
Copy-Item .env.example .env
```

Потім відредагувати `.env` і задати реальні значення за потреби.

## 10. Як запустити PostgreSQL

```powershell
docker compose up -d postgres
```

## 11. Як перевірити, що postgres працює

```powershell
docker compose ps
```

## 12. Як запустити collector один раз

```powershell
python -m collector.main --once
```

## 13. Як запустити collector у loop режимі

```powershell
python -m collector.main --loop
```

## 14. Як подивитись таблиці через psql

```powershell
docker compose exec postgres psql -U margin_user -d margin_research
```

## 15. SQL-запити для перевірки

```sql
SELECT * FROM collector_runs ORDER BY started_at DESC LIMIT 5;
SELECT COUNT(*) FROM assets;
SELECT COUNT(*) FROM margin_pool_snapshots;
SELECT COUNT(*) FROM price_klines;
SELECT COUNT(*) FROM pool_metrics;
```

## 16. Як зробити backup

```powershell
.\scripts\backup_db.ps1
```

## 17. Як зробити restore

```powershell
.\scripts\restore_db.ps1 -BackupPath .\data\backups\backup_YYYY-MM-DD_HH-mm.sql
```

Скрипт запитає підтвердження `YES`, бо restore може перезаписати дані.

## 18. Що входить у цей milestone

- PostgreSQL у Docker (`docker-compose.yml`, один сервіс `postgres`)
- SQL schema init (`database/init/001_init.sql`)
- Локальний Python collector (`--once`, `--loop`)
- Збір `allAssets`, `available-inventory`, `klines`
- Розрахунок похідних `pool_metrics`
- Запис кожного запуску у `collector_runs`
- Backup/restore PowerShell scripts

## 19. Що НЕ входить у цей milestone

- Web dashboard
- Backend API
- Telegram
- Trading API / відкриття угод
- Автоматичні сигнали
- AI LONG/SHORT класифікація
- Coinglass інтеграція
- Контейнеризація collector-а

## 20. Наступний логічний milestone

- Додати базовий аналітичний шар над зібраними таблицями:
- batch SQL views для трендів `available_inventory`
- первинні алерти на різкі зміни `borrow_pressure_proxy`
- підготовка контракту для майбутнього API (без реалізації API)

## Архітектура MVP

- Локально (VS Code): Python collector у `.venv`
- Docker: тільки PostgreSQL
- Дані:
- `assets`
- `symbols`
- `margin_pool_snapshots`
- `price_klines`
- `pool_metrics`
- `collector_runs`

## Нотатки по унікальності snapshot-ів

Для `margin_pool_snapshots` не додано жорсткий unique `(asset, pool_type, binance_update_time)`, щоб не блокувати корисні повторні snapshots, якщо `binance_update_time` не змінюється. Замість цього використовується часовий ряд snapshots і похідні метрики по `collected_at`.

## Порт PostgreSQL

Використано `5432:5432`. Якщо локальний `5432` зайнятий, змініть у `docker-compose.yml` на `5433:5432` і в `.env` встановіть `POSTGRES_PORT=5433`.

## Чи потрібні Binance API key/secret для available-inventory

Так, для `GET /sapi/v1/margin/available-inventory` потрібні ключ/секрет і signed request. Collector це враховує і логікує зрозумілу помилку, якщо ключі відсутні або endpoint недоступний.

## Безпека

- Не комітити `.env`, `.venv`, `data/`, backup-и, логи.
- Не логувати API key/secret.
- Використовувати лише офіційні Binance endpoints.

## Troubleshooting Binance

- `GET /sapi/v1/margin/allAssets` викликається як чистий MARKET_DATA запит (без `timestamp/signature`).
- У деяких оточеннях endpoint може повертати `400/401/403/451` (регіон/IP/мережеві обмеження).
- Якщо `allAssets` недоступний, collector не падає повністю і продовжує збір `price_klines`.
- `GET /sapi/v1/margin/available-inventory` є USER_DATA endpoint:
- потрібні `BINANCE_API_KEY` і `BINANCE_API_SECRET`;
- виконується signed request (`type`, `timestamp`, `recvWindow`, `signature`).
- Якщо ключів нема, inventory пропускається (`skipped`), але `price_klines` все одно збираються.

Приклад прямої перевірки `allAssets` у PowerShell:

```powershell
Invoke-WebRequest -Method GET -Uri "https://api.binance.com/sapi/v1/margin/allAssets"
```
