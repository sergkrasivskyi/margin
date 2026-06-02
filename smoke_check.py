from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from api.settings import SUPPORTED_METRICS, SUPPORTED_TIMEFRAMES


EXPECTED_ROUTES = {
    "/health",
    "/api/overview",
    "/api/scanner/latest",
    "/api/scanner/summary",
    "/api/assets",
    "/api/assets/{asset}/metrics-history",
    "/api/assets/{asset}/pool-history",
}

SMOKE_ENDPOINTS = (
    "/health",
    "/api/overview",
    "/api/scanner/latest?tf=15m&metric=borrow_pressure_usdt&limit=5",
    "/api/scanner/summary?tf=15m&limit=5",
    "/api/assets?limit=5",
    "/api/assets/BTC/metrics-history?tf=15m&limit=5",
    "/api/assets/BTC/pool-history?limit=5",
)


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

    client = TestClient(app)
    for path in SMOKE_ENDPOINTS:
        response = client.get(path)
        if response.status_code != 200:
            raise SystemExit(f"{path} returned {response.status_code}: {response.text[:500]}")

    invalid_tf = client.get("/api/scanner/latest?tf=2h")
    if invalid_tf.status_code != 422:
        raise SystemExit(f"invalid tf returned {invalid_tf.status_code}: {invalid_tf.text[:500]}")

    invalid_metric = client.get("/api/scanner/latest?metric=anomaly_score")
    if invalid_metric.status_code != 422:
        raise SystemExit(f"invalid metric returned {invalid_metric.status_code}: {invalid_metric.text[:500]}")

    print("smoke_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
