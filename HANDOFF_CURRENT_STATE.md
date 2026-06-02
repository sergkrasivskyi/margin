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
- Milestone `Collector UX / Health Report v0.3.1` is implemented.
- Milestone `Backend API Scanner v0.1.1` is implemented.
- Repo-level `AGENTS.md` project instructions are added for future Codex work.
- Milestone `Web Scanner MVP v0.2` is implemented as a static read-only FastAPI-served dashboard.
- Milestone `Web Scanner UX Polish v0.2.1` is implemented.
- Milestone `Reduce Codex sandbox/precheck friction on Windows` is implemented.
- Next milestone: continue scanner/API UX planning if needed.

## Reduce Codex sandbox/precheck friction on Windows

Changed files:

- `AGENTS.md`
- `.codex/config.toml`
- `HANDOFF_CURRENT_STATE.md`

Instruction/config changes:

- `AGENTS.md` now uses one combined git preflight command:
  `git --no-pager log --oneline --decorate -5; git status --short; git diff --name-only`
- `AGENTS.md` now says to request escalation once if a required read-only pre-check command fails because the native Windows sandbox cannot spawn the process.
- `AGENTS.md` now says fresh exact pre-check outputs provided in the current prompt can be treated as pre-check context unless files changed or a new check is required.
- Added project-level `.codex/config.toml` with conservative local settings:
  - `approval_policy = "on-request"`
  - `sandbox_mode = "workspace-write"`
  - Windows sandbox set to `elevated`
  - workspace-write network access disabled

Checks run:

- `git log --oneline --decorate -5; git status --short; git diff --name-only` initially hit a Windows sandbox spawn failure and was rerun once with escalation.
- Pre-check result before changes: HEAD `b252a5c Polish Web Scanner dashboard UX`; working tree clean.
- `python -m compileall api collector database scripts smoke_check.py` -> passed.
- `python smoke_check.py` -> passed; FastAPI TestClient emitted the known Starlette/httpx deprecation warning.

Unchanged:

- No application code changed.
- No API, collector, DB, web UI, or README behavior changed.
- No `.env`, `.venv/`, `data/`, `backups/`, secrets, credentials, tokens, or API keys were changed.
- No collector loop was run.
- No commit was made.

## Web Scanner UX Polish v0.2.1

Changed files:

- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `README.md`
- `HANDOFF_CURRENT_STATE.md`

UX changes:

- Timeframe, limit, and exclude-stables controls auto-refresh scanner summary data.
- Refresh button remains available for manual reload.
- Added visible loading indicator while summary data is fetched.
- Added helper text and tooltips explaining timeframe, limit, and exclude-stables controls.
- Added compact metric explanation section for Borrow Pressure and Recovery.
- Compact number formatting displays large Decimal strings as `K`, `M`, or `B` while preserving exact original values in tooltips.
- Timestamps display in compact UTC format while preserving full original values in tooltips.
- Scanner tables are more compact and keep sticky headers inside scrollable table containers.
- Asset buttons remain visually clickable and still load same-page drilldown tables.
- Added inline SVG favicon data URL to avoid browser `favicon.ico` 404.

Checks run:

- `python -m compileall api collector database scripts smoke_check.py` -> passed.
- `python smoke_check.py` -> passed; FastAPI TestClient emitted the known Starlette/httpx deprecation warning.
- `node --check web\app.js` -> passed.
- Local uvicorn HTTP verification -> passed for `GET /`, `GET /static/app.js`, and `GET /api/scanner/summary?tf=15m&limit=3&exclude_stables=true`.
- In-app browser verification was attempted but blocked by a Windows sandbox spawn error in the browser runtime.

Limitations:

- No charts.
- No frontend build system, npm, React, Vite, Next.js, or chart libraries.
- Number formatting is display-only and is not used for calculations.
- UI remains local and read-only.

Unchanged:

- No DB schema changes.
- Collector formulas were not changed.
- Binance endpoints were not changed.
- Scheduler behavior was not changed.
- API behavior and write behavior were not changed.
- No Telegram, alerts, AI classification, z-score, anomaly score, Coinglass, borrow, repay, or trading actions were added.
- `.env`, `.venv/`, `data/`, `backups/`, credentials, tokens, and API keys were not changed.

