from __future__ import annotations

import argparse
import logging
import sys
import time

from collector.binance_client import BinanceAPIError, BinanceClient
from collector.config import load_settings
from collector import db, metrics

LOGGER = logging.getLogger("collector")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def run_once() -> int:
    settings = load_settings()
    conn = db.connect(settings)
    client = BinanceClient(settings.binance_api_key, settings.binance_api_secret)
    run_id = db.start_run(conn, "margin-local-data-core")
    records_collected = 0
    problems: list[str] = []
    raw_errors: list[dict] = []

    try:
        LOGGER.info("Cycle started")
        symbols_upserted = db.upsert_symbols(conn, settings.watchlist_assets)
        LOGGER.info("symbols upserted=%s", symbols_upserted)

        assets_count = 0
        try:
            assets_payload = client.get_margin_assets()
            assets_count = db.upsert_assets(conn, assets_payload)
            records_collected += assets_count
            LOGGER.info("assets collected=%s", assets_count)
        except BinanceAPIError as exc:
            problems.append("margin allAssets failed")
            raw_errors.append({"endpoint": "allAssets", "details": exc.details})
            LOGGER.warning("assets failed: %s details=%s", exc, exc.details)
        except Exception as exc:
            problems.append("margin allAssets failed")
            raw_errors.append({"endpoint": "allAssets", "details": {"error": str(exc), "type": exc.__class__.__name__}})
            LOGGER.warning("assets failed: %s", exc)

        snapshots_count = 0
        snapshots_fetched = 0
        if not settings.binance_api_key or not settings.binance_api_secret:
            problems.append("available-inventory skipped: missing API key/secret")
            LOGGER.warning("available-inventory skipped because Binance API credentials are missing")
            inventory_state = "skipped"
        else:
            try:
                inv_payload = client.get_margin_available_inventory(settings.pool_type)
                snapshots_count, snapshots_fetched = db.insert_margin_snapshots(conn, settings.pool_type, inv_payload)
                records_collected += snapshots_count
                inventory_state = "collected"
            except BinanceAPIError as exc:
                problems.append("available-inventory failed")
                raw_errors.append({"endpoint": "available-inventory", "details": exc.details})
                LOGGER.warning("inventory failed: %s details=%s", exc, exc.details)
                inventory_state = "failed"
            except Exception as exc:
                problems.append("available-inventory failed")
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
                raw_errors.append({"endpoint": f"klines:{symbol}", "details": {"error": str(exc), "type": exc.__class__.__name__}})
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
            problems.append(f"klines failed for {kline_errors} symbol(s)")

        pool_metrics_count = metrics.calculate_and_store_pool_metrics(conn)
        records_collected += pool_metrics_count
        LOGGER.info("pool_metrics calculated=%s", pool_metrics_count)

        if klines_success_symbols == len(settings.symbols) and not problems:
            status = "success"
        elif klines_success_symbols > 0 or records_collected > 0:
            status = "partial_success"
        else:
            status = "failed"
        error_message = "; ".join(problems) if problems else None
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
    args = parser.parse_args()

    setup_logging()
    settings = load_settings()
    loop_mode = args.loop

    if not loop_mode:
        return run_once()

    LOGGER.info("Starting loop mode interval=%s", settings.collector_interval_seconds)
    while True:
        code = run_once()
        if code != 0:
            LOGGER.error("Cycle failed in loop mode; continuing after sleep")
        time.sleep(settings.collector_interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
