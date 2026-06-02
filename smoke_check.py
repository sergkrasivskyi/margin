from __future__ import annotations

from api.main import app
from api.settings import SUPPORTED_METRICS, SUPPORTED_TIMEFRAMES


EXPECTED_ROUTES = {
    "/health",
    "/api/overview",
    "/api/scanner/latest",
    "/api/assets",
    "/api/assets/{asset}/metrics-history",
    "/api/assets/{asset}/pool-history",
}


def main() -> int:
    route_paths = {getattr(route, "path", "") for route in app.routes}
    missing_routes = sorted(EXPECTED_ROUTES - route_paths)
    if missing_routes:
        raise SystemExit(f"Missing routes: {missing_routes}")

    if SUPPORTED_TIMEFRAMES != ("15m", "30m", "1h", "4h"):
        raise SystemExit(f"Unexpected timeframes: {SUPPORTED_TIMEFRAMES}")

    expected_metrics = {
        "borrow_pressure_usdt",
        "borrow_pressure_percent",
        "recovery_usdt",
        "recovery_percent",
    }
    if set(SUPPORTED_METRICS) != expected_metrics:
        raise SystemExit(f"Unexpected metrics: {SUPPORTED_METRICS}")

    print("smoke_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
