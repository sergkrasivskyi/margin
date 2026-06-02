# AGENTS.md

## Project overview

- Project name: `margin-loan-research`
- Local path: `C:\Projects\margin-loan-research`
- Repo: `https://github.com/sergkrasivskyi/margin`
- Local-first research project for Binance margin available inventory and borrow pressure analysis.
- PostgreSQL runs in Docker.
- Collector runs locally in `.venv`.
- FastAPI serves the read-only API and local web UI.
- The project exposes research metrics, not trading signals.

## Architecture summary

Current components:

- Docker PostgreSQL
- Python collector
- Binance Margin Available Inventory collection
- `spot_price_snapshots`
- `borrow_pressure_metrics`
- FastAPI read-only API
- Planned/simple static web UI served by FastAPI

Current API endpoints:

- `GET /health`
- `GET /api/overview`
- `GET /api/scanner/latest`
- `GET /api/scanner/summary`
- `GET /api/assets`
- `GET /api/assets/{asset}/metrics-history`
- `GET /api/assets/{asset}/pool-history`

## Safety rules

- Never touch or print `.env`, secrets, API keys, credentials, or tokens.
- Do not modify `.venv/`, `data/`, or backups unless explicitly instructed.
- Do not delete or truncate old history unless explicitly instructed.
- Do not add trading actions, borrow, repay, Binance write calls, or buy/sell recommendations.
- Do not add Telegram, alerts, AI classification, z-score, `anomaly_score`, or Coinglass unless the current milestone explicitly asks for it.
- Do not change DB schema, collector formulas, Binance endpoints, or scheduler behavior unless explicitly asked.
- API and UI should remain read-only unless explicitly instructed otherwise.
- Do not commit. The user controls git commits manually.

## Git pre-checks

Before making changes always run:

```powershell
git --no-pager log --oneline --decorate -5; git status --short; git diff --name-only
```

If the working tree is not clean, stop and report modified files.

If a required read-only pre-check command fails because the native Windows sandbox cannot spawn the process, do not retry multiple non-escalated attempts. Request escalation once and continue.

If the user provides fresh exact pre-check outputs in the current prompt, treat those as pre-check context and do not rerun the same commands unless files were changed or the task requires a new check.

## Verification commands

After code changes, run:

```powershell
python -m compileall api collector database scripts smoke_check.py
python smoke_check.py
```

For UI/API tasks, manual verification may include:

```powershell
uvicorn api.main:app --reload --port 8000
```

Then open:

```text
http://127.0.0.1:8000/
```

For collector tasks:

- Do not run a long collector loop unless specifically needed.
- Prefer `python -m collector.main --once` or `python -m collector.main --health-report` for verification.

## Documentation expectations

For meaningful milestones:

- Update `README.md` when user-facing commands or endpoints change.
- Update `HANDOFF_CURRENT_STATE.md` with current state, files changed, checks run, and limitations.

## Final response format

Codex final responses should include:

- Whether the working tree was clean at start.
- Changed files.
- Summary of changes.
- Commands run and results.
- Warnings or failed checks.
- Explicit safety confirmation.
- Confirmation that no commit was made.
