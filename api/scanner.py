from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import HTTPException

from api.schemas import decimal_to_str, datetime_to_utc_iso
from api.settings import STALE_AFTER_SECONDS, STABLE_ASSETS, SUPPORTED_METRICS, SUPPORTED_TIMEFRAMES

METRIC_ORDERING = {
    "borrow_pressure_usdt": (
        "borrow_pressure_usdt IS NOT NULL AND borrow_pressure_usdt > 0 AND price_available = TRUE",
        "borrow_pressure_usdt DESC, borrow_pressure_percent DESC NULLS LAST, asset ASC",
    ),
    "borrow_pressure_percent": (
        "borrow_pressure_percent IS NOT NULL AND borrow_pressure_percent > 0",
        "borrow_pressure_percent DESC, borrow_pressure_usdt DESC NULLS LAST, asset ASC",
    ),
    "recovery_usdt": (
        "recovery_usdt IS NOT NULL AND recovery_usdt > 0 AND price_available = TRUE",
        "recovery_usdt DESC, recovery_percent DESC NULLS LAST, asset ASC",
    ),
    "recovery_percent": (
        "recovery_percent IS NOT NULL AND recovery_percent > 0",
        "recovery_percent DESC, recovery_usdt DESC NULLS LAST, asset ASC",
    ),
}


def validate_timeframe(tf: str) -> str:
    normalized = tf.strip().lower()
    if normalized not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=422, detail=f"Unsupported tf={tf}. Supported: {', '.join(SUPPORTED_TIMEFRAMES)}")
    return normalized


def validate_metric(metric: str) -> str:
    normalized = metric.strip().lower()
    if normalized not in SUPPORTED_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported metric={metric}. Supported: {', '.join(SUPPORTED_METRICS)}",
        )
    return normalized


def normalize_asset(asset: str) -> str:
    return asset.strip().upper()


def _stable_filter_sql(exclude_stables: bool) -> tuple[str, list[Any]]:
    if not exclude_stables:
        return "", []
    return " AND UPPER(asset) <> ALL(%s)", [list(STABLE_ASSETS)]


def _scanner_item(row: dict) -> dict:
    return {
        "asset": row["asset"],
        "current_available_inventory": decimal_to_str(row["current_available_inventory"]),
        "previous_available_inventory": decimal_to_str(row["previous_available_inventory"]),
        "net_pool_change_units": decimal_to_str(row["net_pool_change_units"]),
        "net_pool_change_percent": decimal_to_str(row["net_pool_change_percent"]),
        "borrow_pressure_units": decimal_to_str(row["borrow_pressure_units"]),
        "borrow_pressure_percent": decimal_to_str(row["borrow_pressure_percent"]),
        "borrow_pressure_usdt": decimal_to_str(row["borrow_pressure_usdt"]),
        "recovery_units": decimal_to_str(row["recovery_units"]),
        "recovery_percent": decimal_to_str(row["recovery_percent"]),
        "recovery_usdt": decimal_to_str(row["recovery_usdt"]),
        "spot_price_usdt": decimal_to_str(row["spot_price_usdt"]),
        "price_symbol": row["price_symbol"],
        "price_available": bool(row["price_available"]),
        "current_snapshot_at": datetime_to_utc_iso(row["current_snapshot_at"]),
        "previous_snapshot_at": datetime_to_utc_iso(row["previous_snapshot_at"]),
    }


def fetch_latest_calculated_at(conn: psycopg.Connection, tf: str) -> Any:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(calculated_at) AS calculated_at
            FROM borrow_pressure_metrics
            WHERE timeframe = %s
            """,
            (tf,),
        )
        row = cur.fetchone()
        return row["calculated_at"] if row else None


def _age_seconds(now_utc: datetime, value: Any) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, int((now_utc - value.astimezone(timezone.utc)).total_seconds()))


def fetch_data_freshness(conn: psycopg.Connection) -> dict:
    now_utc = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(calculated_at) AS calculated_at FROM borrow_pressure_metrics")
        latest_metrics_calculated_at = cur.fetchone()["calculated_at"]

        cur.execute("SELECT MAX(collected_at) AS snapshot_at FROM margin_pool_snapshots")
        latest_snapshot_at = cur.fetchone()["snapshot_at"]

        cur.execute(
            """
            SELECT status, finished_at
            FROM collector_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        run_row = cur.fetchone()

    latest_metrics_age_seconds = _age_seconds(now_utc, latest_metrics_calculated_at)
    latest_snapshot_age_seconds = _age_seconds(now_utc, latest_snapshot_at)
    is_data_stale = (
        latest_metrics_age_seconds is None
        or latest_snapshot_age_seconds is None
        or latest_metrics_age_seconds > STALE_AFTER_SECONDS
        or latest_snapshot_age_seconds > STALE_AFTER_SECONDS
    )
    return {
        "latest_metrics_calculated_at": datetime_to_utc_iso(latest_metrics_calculated_at),
        "latest_metrics_age_seconds": latest_metrics_age_seconds,
        "latest_snapshot_at": datetime_to_utc_iso(latest_snapshot_at),
        "latest_snapshot_age_seconds": latest_snapshot_age_seconds,
        "last_collector_run_status": run_row["status"] if run_row else None,
        "last_collector_run_finished_at": datetime_to_utc_iso(run_row["finished_at"]) if run_row else None,
        "is_data_stale": is_data_stale,
        "stale_after_seconds": STALE_AFTER_SECONDS,
    }


