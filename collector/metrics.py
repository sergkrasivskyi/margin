from __future__ import annotations

from decimal import Decimal

from collector import db

SpotPriceMap = dict[str, dict[str, Decimal | str]]


def calculate_and_store_pool_metrics(conn) -> int:
    snapshots = db.fetch_latest_unprocessed_snapshots(conn)
    inserted = 0

    for snap in snapshots:
        current = Decimal(snap["available_inventory"])
        previous = db.fetch_previous_snapshot(conn, snap["asset"], snap["pool_type"], snap["collected_at"])

        if previous is None:
            pool_change = None
            pool_change_percent = None
            pool_decrease = Decimal("0")
            pool_recovery = Decimal("0")
        else:
            pool_change = current - previous
            pool_change_percent = (pool_change / previous * Decimal("100")) if previous > 0 else None
            pool_decrease = max(Decimal("0"), previous - current)
            pool_recovery = max(Decimal("0"), current - previous)

        row = {
            "asset": snap["asset"],
            "pool_type": snap["pool_type"],
            "timestamp": snap["collected_at"],
            "available_inventory": current,
            "previous_available_inventory": previous,
            "pool_change": pool_change,
            "pool_change_percent": pool_change_percent,
            "pool_decrease": pool_decrease,
            "pool_recovery": pool_recovery,
            "borrow_pressure_proxy": pool_decrease,
            "repay_or_refill_proxy": pool_recovery,
        }
        db.insert_pool_metric(conn, row)
        inserted += 1

    conn.commit()
    return inserted


def calculate_and_store_borrow_pressure_metrics(conn, spot_price_map: SpotPriceMap | None = None) -> dict:
    spot_price_map = spot_price_map or {}
    current_snapshot_at = db.fetch_latest_snapshot_timestamp(conn)
    if current_snapshot_at is None:
        return {
            "calculated": 0,
            "calculated_by_timeframe": {timeframe: 0 for timeframe in db.BORROW_PRESSURE_TIMEFRAMES},
            "price_available_count": 0,
            "price_unavailable_count": 0,
            "sample_price_matches": [],
        }

    current_block = db.fetch_snapshot_block(conn, current_snapshot_at)
    if not current_block:
        return {
            "calculated": 0,
            "calculated_by_timeframe": {timeframe: 0 for timeframe in db.BORROW_PRESSURE_TIMEFRAMES},
            "price_available_count": 0,
            "price_unavailable_count": 0,
            "sample_price_matches": [],
        }

    db.delete_borrow_pressure_metrics_for_snapshot(conn, current_snapshot_at)
    inserted = 0
    price_available_count = 0
    price_unavailable_count = 0
    sample_price_matches: list[dict] = []
    calculated_by_timeframe = {timeframe: 0 for timeframe in db.BORROW_PRESSURE_TIMEFRAMES}

    for snap in current_block:
        current_pool = Decimal(snap["available_inventory"])

        for timeframe, delta in db.BORROW_PRESSURE_TIMEFRAMES.items():
            previous_snapshot = db.fetch_previous_snapshot_for_timeframe(
                conn,
                snap["asset"],
                snap["pool_type"],
                current_snapshot_at - delta,
            )
            if previous_snapshot is None:
                continue

            previous_pool = Decimal(previous_snapshot["available_inventory"])
            net_pool_change_units = current_pool - previous_pool
            net_pool_change_percent = (net_pool_change_units / previous_pool * Decimal("100")) if previous_pool > 0 else None
            borrow_pressure_units = max(Decimal("0"), previous_pool - current_pool)
            borrow_pressure_percent = (borrow_pressure_units / previous_pool * Decimal("100")) if previous_pool > 0 else None
            recovery_units = max(Decimal("0"), current_pool - previous_pool)
            recovery_percent = (recovery_units / previous_pool * Decimal("100")) if previous_pool > 0 else None

            spot_price = spot_price_map.get(snap["asset"])
            if spot_price is None:
                spot_price = db.fetch_latest_spot_price_for_asset(conn, snap["asset"])
            price_available = spot_price is not None
            spot_price_usdt = Decimal(spot_price["price_usdt"]) if price_available else None
            price_symbol = spot_price["symbol"] if price_available else None
            borrow_pressure_usdt = borrow_pressure_units * spot_price_usdt if price_available else None
            recovery_usdt = recovery_units * spot_price_usdt if price_available else None
            if price_available:
                price_available_count += 1
                if len(sample_price_matches) < 10:
                    sample_price_matches.append(
                        {
                            "asset": snap["asset"],
                            "symbol": price_symbol,
                            "price_usdt": str(spot_price_usdt),
                            "timeframe": timeframe,
                        }
                    )
            else:
                price_unavailable_count += 1

            db.insert_borrow_pressure_metric(
                conn,
                {
                    "asset": snap["asset"],
                    "timeframe": timeframe,
                    "current_available_inventory": current_pool,
                    "previous_available_inventory": previous_pool,
                    "net_pool_change_units": net_pool_change_units,
                    "net_pool_change_percent": net_pool_change_percent,
                    "borrow_pressure_units": borrow_pressure_units,
                    "borrow_pressure_percent": borrow_pressure_percent,
                    "borrow_pressure_usdt": borrow_pressure_usdt,
                    "recovery_units": recovery_units,
                    "recovery_percent": recovery_percent,
                    "recovery_usdt": recovery_usdt,
                    "spot_price_usdt": spot_price_usdt,
                    "price_symbol": price_symbol,
                    "price_available": price_available,
                    "current_snapshot_at": current_snapshot_at,
                    "previous_snapshot_at": previous_snapshot["collected_at"],
                },
            )
            inserted += 1
            calculated_by_timeframe[timeframe] += 1

    conn.commit()
    return {
        "calculated": inserted,
        "calculated_by_timeframe": calculated_by_timeframe,
        "price_available_count": price_available_count,
        "price_unavailable_count": price_unavailable_count,
        "sample_price_matches": sample_price_matches,
    }
