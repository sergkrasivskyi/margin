from __future__ import annotations

from decimal import Decimal

from collector import db


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