## Web Scanner MVP v0.2

Changed files:

- `api/main.py`
- `smoke_check.py`
- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `README.md`
- `HANDOFF_CURRENT_STATE.md`

UI routes:

- `GET /`
- `GET /static/app.js`
- `GET /static/styles.css`

API endpoints used by the UI:

- `GET /api/overview`
- `GET /api/scanner/summary`
- `GET /api/assets/{asset}/metrics-history`
- `GET /api/assets/{asset}/pool-history`

Implemented UI:

- Header with project name, API version, and freshness status.
- Data freshness block with stale warning or fresh status.
- Controls for timeframe, limit, exclude stables, and refresh.
- Four scanner tables:
  - Top Borrow Pressure USDT
  - Top Borrow Pressure %
  - Top Recovery USDT
  - Top Recovery %
- Clickable asset rows that load same-page recent metrics and pool history tables.
- Readable API error display.
- Decimal strings are displayed as strings; long values are shortened visually with full value in tooltip.

Limitations:

- No charts yet.
- No frontend build system, npm, React, Vite, Next.js, or chart libraries.
- UI is local and read-only.

Unchanged:

- No DB schema changes.
- Collector formulas were not changed.
- Binance endpoints were not changed.
- Scheduler behavior was not changed.
- API write behavior was not added.
- No Telegram, alerts, AI classification, z-score, anomaly score, Coinglass, borrow, repay, or trading actions were added.

Checks run:

- `git log --oneline --decorate -5` -> latest commit before changes: `6c572ac Add Codex project instructions`.
- `git status --short` -> clean working tree before changes.
- `git diff --name-only` -> clean working tree before changes.
- `python -m compileall api collector database scripts smoke_check.py` -> passed.
- `python smoke_check.py` -> passed; covers web root, static JS/CSS, API endpoints, and invalid scanner params.

## AGENTS.md project instructions

- Added repo-level `AGENTS.md` to keep stable project rules available across future Codex prompts.
- Covers project overview, architecture, safety rules, git pre-checks, verification commands, documentation expectations, and final response expectations.
- This was a docs/instructions-only update.
- No application code, collector logic, API behavior, DB schema, `.env`, secrets, `.venv/`, `data/`, or backups were changed.

## Backend API Scanner v0.1.1

Changed files:

- `api/main.py`
- `api/scanner.py`
- `api/schemas.py`
- `api/settings.py`
- `smoke_check.py`
- `README.md`
- `HANDOFF_CURRENT_STATE.md`

Endpoints changed or added:

- Added `GET /api/scanner/summary`.
- Updated `GET /api/overview` with `data_freshness`.
- Updated `GET /api/scanner/latest` with `data_freshness`.
- Kept `GET /health` lightweight.

Scanner summary behavior:

- Query params: `tf=15m`, `limit=20`, `exclude_stables=true`.
- Supported timeframes: `15m`, `30m`, `1h`, `4h`.
- Returns all four latest-block rankings in one response:
  - `top_borrow_pressure_usdt`
  - `top_borrow_pressure_percent`
  - `top_recovery_usdt`
  - `top_recovery_percent`
- Ranking items use the same DTO fields as `GET /api/scanner/latest`.
- Ranking logic reuses the same helper as `GET /api/scanner/latest`.

Data freshness behavior:

- Freshness fields:
  - `latest_metrics_calculated_at`
  - `latest_metrics_age_seconds`
  - `latest_snapshot_at`
  - `latest_snapshot_age_seconds`
  - `last_collector_run_status`
  - `last_collector_run_finished_at`
  - `is_data_stale`
  - `stale_after_seconds`
- Default stale threshold: `stale_after_seconds=1800`.
- Freshness uses UTC now and latest metrics/snapshot/collector run.
- Old historical data does not make the API stale by itself.

Validation and edge cases:

- Scanner endpoints use `limit` min `1`, max `100`.
- Asset history endpoints use `limit` min `1`, max `100`.
- Invalid `tf` and `metric` return validation errors.
- Unknown asset history endpoints return `200` with empty `items`.
- Scanner endpoints return `200` with empty items/rankings and `calculated_at=null` when no latest block exists.

