from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from collector.config import Settings


def _to_dt(ms: int | None) -> datetime | None:
    if ms is None:
        return None
    # Binance endpoints can return epoch seconds or milliseconds.
    ts = float(ms)
    if ts < 10_000_000_000:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=False,
        row_factory=dict_row,
    )


def start_run(conn: psycopg.Connection, collector_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO collector_runs (collector_name, status)
            VALUES (%s, %s)
            RETURNING id
            """,
            (collector_name, "running"),
        )
        run_id = int(cur.fetchone()["id"])
    conn.commit()
    return run_id


def finish_run(conn: psycopg.Connection, run_id: int, status: str, records_collected: int, error_message: str | None, raw_error: dict | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE collector_runs
            SET finished_at = NOW(),
                status = %s,
                records_collected = %s,
                error_message = %s,
                raw_error = %s
            WHERE id = %s
            """,
            (status, records_collected, error_message, json.dumps(raw_error) if raw_error else None, run_id),
        )
    conn.commit()


def upsert_symbols(conn: psycopg.Connection, assets: list[str]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for asset in assets:
            symbol = f"{asset}USDT"
            cur.execute(
                """
                INSERT INTO symbols (asset, symbol, quote_asset, market_type, is_active)
                VALUES (%s, %s, 'USDT', 'spot', TRUE)
                ON CONFLICT (symbol) DO UPDATE SET
                  asset = EXCLUDED.asset,
                  updated_at = NOW(),
                  is_active = TRUE
                """,
                (asset, symbol),
            )
            inserted += 1
    conn.commit()
    return inserted


def upsert_assets(conn: psycopg.Connection, assets_payload: list[dict]) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in assets_payload:
            cur.execute(
                """
                INSERT INTO assets (
                  asset, is_borrowable, is_mortgageable, user_min_borrow, user_min_repay, updated_at, raw_json
                ) VALUES (%s, %s, %s, %s, %s, NOW(), %s::jsonb)
                ON CONFLICT (asset) DO UPDATE SET
                  is_borrowable = EXCLUDED.is_borrowable,
                  is_mortgageable = EXCLUDED.is_mortgageable,
                  user_min_borrow = EXCLUDED.user_min_borrow,
                  user_min_repay = EXCLUDED.user_min_repay,
                  updated_at = NOW(),
                  raw_json = EXCLUDED.raw_json
                """,
                (
                    item.get("assetName"),
                    item.get("isBorrowable"),
                    item.get("isMortgageable"),
                    Decimal(str(item.get("userMinBorrow", "0"))) if item.get("userMinBorrow") is not None else None,
                    Decimal(str(item.get("userMinRepay", "0"))) if item.get("userMinRepay") is not None else None,
                    json.dumps(item),
                ),
            )
            count += 1
    conn.commit()
    return count


def insert_margin_snapshots(conn: psycopg.Connection, pool_type: str, payload: dict) -> int:
    if not isinstance(payload, dict):
        raise ValueError(f"available-inventory payload must be dict, got {type(payload).__name__}")

    assets_node = payload.get("assets")
    update_time = _to_dt(payload.get("updateTime"))
    parsed_rows: list[tuple[str, Decimal, dict]] = []

    if isinstance(assets_node, dict):
        for asset, value in assets_node.items():
            parsed_rows.append(
                (
                    str(asset),
                    Decimal(str(value)),
                    {"asset": asset, "availableInventory": value, "updateTime": payload.get("updateTime")},
                )
            )
    elif isinstance(assets_node, list):
        for row in assets_node:
            if not isinstance(row, dict):
                continue
            asset = row.get("asset")
            if asset is None:
                continue
            parsed_rows.append(
                (
                    str(asset),
                    Decimal(str(row.get("availableInventory", "0"))),
                    row,
                )
            )
    else:
        payload_keys = list(payload.keys())[:10]
        raise ValueError(
            f"Unexpected available-inventory assets structure: assets_type={type(assets_node).__name__}, payload_keys={payload_keys}"
        )

    inserted = 0
    with conn.cursor() as cur:
        for asset, available_inventory, raw_row in parsed_rows:
            cur.execute(
                """
                INSERT INTO margin_pool_snapshots (
                  asset, pool_type, available_inventory, binance_update_time, collected_at, source, raw_json
                ) VALUES (%s, %s, %s, %s, NOW(), %s, %s::jsonb)
                """,
                (
                    asset,
                    pool_type,
                    available_inventory,
                    update_time,
                    "binance_available_inventory",
                    json.dumps(raw_row),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted, len(parsed_rows)


def insert_klines(conn: psycopg.Connection, symbol: str, interval: str, klines: list[list]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for k in klines:
            cur.execute(
                """
                INSERT INTO price_klines (
                  symbol, interval, open_time, close_time, open, high, low, close, volume,
                  quote_volume, number_of_trades, taker_buy_base_volume, taker_buy_quote_volume, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, interval, open_time) DO NOTHING
                """,
                (
                    symbol,
                    interval,
                    _to_dt(k[0]),
                    _to_dt(k[6]),
                    Decimal(str(k[1])),
                    Decimal(str(k[2])),
                    Decimal(str(k[3])),
                    Decimal(str(k[4])),
                    Decimal(str(k[5])),
                    Decimal(str(k[7])),
                    int(k[8]),
                    Decimal(str(k[9])),
                    Decimal(str(k[10])),
                    "binance:/api/v3/klines",
                ),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted


def fetch_previous_snapshot(conn: psycopg.Connection, asset: str, pool_type: str, current_collected_at: datetime) -> Decimal | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT available_inventory
            FROM margin_pool_snapshots
            WHERE asset = %s
              AND pool_type = %s
              AND collected_at < %s
            ORDER BY collected_at DESC
            LIMIT 1
            """,
            (asset, pool_type, current_collected_at),
        )
        row = cur.fetchone()
        return row["available_inventory"] if row else None


def fetch_latest_unprocessed_snapshots(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.asset, s.pool_type, s.available_inventory, s.collected_at
            FROM margin_pool_snapshots s
            LEFT JOIN pool_metrics m
              ON m.asset = s.asset
             AND m.pool_type = s.pool_type
             AND m.timestamp = s.collected_at
            WHERE m.id IS NULL
            ORDER BY s.collected_at ASC
            """
        )
        return list(cur.fetchall())


def insert_pool_metric(conn: psycopg.Connection, row: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pool_metrics (
              asset, pool_type, "timestamp", available_inventory, previous_available_inventory,
              pool_change, pool_change_percent, pool_decrease, pool_recovery,
              borrow_pressure_proxy, repay_or_refill_proxy
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["asset"],
                row["pool_type"],
                row["timestamp"],
                row["available_inventory"],
                row["previous_available_inventory"],
                row["pool_change"],
                row["pool_change_percent"],
                row["pool_decrease"],
                row["pool_recovery"],
                row["borrow_pressure_proxy"],
                row["repay_or_refill_proxy"],
            ),
        )