def fetch_overview(conn: psycopg.Connection) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(calculated_at) AS calculated_at FROM borrow_pressure_metrics")
        latest = cur.fetchone()["calculated_at"]
        cur.execute(
            """
            WITH latest AS (
              SELECT timeframe, MAX(calculated_at) AS calculated_at
              FROM borrow_pressure_metrics
              GROUP BY timeframe
            )
            SELECT
              bpm.timeframe AS tf,
              COUNT(*) AS rows,
              COUNT(*) FILTER (WHERE bpm.price_available) AS price_available_rows,
              COUNT(*) FILTER (WHERE NOT bpm.price_available) AS price_unavailable_rows
            FROM latest l
            JOIN borrow_pressure_metrics bpm
              ON bpm.timeframe = l.timeframe
             AND bpm.calculated_at = l.calculated_at
            GROUP BY bpm.timeframe
            ORDER BY bpm.timeframe
            """
        )
        overview = [
            {
                "tf": row["tf"],
                "rows": int(row["rows"]),
                "price_available_rows": int(row["price_available_rows"]),
                "price_unavailable_rows": int(row["price_unavailable_rows"]),
            }
            for row in cur.fetchall()
        ]
    return {
        "latest_metrics_calculated_at": datetime_to_utc_iso(latest),
        "data_freshness": fetch_data_freshness(conn),
        "overview": overview,
    }


