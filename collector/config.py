from __future__ import annotations

import os
from dataclasses import dataclass


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
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    binance_api_key: str
    binance_api_secret: str
    watchlist_assets: list[str]
    kline_interval: str
    collector_interval_seconds: int
    pool_type: str
    collect_margin_assets: bool
    price_collection_mode: str
    scheduler_mode: str
    alignment_minutes: int
    collection_delay_seconds: int

    @property
    def symbols(self) -> list[str]:
        return [f"{asset}USDT" for asset in self.watchlist_assets]


def load_settings() -> Settings:
    _load_dotenv()
    watchlist_raw = os.getenv("WATCHLIST_ASSETS", "BTC,ETH,ARKM")
    watchlist_assets = [x.strip().upper() for x in watchlist_raw.split(",") if x.strip()]
    collect_margin_assets = os.getenv("COLLECT_MARGIN_ASSETS", "false").strip().lower() in {"1", "true", "yes", "on"}
    price_collection_mode = os.getenv("PRICE_COLLECTION_MODE", "scheduled").strip().lower()
    scheduler_mode = os.getenv("SCHEDULER_MODE", "aligned").strip().lower()
    return Settings(
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "margin_research"),
        postgres_user=os.getenv("POSTGRES_USER", "margin_user"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "change_me"),
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        watchlist_assets=watchlist_assets,
        kline_interval=os.getenv("KLINE_INTERVAL", "15m"),
        collector_interval_seconds=int(os.getenv("COLLECTOR_INTERVAL_SECONDS", "900")),
        pool_type=os.getenv("POOL_TYPE", "MARGIN").upper(),
        collect_margin_assets=collect_margin_assets,
        price_collection_mode=price_collection_mode,
        scheduler_mode=scheduler_mode,
        alignment_minutes=int(os.getenv("ALIGNMENT_MINUTES", "15")),
        collection_delay_seconds=int(os.getenv("COLLECTION_DELAY_SECONDS", "20")),
    )
