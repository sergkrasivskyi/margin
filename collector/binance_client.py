from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests


class BinanceAPIError(Exception):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, timeout_seconds: int = 15) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.binance.com"

    @staticmethod
    def _mask_api_key(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict | list:
        url = f"{self.base_url}{path}"
        request_params = dict(params or {})
        headers: dict[str, str] = {}

        if signed:
            if not self.api_key or not self.api_secret:
                raise BinanceAPIError(
                    "Binance API key/secret are required for signed request.",
                    {"endpoint": path, "signed": True},
                )
            request_params["timestamp"] = int(time.time() * 1000)
            query = urlencode(request_params, doseq=True)
            signature = hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
            request_params["signature"] = signature
            if self.api_key:
                headers["X-MBX-APIKEY"] = self.api_key
        sent_api_key_header = "X-MBX-APIKEY" in headers

        try:
            resp = requests.request(method=method, url=url, params=request_params, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise BinanceAPIError(
                f"HTTP request failed: {method} {url}",
                {
                    "method": method,
                    "url": url,
                    "params": request_params,
                    "api_key": self._mask_api_key(self.api_key),
                    "sent_api_key_header": sent_api_key_header,
                    "error": str(exc),
                },
            ) from exc

        if 200 <= resp.status_code < 300:
            return resp.json()

        response_text = resp.text[:2000]
        binance_code = None
        binance_msg = None
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                binance_code = payload.get("code")
                binance_msg = payload.get("msg")
        except ValueError:
            payload = None

        details = {
            "method": method,
            "url": url,
            "params": request_params,
            "status_code": resp.status_code,
            "response_text": response_text,
            "binance_code": binance_code,
            "binance_msg": binance_msg,
            "api_key": self._mask_api_key(self.api_key),
            "sent_api_key_header": sent_api_key_header,
            "signed": signed,
            "headers": {
                "content-type": resp.headers.get("Content-Type"),
                "x-mbx-used-weight": resp.headers.get("X-MBX-USED-WEIGHT"),
                "x-mbx-used-weight-1m": resp.headers.get("X-MBX-USED-WEIGHT-1M"),
            },
        }
        raise BinanceAPIError(f"Binance API error {resp.status_code} for {method} {url}", details)

    def get_margin_assets(self, asset: str | None = None) -> list[dict]:
        params = {"asset": asset} if asset else None
        data = self._request("GET", "/sapi/v1/margin/allAssets", params=params, signed=False)
        return data if isinstance(data, list) else []

    def get_margin_available_inventory(self, pool_type: str = "MARGIN") -> dict:
        params: dict[str, str | int] = {
            "type": pool_type,
            "recvWindow": 5000,
        }
        data = self._request("GET", "/sapi/v1/margin/available-inventory", params=params, signed=True)
        return data if isinstance(data, dict) else {}

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[list]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        data = self._request("GET", "/api/v3/klines", params=params, signed=False)
        return data if isinstance(data, list) else []
