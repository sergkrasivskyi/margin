from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

from collector.binance_client import BinanceAPIError, BinanceClient
from collector.config import load_settings
from collector import db, metrics

LOGGER = logging.getLogger("collector")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _next_aligned_run(now_utc: datetime, alignment_minutes: int, delay_seconds: int) -> datetime:
    alignment_seconds = max(1, alignment_minutes) * 60
    epoch = int(now_utc.timestamp())
    next_boundary = ((epoch // alignment_seconds) + 1) * alignment_seconds
    return datetime.fromtimestamp(next_boundary, tz=timezone.utc) + timedelta(seconds=max(0, delay_seconds))


def _run_health_report(conn) -> None:
    with conn.cursor() as cur:
        LOGGER.info("health_report: last 10 collector_runs")
        cur.execute(
            """
            SELECT collector_name, started_at, finished_at, status, records_collected, error_message
            FROM collector_runs
            ORDER BY started_at DESC
            LIMIT 10
            """
        )
        for row in cur.fetchall():
            LOGGER.info("run: %s", row)

        cur.execute("SELECT COUNT(*) AS count FROM margin_pool_snapshots")
        LOGGER.info("health_report: margin_pool_snapshots_count=%s", cur.fetchone()["count"])

        cur.execute("SELECT COUNT(*) AS count FROM pool_metrics")
        LOGGER.info("health_report: pool_metrics_count=%s", cur.fetchone()["count"])

        cur.execute(
            """
            SELECT date_trunc('minute', collected_at) AS minute, COUNT(*) AS rows
            FROM margin_pool_snapshots
            GROUP BY minute
            ORDER BY minute DESC
            LIMIT 10
            """
        )
        LOGGER.info("health_report: latest snapshot blocks")
        for row in cur.fetchall():
            LOGGER.info("snapshot_block: %s", row)

        cur.execute(
            """
            SELECT asset, COUNT(*) AS snapshots
            FROM margin_pool_snapshots
            GROUP BY asset
            ORDER BY snapshots DESC, asset
            LIMIT 20
            """
        )
        LOGGER.info("health_report: snapshot count by asset (top 20)")
        for row in cur.fetchall():
            LOGGER.info("asset_snapshots: %s", row)

        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM pool_metrics
            WHERE previous_available_inventory IS NOT NULL
            """
        )
        LOGGER.info("health_report: pool_metrics_with_previous=%s", cur.fetchone()["count"])

        cur.execute(
            """
            SELECT MAX(created_at) AS latest_metrics_block
            FROM pool_metrics
            """
        )
        latest_block = cur.fetchone()["latest_metrics_block"]
        LOGGER.info("health_report: latest_metrics_block=%s", latest_block)

        if latest_block is None:
            LOGGER.info("health_report: no pool_metrics rows for top changes report")
            return

        cur.execute(
            """
            SELECT asset, available_inventory, previous_available_inventory, pool_change, pool_change_percent, pool_decrease, created_at
            FROM pool_metrics
            WHERE previous_available_inventory IS NOT NULL
              AND created_at = %s
            ORDER BY pool_decrease DESC
            LIMIT 20
            """,
            (latest_block,),
        )
        LOGGER.info("health_report: top pool decreases for latest cycle")
        for row in cur.fetchall():
            LOGGER.info("top_decrease: %s", row)

        cur.execute(
            """
            SELECT asset, available_inventory, previous_available_inventory, pool_change, pool_change_percent, pool_recovery, created_at
            FROM pool_metrics
            WHERE previous_available_inventory IS NOT NULL
              AND created_at = %s
            ORDER BY pool_recovery DESC
            LIMIT 20
            """,
            (latest_block,),
        )
        LOGGER.info("health_report: top pool recoveries for latest cycle")
        for row in cur.fetchall():
            LOGGER.info("top_recovery: %s", row)

        cur.execute(
            """
            SELECT asset, pool_change_percent, available_inventory, previous_available_inventory, created_at
            FROM pool_metrics
            WHERE previous_available_inventory IS NOT NULL
              AND pool_change_percent IS NOT NULL
              AND created_at = %s
            ORDER BY ABS(pool_change_percent) DESC
            LIMIT 20
            """,
            (latest_block,),
        )
        LOGGER.info("health_report: top absolute percent changes for latest cycle")
        for row in cur.fetchall():
            LOGGER.info("top_abs_pct_change: %s", row)

        cur.execute(
            """
            SELECT asset, available_inventory, previous_available_inventory, pool_change, pool_change_percent, pool_decrease, created_at
            FROM pool_metrics
            WHERE previous_available_inventory IS NOT NULL
            ORDER BY pool_decrease DESC, created_at DESC
            LIMIT 20
            """
        )
        LOGGER.info("health_report: top pool decreases all history")
        for row in cur.fetchall():
            LOGGER.info("top_decrease_all_history: %s", row)


def run_once() -> int:
    settings = load_settings()
    conn = db.connect(settings)
    client = BinanceClient(settings.binance_api_key, settings.binance_api_secret)
    run_id = db.start_run(conn, "margin-local-data-core")
    records_collected = 0
    critical_problems: list[str] = []
    warnings: list[str] = []
    raw_errors: list[dict] = []

    try:
        LOGGER.info("Cycle started")
        symbols_upserted = db.upsert_symbols(conn, settings.watchlist_assets)
        LOGGER.info("symbols upserted=%s", symbols_upserted)

        assets_count = 0
        if settings.collect_margin_assets:
            try:
                assets_payload = client.get_margin_assets()
                assets_count = db.upsert_assets(conn, assets_payload)
                records_collected += assets_count
                LOGGER.info("assets collected=%s", assets_count)
            except BinanceAPIError as exc:
                warnings.append("margin allAssets failed")
                raw_errors.append({"endpoint": "allAssets", "details": exc.details})
                LOGGER.warning("assets failed (non-critical): %s details=%s", exc, exc.details)
            except Exception as exc:
                warnings.append("margin allAssets failed")
                raw_errors.append({"endpoint": "allAssets", "details": {"error": str(exc), "type": exc.__class__.__name__}})
                LOGGER.warning("assets failed (non-critical): %s", exc)
        else:
            LOGGER.info("assets collection disabled by COLLECT_MARGIN_ASSETS=false")

        snapshots_count = 0
        snapshots_fetched = 0
        if not settings.binance_api_key or not settings.binance_api_secret:
            critical_problems.append("available-inventory skipped: missing API key/secret")
            LOGGER.warning("available-inventory skipped because Binance API credentials are missing")
            inventory_state = "skipped"
        else:
            try:
                inv_payload = client.get_margin_available_inventory(settings.pool_type)
                snapshots_count, snapshots_fetched = db.insert_margin_snapshots(conn, settings.pool_type, inv_payload)
                records_collected += snapshots_count
                inventory_state = "collected"
            except BinanceAPIError as exc:
                critical_problems.append("available-inventory failed")
                raw_errors.append({"endpoint": "available-inventory", "details": exc.details})
                LOGGER.warning("inventory failed: %s details=%s", exc, exc.details)
                inventory_state = "failed"
            except Exception as exc:
                critical_problems.append("available-inventory failed")
                raw_errors.append(
                    {"endpoint": "available-inventory", "details": {"error": str(exc), "type": exc.__class__.__name__}}
                )
                LOGGER.warning("inventory failed: %s", exc)
                inventory_state = "failed"
        LOGGER.info(
            "inventory %s; inventory fetched=%s inserted=%s",
            inventory_state,
            snapshots_fetched,
            snapshots_count,
        )

        klines_inserted = 0
        klines_fetched = 0
        kline_errors = 0
        klines_success_symbols = 0
        if settings.price_collection_mode == "disabled":
            LOGGER.info("price collection disabled by PRICE_COLLECTION_MODE=disabled")
        else:
            for symbol in settings.symbols:
                try:
                    klines = client.get_klines(symbol, settings.kline_interval)
                    klines_fetched += len(klines)
                    klines_inserted += db.insert_klines(conn, symbol, settings.kline_interval, klines)
                    klines_success_symbols += 1
                except BinanceAPIError as exc:
                    kline_errors += 1
                    raw_errors.append({"endpoint": f"klines:{symbol}", "details": exc.details})
                    LOGGER.warning("klines failed for %s: %s", symbol, exc)
                except Exception as exc:
                    kline_errors += 1
                    raw_errors.append(
                        {"endpoint": f"klines:{symbol}", "details": {"error": str(exc), "type": exc.__class__.__name__}}
                    )
                    LOGGER.warning("klines failed for %s: %s", symbol, exc)
        klines_skipped_duplicates = max(0, klines_fetched - klines_inserted)
        records_collected += klines_inserted
        LOGGER.info(
            "klines fetched=%s inserted=%s skipped_duplicates=%s",
            klines_fetched,
            klines_inserted,
            klines_skipped_duplicates,
        )
        if kline_errors:
            critical_problems.append(f"klines failed for {kline_errors} symbol(s)")

        pool_metrics_count = metrics.calculate_and_store_pool_metrics(conn)
        records_collected += pool_metrics_count
        LOGGER.info("pool_metrics calculated=%s", pool_metrics_count)

        if not critical_problems:
            status = "success"
        elif records_collected > 0 or snapshots_count > 0 or klines_success_symbols > 0:
            status = "partial_success"
        else:
            status = "failed"
        message_parts = critical_problems + warnings
        error_message = "; ".join(message_parts) if message_parts else None
        raw_error_payload = {"errors": raw_errors} if raw_errors else None

        db.finish_run(conn, run_id, status, records_collected, error_message, raw_error_payload)
        LOGGER.info(
            "Cycle finished: assets=%s inventory=%s klines_fetched=%s klines_inserted=%s pool_metrics=%s run_status=%s",
            assets_count,
            inventory_state,
            klines_fetched,
            klines_inserted,
            pool_metrics_count,
            status,
        )
        return 0 if status != "failed" else 1
    except Exception as exc:
        conn.rollback()
        LOGGER.exception("Critical collector error")
        db.finish_run(conn, run_id, "failed", records_collected, str(exc), {"type": exc.__class__.__name__})
        return 1
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Binance margin research collector")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one collection cycle (default)")
    mode.add_argument("--loop", action="store_true", help="Run collection loop")
    mode.add_argument("--health-report", action="store_true", help="Show DB health and pool change report")
    args = parser.parse_args()

    setup_logging()
    settings = load_settings()
    if args.health_report:
        conn = db.connect(settings)
        try:
            _run_health_report(conn)
            return 0
        finally:
            conn.close()

    if not args.loop:
        return run_once()

    LOGGER.info(
        "Starting loop mode scheduler_mode=%s interval_seconds=%s alignment_minutes=%s collection_delay_seconds=%s",
        settings.scheduler_mode,
        settings.collector_interval_seconds,
        settings.alignment_minutes,
        settings.collection_delay_seconds,
    )
    while True:
        if settings.scheduler_mode == "aligned":
            now = datetime.now(timezone.utc)
            next_run = _next_aligned_run(now, settings.alignment_minutes, settings.collection_delay_seconds)
            wait_seconds = max(0.0, (next_run - now).total_seconds())
            LOGGER.info(
                "scheduler_mode=aligned next_run_at=%s alignment_minutes=%s collection_delay_seconds=%s",
                next_run.isoformat(),
                settings.alignment_minutes,
                settings.collection_delay_seconds,
            )
            time.sleep(wait_seconds)
            actual_started_at = datetime.now(timezone.utc)
            delay_from_schedule = (actual_started_at - next_run).total_seconds()
            LOGGER.info(
                "actual_started_at=%s delay_from_schedule_seconds=%.3f",
                actual_started_at.isoformat(),
                delay_from_schedule,
            )
            code = run_once()
        else:
            code = run_once()
            LOGGER.info("scheduler_mode=interval sleeping=%s", settings.collector_interval_seconds)
            time.sleep(settings.collector_interval_seconds)

        if code != 0:
            LOGGER.error("Cycle failed in loop mode; continuing")


if __name__ == "__main__":
    sys.exit(main())