Unchanged:

- API remains read-only.
- No old history was deleted or truncated.
- DB schema was not changed.
- Collector formulas were not changed.
- Binance endpoints were not changed.
- Scheduler alignment behavior was not changed.
- Data Core calculations were not changed.
- No frontend, Telegram, alerts, AI classification, z-score, anomaly score, Coinglass, borrow, repay, or trading actions were added.
- `.env`, `.venv/`, `data/`, `backups/`, credentials, tokens, and API keys were not changed.

Commands run:

- `git log --oneline --decorate -5` -> latest commit before changes: `82a4669 Improve collector UX and health report`.
- `git status --short` -> clean working tree before changes.
- `git diff --name-only` -> clean working tree before changes.
- `python -m compileall api collector database scripts smoke_check.py` -> passed.
- `python smoke_check.py` -> passed; covers all API endpoints and invalid `tf` / invalid `metric`.

Known notes:

- `smoke_check.py` now performs FastAPI `TestClient` requests and requires local PostgreSQL for API endpoints beyond `/health`.
- FastAPI TestClient emits a Starlette deprecation warning about `httpx`; checks still pass.

## Collector UX / Health Report v0.3.1

Files changed:

- `collector/main.py`
- `collector/db.py`
- `collector/metrics.py`
- `README.md`
- `HANDOFF_CURRENT_STATE.md`

Behavior changed:

- `python -m collector.main --once` now logs visible cycle progress before slow work starts.
- `Cycle started` is logged at the true beginning of `run_once()`, before settings load, DB connect, schema bootstrap, and collector run creation.
- Final cycle log includes `duration_seconds`.
- Normal INFO logs no longer print full `sample_price_matches`; INFO prints `sample_price_matches_count`, and detailed samples are DEBUG-only.
- Borrow pressure metric calculation logs concise per-timeframe progress:
  - starting timeframe calculation
  - rows calculated per timeframe
- Loop mode waiting log now clearly says the collector is waiting for the next aligned or interval run.
- Loop mode handles `Ctrl+C` during wait with `collector loop stopped by user` and exits without traceback.
- `python -m collector.main --health-report` is concise by default and omits TOP rows.
- `python -m collector.main --health-report --verbose` preserves detailed diagnostic sections and TOP rankings.
- `--top-limit N` controls verbose TOP ranking rows.
- `python -m collector.main --health-summary` is an alias for concise health report.
- Collector PostgreSQL connection now has `connect_timeout=5` to avoid silent terminal hangs when DB connection is unavailable.

Unchanged:

- No old history was deleted.
- DB schema was not changed.
- Collector formulas for `pool_metrics` and `borrow_pressure_metrics` were not changed.
- Binance endpoints were not changed.
- Scheduler alignment behavior was not changed.
- API Scanner behavior was not changed.
- No frontend, Telegram, alerts, borrow, repay, or trading actions were added.
- `.env`, `.venv/`, `data/`, `backups/`, credentials, tokens, and API keys were not changed.

Known notes:

- Borrow pressure metric insertion order is now timeframe-first so progress can be logged per timeframe; calculated formulas and rows are unchanged.
- Verbose health reports can still be large if `--top-limit` is high.

Commands run:

- `git status --short` -> clean working tree before changes.
- `git diff --name-only` -> clean working tree before changes.
- `python -m compileall api collector database scripts smoke_check.py` -> passed.
- `python smoke_check.py` -> passed.
- `python -m collector.main --health-report` -> passed; concise output, no TOP rows by default.
- `python -m collector.main --health-report --verbose --top-limit 3` -> passed; verbose TOP sections limited to 3 rows.
- `python -m collector.main --once` -> passed with visible progress logs and final `duration_seconds`.
- Synthetic loop wait `KeyboardInterrupt` test -> passed; logs `collector loop stopped by user` and exits without traceback.
- `python -m collector.main --health-summary` -> passed; same concise output as `--health-report`.

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
- Read-only FastAPI backend API is available
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
