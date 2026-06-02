from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


def decimal_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def datetime_to_utc_iso(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class DatabaseStatus(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: DatabaseStatus
    supported_timeframes: list[str]


class TimeframeOverview(BaseModel):
    tf: str
    rows: int
    price_available_rows: int
    price_unavailable_rows: int


class StableFilterConfig(BaseModel):
    default_exclude_stables: bool
    stable_assets: list[str]


class DataFreshness(BaseModel):
    latest_metrics_calculated_at: str | None
    latest_metrics_age_seconds: int | None
    latest_snapshot_at: str | None
    latest_snapshot_age_seconds: int | None
    last_collector_run_status: str | None
    last_collector_run_finished_at: str | None
    is_data_stale: bool
    stale_after_seconds: int


class OverviewResponse(BaseModel):
    latest_metrics_calculated_at: str | None
    data_freshness: DataFreshness
    overview: list[TimeframeOverview]
    stable_filter_config: StableFilterConfig


class ScannerItem(BaseModel):
    asset: str
    current_available_inventory: str
    previous_available_inventory: str
    net_pool_change_units: str | None
    net_pool_change_percent: str | None
    borrow_pressure_units: str
    borrow_pressure_percent: str | None
    borrow_pressure_usdt: str | None
    recovery_units: str
    recovery_percent: str | None
    recovery_usdt: str | None
    spot_price_usdt: str | None
    price_symbol: str | None
    price_available: bool
    current_snapshot_at: str
    previous_snapshot_at: str


class ScannerLatestResponse(BaseModel):
    tf: str
    metric: str
    limit: int
    exclude_stables: bool
    calculated_at: str | None
    data_freshness: DataFreshness
    items: list[ScannerItem]


class ScannerSummaryRankings(BaseModel):
    top_borrow_pressure_usdt: list[ScannerItem]
    top_borrow_pressure_percent: list[ScannerItem]
    top_recovery_usdt: list[ScannerItem]
    top_recovery_percent: list[ScannerItem]


class ScannerSummaryResponse(BaseModel):
    tf: str
    limit: int
    exclude_stables: bool
    calculated_at: str | None
    data_freshness: DataFreshness
    rankings: ScannerSummaryRankings


class AssetState(BaseModel):
    asset: str
    latest_available_inventory: str | None
    latest_spot_price_usdt: str | None
    price_symbol: str | None
    price_available: bool
    latest_snapshot_at: str | None
    latest_metrics_calculated_at: str | None


class AssetsResponse(BaseModel):
    exclude_stables: bool
    search: str | None
    limit: int
    items: list[AssetState]


class MetricsHistoryItem(ScannerItem):
    tf: str
    calculated_at: str


class MetricsHistoryResponse(BaseModel):
    asset: str
    tf: str
    limit: int
    items: list[MetricsHistoryItem]


class PoolHistoryItem(BaseModel):
    asset: str
    pool_type: str
    available_inventory: str
    snapshot_at: str
    source: str


class PoolHistoryResponse(BaseModel):
    asset: str
    limit: int
    items: list[PoolHistoryItem]
