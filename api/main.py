from __future__ import annotations

from fastapi import FastAPI, Query

from api import db, scanner
from api.schemas import (
    AssetsResponse,
    DatabaseStatus,
    HealthResponse,
    MetricsHistoryResponse,
    OverviewResponse,
    PoolHistoryResponse,
    ScannerLatestResponse,
    ScannerSummaryResponse,
    StableFilterConfig,
)
from api.settings import (
    DEFAULT_EXCLUDE_STABLES,
    STABLE_ASSETS,
    SUPPORTED_METRICS,
    SUPPORTED_TIMEFRAMES,
    load_settings,
)

app = FastAPI(
    title="Margin Loan Research API",
    version="0.1.0",
    description="Read-only research API for Binance margin available-inventory metrics.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = load_settings()
    database_status = "ok"
    try:
        with db.connect(settings) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception:
        database_status = "error"

    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        service=settings.service_name,
        version=settings.version,
        database=DatabaseStatus(status=database_status),
        supported_timeframes=list(SUPPORTED_TIMEFRAMES),
    )


@app.get("/api/overview", response_model=OverviewResponse)
def overview() -> OverviewResponse:
    settings = load_settings()
    with db.connect(settings) as conn:
        payload = scanner.fetch_overview(conn)
    return OverviewResponse(
        latest_metrics_calculated_at=payload["latest_metrics_calculated_at"],
        data_freshness=payload["data_freshness"],
        overview=payload["overview"],
        stable_filter_config=StableFilterConfig(
            default_exclude_stables=DEFAULT_EXCLUDE_STABLES,
            stable_assets=list(STABLE_ASSETS),
        ),
    )


@app.get("/api/scanner/latest", response_model=ScannerLatestResponse)
def scanner_latest(
    tf: str = Query(default="15m", description="One of 15m, 30m, 1h, 4h"),
    metric: str = Query(default="borrow_pressure_usdt", description=", ".join(SUPPORTED_METRICS)),
    limit: int = Query(default=20, ge=1, le=100),
    exclude_stables: bool = Query(default=True),
) -> ScannerLatestResponse:
    valid_tf = scanner.validate_timeframe(tf)
    valid_metric = scanner.validate_metric(metric)
    settings = load_settings()
    with db.connect(settings) as conn:
        payload = scanner.fetch_scanner_latest(conn, valid_tf, valid_metric, limit, exclude_stables)
    return ScannerLatestResponse(**payload)


@app.get("/api/scanner/summary", response_model=ScannerSummaryResponse)
def scanner_summary(
    tf: str = Query(default="15m", description="One of 15m, 30m, 1h, 4h"),
    limit: int = Query(default=20, ge=1, le=100),
    exclude_stables: bool = Query(default=True),
) -> ScannerSummaryResponse:
    valid_tf = scanner.validate_timeframe(tf)
    settings = load_settings()
    with db.connect(settings) as conn:
        payload = scanner.fetch_scanner_summary(conn, valid_tf, limit, exclude_stables)
    return ScannerSummaryResponse(**payload)


@app.get("/api/assets", response_model=AssetsResponse)
def assets(
    exclude_stables: bool = Query(default=False),
    search: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
) -> AssetsResponse:
    settings = load_settings()
    with db.connect(settings) as conn:
        items = scanner.fetch_assets(conn, exclude_stables, search, limit)
    return AssetsResponse(exclude_stables=exclude_stables, search=search, limit=limit, items=items)


@app.get("/api/assets/{asset}/metrics-history", response_model=MetricsHistoryResponse)
def asset_metrics_history(
    asset: str,
    tf: str = Query(default="15m", description="One of 15m, 30m, 1h, 4h"),
    limit: int = Query(default=100, ge=1, le=100),
) -> MetricsHistoryResponse:
    valid_tf = scanner.validate_timeframe(tf)
    normalized_asset = scanner.normalize_asset(asset)
    settings = load_settings()
    with db.connect(settings) as conn:
        items = scanner.fetch_metrics_history(conn, normalized_asset, valid_tf, limit)
    return MetricsHistoryResponse(asset=normalized_asset, tf=valid_tf, limit=limit, items=items)


@app.get("/api/assets/{asset}/pool-history", response_model=PoolHistoryResponse)
def asset_pool_history(
    asset: str,
    limit: int = Query(default=100, ge=1, le=100),
) -> PoolHistoryResponse:
    normalized_asset = scanner.normalize_asset(asset)
    settings = load_settings()
    with db.connect(settings) as conn:
        items = scanner.fetch_pool_history(conn, normalized_asset, limit)
    return PoolHistoryResponse(asset=normalized_asset, limit=limit, items=items)