def fetch_scanner_items(
    conn: psycopg.Connection,
    tf: str,
    metric: str,
    limit: int,
    exclude_stables: bool,
    calculated_at: Any,
) -> list[dict]:
    where_metric, order_by = METRIC_ORDERING[metric]
    stable_sql, stable_params = _stable_filter_sql(exclude_stables)
    params: list[Any] = [tf, calculated_at, *stable_params, limit]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
              asset, current_available_inventory, previous_available_inventory,
              net_pool_change_units, net_pool_change_percent, borrow_pressure_units,
              borrow_pressure_percent, borrow_pressure_usdt, recovery_units,
              recovery_percent, recovery_usdt, spot_price_usdt, price_symbol,
              price_available, current_snapshot_at, previous_snapshot_at
            FROM borrow_pressure_metrics
            WHERE timeframe = %s
              AND calculated_at = %s
              AND {where_metric}
              {stable_sql}
            ORDER BY {order_by}
            LIMIT %s
            """,
            params,
        )
        return [_scanner_item(row) for row in cur.fetchall()]


def fetch_scanner_latest(
    conn: psycopg.Connection,
    tf: str,
    metric: str,
    limit: int,
    exclude_stables: bool,
) -> dict:
    calculated_at = fetch_latest_calculated_at(conn, tf)
    data_freshness = fetch_data_freshness(conn)
    if calculated_at is None:
        return {
            "tf": tf,
            "metric": metric,
            "limit": limit,
            "exclude_stables": exclude_stables,
            "calculated_at": None,
            "data_freshness": data_freshness,
            "items": [],
        }

    return {
        "tf": tf,
        "metric": metric,
        "limit": limit,
        "exclude_stables": exclude_stables,
        "calculated_at": datetime_to_utc_iso(calculated_at),
        "data_freshness": data_freshness,
        "items": fetch_scanner_items(conn, tf, metric, limit, exclude_stables, calculated_at),
    }


def fetch_scanner_summary(conn: psycopg.Connection, tf: str, limit: int, exclude_stables: bool) -> dict:
    calculated_at = fetch_latest_calculated_at(conn, tf)
    data_freshness = fetch_data_freshness(conn)
    empty_rankings = {
        "top_borrow_pressure_usdt": [],
        "top_borrow_pressure_percent": [],
        "top_recovery_usdt": [],
        "top_recovery_percent": [],
    }
    if calculated_at is None:
        return {
            "tf": tf,
            "limit": limit,
            "exclude_stables": exclude_stables,
            "calculated_at": None,
            "data_freshness": data_freshness,
            "rankings": empty_rankings,
        }

    return {
        "tf": tf,
        "limit": limit,
        "exclude_stables": exclude_stables,
        "calculated_at": datetime_to_utc_iso(calculated_at),
        "data_freshness": data_freshness,
        "rankings": {
            "top_borrow_pressure_usdt": fetch_scanner_items(
                conn, tf, "borrow_pressure_usdt", limit, exclude_stables, calculated_at
            ),
            "top_borrow_pressure_percent": fetch_scanner_items(
                conn, tf, "borrow_pressure_percent", limit, exclude_stables, calculated_at
            ),
            "top_recovery_usdt": fetch_scanner_items(conn, tf, "recovery_usdt", limit, exclude_stables, calculated_at),
            "top_recovery_percent": fetch_scanner_items(
                conn, tf, "recovery_percent", limit, exclude_stables, calculated_at
            ),
        },
    }


def fetch_assets(conn: psycopg.Connection, exclude_stables: bool, search: str | None, limit: int) -> list[dict]:
    stable_sql, stable_params = _stable_filter_sql(exclude_stables)
    search_sql = ""
    search_params: list[Any] = []
    if search:
        search_sql = " AND latest_assets.asset ILIKE %s"
        search_params.append(f"%{search.strip()}%")

    params = [*stable_params, *search_params, limit]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH latest_snapshots AS (
              SELECT DISTINCT ON (asset)
                asset, available_inventory, collected_at
              FROM margin_pool_snapshots
              ORDER BY asset, collected_at DESC
            ),
            latest_prices AS (
              SELECT DISTINCT ON (asset)
                asset, symbol, price_usdt, collected_at
              FROM spot_price_snapshots
              ORDER BY asset, collected_at DESC
            ),
            latest_metrics AS (
              SELECT asset, MAX(calculated_at) AS calculated_at
              FROM borrow_pressure_metrics
              GROUP BY asset
            ),
            latest_assets AS (
              SELECT
                s.asset,
                s.available_inventory,
                p.price_usdt,
                p.symbol,
                s.collected_at AS latest_snapshot_at,
                m.calculated_at AS latest_metrics_calculated_at
              FROM latest_snapshots s
              LEFT JOIN latest_prices p ON p.asset = s.asset
              LEFT JOIN latest_metrics m ON m.asset = s.asset
            )
            SELECT *
            FROM latest_assets
            WHERE 1=1
              {stable_sql}
              {search_sql}
            ORDER BY asset ASC
            LIMIT %s
            """,
            params,
        )
        return [
            {
                "asset": row["asset"],
                "latest_available_inventory": decimal_to_str(row["available_inventory"]),
                "latest_spot_price_usdt": decimal_to_str(row["price_usdt"]),
                "price_symbol": row["symbol"],
                "price_available": row["price_usdt"] is not None,
                "latest_snapshot_at": datetime_to_utc_iso(row["latest_snapshot_at"]),
                "latest_metrics_calculated_at": datetime_to_utc_iso(row["latest_metrics_calculated_at"]),
            }
            for row in cur.fetchall()
        ]


def fetch_metrics_history(conn: psycopg.Connection, asset: str, tf: str, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              asset, timeframe, current_available_inventory, previous_available_inventory,
              net_pool_change_units, net_pool_change_percent, borrow_pressure_units,
              borrow_pressure_percent, borrow_pressure_usdt, recovery_units,
              recovery_percent, recovery_usdt, spot_price_usdt, price_symbol,
              price_available, current_snapshot_at, previous_snapshot_at, calculated_at
            FROM borrow_pressure_metrics
            WHERE UPPER(asset) = %s
              AND timeframe = %s
            ORDER BY calculated_at DESC
            LIMIT %s
            """,
            (normalize_asset(asset), tf, limit),
        )
        items = []
        for row in cur.fetchall():
            item = _scanner_item(row)
            item["tf"] = row["timeframe"]
            item["calculated_at"] = datetime_to_utc_iso(row["calculated_at"])
            items.append(item)
        return items


def fetch_pool_history(conn: psycopg.Connection, asset: str, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT asset, pool_type, available_inventory, collected_at, source
            FROM margin_pool_snapshots
            WHERE UPPER(asset) = %s
            ORDER BY collected_at DESC
            LIMIT %s
            """,
            (normalize_asset(asset), limit),
        )
        return [
            {
                "asset": row["asset"],
                "pool_type": row["pool_type"],
                "available_inventory": decimal_to_str(row["available_inventory"]),
                "snapshot_at": datetime_to_utc_iso(row["collected_at"]),
                "source": row["source"],
            }
            for row in cur.fetchall()
        ]
