from __future__ import annotations

import os
from dataclasses import dataclass

SUPPORTED_TIMEFRAMES = ("15m", "30m", "1h", "4h")
SUPPORTED_METRICS = (
    "borrow_pressure_usdt",
    "borrow_pressure_percent",
    "recovery_usdt",
    "recovery_percent",
)
STABLE_ASSETS = ("USDT", "USDC", "FDUSD", "TUSD", "DAI", "USTC")
DEFAULT_EXCLUDE_STABLES = True
STALE_AFTER_SECONDS = 1800


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class ApiSettings:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    service_name: str = "margin-loan-api"
    version: str = "0.1.1"


def load_settings() -> ApiSettings:
    _load_dotenv()
    return ApiSettings(
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "margin_research"),
        postgres_user=os.getenv("POSTGRES_USER", "margin_user"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
