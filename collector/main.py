from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from collector import db, metrics
from collector.binance_client import BinanceAPIError, BinanceClient
from collector.config import load_settings

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


def _build_direct_usdt_price_rows(payload: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).upper()
        if not symbol.endswith("USDT") or len(symbol) <= 4:
            continue
        price_raw = item.get("price")
        try:
            price_usdt = Decimal(str(price_raw))
        except (InvalidOperation, TypeError):
            continue
        rows.append(
            {
                "asset": symbol[:-4],
                "symbol": symbol,
                "price_usdt": price_usdt,
                "source": "binance:/api/v3/ticker/price",
                "raw_json": item,
            }
        )
    return rows


def _build_spot_price_map(price_rows: list[dict]) -> dict[str, dict[str, Decimal | str]]:
    return {
        row["asset"]: {
            "symbol": row["symbol"],
            "price_usdt": row["price_usdt"],
        }
        for row in price_rows
    }


def _log_health_rankings(conn, timeframe: str, label: str, query: str) -> None:
    with conn.cursor() as cur:
        cur.execute(query, (timeframe,))
        LOGGER.info("health_report: %s timeframe=%s", label, timeframe)
        for row in cur.fetchall():
            LOGGER.info("%s: %s", label, row)


def _run_health_report(conn) -> None:
    db.ensure_schema(conn)
    timeframes = tuple(db.BORROW_PRESSURE_TIMEFRAMES.keys())

    with conn.cursor() as cur:
        LOGGER.info("health_report: research metrics only, not trading signals")
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

        for table_name in (
            "margin_pool_snapshots",
            "pool_metrics",
            "spot_price_snapshots",
            "borrow_pressure_metrics",
        ):
            cur.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
            LOGGER.info("health_report: %s_count=%s", table_name, cur.fetchone()["count"])

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
            WITH latest AS (
              SELECT timeframe, MAX(calculated_at) AS latest_calculated_at
              FROM borrow_pressure_metrics
              WHERE timeframe = ANY(%s)
              GROUP BY timeframe
            )
            SELECT l.timeframe, l.latest_calculated_at, COUNT(bpm.id) AS rows_at_latest
            FROM latest l
            JOIN borrow_pressure_metrics bpm
              ON bpm.timeframe = l.timeframe
             AND bpm.calculated_at = l.latest_calculated_at
            GROUP BY l.timeframe, l.latest_calculated_at
            ORDER BY l.timeframe
            """,
            (list(timeframes),),
        )
        LOGGER.info("health_report: latest borrow_pressure_metrics blocks by timeframe")
        for row in cur.fetchall():
            LOGGER.info("borrow_pressure_block: %s", row)

        cur.execute(
            """
            SELECT
              timeframe,
              COUNT(*) AS rows,
              COUNT(*) FILTER (WHERE price_available) AS price_available_rows,
              COUNT(*) FILTER (WHERE NOT price_available) AS price_unavailable_rows
            FROM borrow_pressure_metrics
            GROUP BY timeframe
            ORDER BY timeframe
            """
        )
        LOGGER.info("health_report: price availability by timeframe")
        for row in cur.fetchall():
            LOGGER.info("price_availability: %s", row)

    top_borrow_pressure_usdt = """
        SELECT asset, borrow_pressure_usdt, borrow_pressure_units, spot_price_usdt, current_snapshot_at, calculated_at
        FROM borrow_pressure_metrics
        WHERE timeframe = %s
          AND price_available = TRUE
          AND borrow_pressure_usdt IS NOT NULL
        ORDER BY borrow_pressure_usdt DESC, calculated_at DESC, asset
        LIMIT 10
    """
    top_borrow_pressure_percent = """
        SELECT asset, borrow_pressure_percent, borrow_pressure_units, previous_available_inventory, current_snapshot_at, calculated_at
        FROM borrow_pressure_metrics
        WHERE timeframe = %s
          AND borrow_pressure_percent IS NOT NULL
        ORDER BY borrow_pressure_percent DESC, calculated_at DESC, asset
        LIMIT 10
    """
    top_recovery_usdt = """
        SELECT asset, recovery_usdt, recovery_units, spot_price_usdt, current_snapshot_at, calculated_at
        FROM borrow_pressure_metrics
        WHERE timeframe = %s
          AND price_available = TRUE
          AND recovery_usdt IS NOT NULL
        ORDER BY recovery_usdt DESC, calculated_at DESC, asset
        LIMIT 10
    """
    top_recovery_percent = """
        SELECT asset, recovery_percent, recovery_units, previous_available_inventory, current_snapshot_at, calculated_at
        FROM borrow_pressure_metrics
        WHERE timeframe = %s
          AND recovery_percent IS NOT NULL
        ORDER BY recovery_percent DESC, calculated_at DESC, asset
        LIMIT 10
    """

    for timeframe in timeframes:
        _log_health_rankings(conn, timeframe, "top_borrow_pressure_usdt", top_borrow_pressure_usdt)
        _log_health_rankings(conn, timeframe, "top_borrow_pressure_percent", top_borrow_pressure_percent)
        _log_health_rankings(conn, timeframe, "top_recovery_usdt", top_recovery_usdt)
        _log_health_rankings(conn, timeframe, "top_recovery_percent", top_recovery_percent)


def run_once() -> int:
    settings = load_settings()
    conn = db.connect(settings)
    db.ensure_schema(conn)
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
        inventory_collected = False
        if not settings.binance_api_key or not settings.binance_api_secret:
            critical_problems.append("available-inventory skipped: missing API key/secret")
            LOGGER.warning("available-inventory skipped because Binance API credentials are missing")
            inventory_state = "skipped"
        else:
            try:
                inv_payload = client.get_margin_available_inventory(settings.pool_type)
                snapshots_count, snapshots_fetched = db.insert_margin_snapshots(conn, settings.pool_type, inv_payload)
                records_collected += snapshots_count
                inventory_collected = snapshots_count > 0
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

        spot_prices_inserted = 0
        spot_prices_fetched = 0
        spot_price_map: dict[str, dict[str, Decimal | str]] = {}
        if settings.spot_price_collection_mode == "disabled":
            LOGGER.info("spot price collection disabled by SPOT_PRICE_COLLECTION_MODE=disabled")
        elif inventory_collected:
            try:
                ticker_payload = client.get_spot_ticker_prices()
                spot_price_rows = _build_direct_usdt_price_rows(ticker_payload)
                spot_price_map = _build_spot_price_map(spot_price_rows)
                spot_prices_fetched = len(spot_price_rows)
                spot_prices_inserted = db.insert_spot_price_snapshots(conn, spot_price_rows)
                records_collected += spot_prices_inserted
                LOGGER.info("spot_prices fetched=%s inserted=%s", spot_prices_fetched, spot_prices_inserted)
            except BinanceAPIError as exc:
                critical_problems.append("spot prices failed")
                raw_errors.append({"endpoint": "spot-ticker-price", "details": exc.details})
                LOGGER.warning("spot prices failed: %s details=%s", exc, exc.details)
            except Exception as exc:
                critical_problems.append("spot prices failed")
                raw_errors.append({"endpoint": "spot-ticker-price", "details": {"error": str(exc), "type": exc.__class__.__name__}})
                LOGGER.warning("spot prices failed: %s", exc)
        else:
            LOGGER.info("spot price collection skipped because inventory snapshot was not collected")

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

        borrow_pressure_summary = {
            "calculated": 0,
            "calculated_by_timeframe": {timeframe: 0 for timeframe in db.BORROW_PRESSURE_TIMEFRAMES},
            "price_available_count": 0,
            "price_unavailable_count": 0,
            "sample_price_matches": [],
        }
        if inventory_collected:
            borrow_pressure_summary = metrics.calculate_and_store_borrow_pressure_metrics(conn, spot_price_map)
            records_collected += borrow_pressure_summary["calculated"]
        LOGGER.info(
            "borrow_pressure_metrics calculated=%s calculated_by_timeframe=%s price_available_count=%s "
            "price_unavailable_count=%s sample_price_matches=%s",
            borrow_pressure_summary["calculated"],
            borrow_pressure_summary["calculated_by_timeframe"],
            borrow_pressure_summary["price_available_count"],
            borrow_pressure_summary["price_unavailable_count"],
            borrow_pressure_summary["sample_price_matches"],
        )

        if not critical_problems:
            status = "success"
        elif (
            records_collected > 0
            or snapshots_count > 0
            or klines_success_symbols > 0
            or spot_prices_inserted > 0
            or borrow_pressure_summary["calculated"] > 0
        ):
            status = "partial_success"
        else:
            status = "failed"
        message_parts = critical_problems + warnings
        error_message = "; ".join(message_parts) if message_parts else None
        raw_error_payload = {"errors": raw_errors} if raw_errors else None

        db.finish_run(conn, run_id, status, records_collected, error_message, raw_error_payload)
        LOGGER.info(
            "Cycle finished: assets=%s inventory=%s spot_prices_inserted=%s klines_fetched=%s klines_inserted=%s "
            "pool_metrics=%s borrow_pressure_metrics=%s run_status=%s",
            assets_count,
            inventory_state,
            spot_prices_inserted,
            klines_fetched,
            klines_inserted,
            pool_metrics_count,
            borrow_pressure_summary["calculated"],
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
