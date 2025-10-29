import time
import hmac
import hashlib
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiolimiter import AsyncLimiter
from typing import Dict, Any, Optional
from settings import settings

_BINANCE_BASE = "https://api.binance.com"
_BINANCE_TEST = "https://testnet.binance.vision"

class BinanceExchange:
    def __init__(self):
        self.api_key = settings.BINANCE_API_KEY
        self.secret = settings.BINANCE_API_SECRET.encode()
        self.base = _BINANCE_TEST if settings.MODE == "testnet" else _BINANCE_BASE
        # Простой лимитер: 10 запросов/сек — подстрой под реальные лимиты
        self.limiter = AsyncLimiter(10, 1)
        self._client = httpx.AsyncClient(base_url=self.base, timeout=20.0)

        self._exchange_info_cache: Optional[Dict[str, Any]] = None
        self._exchange_info_ts: float = 0.0

    async def _auth_headers(self) -> Dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = httpx.QueryParams(params).encode()
        sig = hmac.new(self.secret, query, hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _get(self, path: str, params: Dict[str, Any] | None = None, signed: bool = False):
        async with self.limiter:
            if signed:
                if params is None:
                    params = {}
                params["timestamp"] = int(time.time() * 1000)
                params = self._sign(params)
            r = await self._client.get(path, params=params, headers=(await self._auth_headers() if signed else None))
            r.raise_for_status()
            return r.json()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _post(self, path: str, params: Dict[str, Any] | None = None, signed: bool = False):
        async with self.limiter:
            if signed:
                if params is None:
                    params = {}
                params["timestamp"] = int(time.time() * 1000)
                params = self._sign(params)
            r = await self._client.post(path, params=params, headers=(await self._auth_headers() if signed else None))
            r.raise_for_status()
            return r.json()

    async def close(self):
        await self._client.aclose()

    async def get_exchange_info(self) -> Dict[str, Any]:
        now = time.time()
        if not self._exchange_info_cache or now - self._exchange_info_ts > 900:  # 15 минут
            data = await self._get("/api/v3/exchangeInfo")
            self._exchange_info_cache = data
            self._exchange_info_ts = now
        return self._exchange_info_cache

    async def _normalize_symbol(self, symbol: str) -> str:
        return symbol.replace("/", "").upper()

    async def get_price(self, symbol: str) -> float:
        sym = await self._normalize_symbol(symbol)
        data = await self._get("/api/v3/ticker/price", params={"symbol": sym})
        return float(data["price"])

    async def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float | None = None, client_id: str | None = None) -> Dict[str, Any]:
        sym = await self._normalize_symbol(symbol)
        params: Dict[str, Any] = {
            "symbol": sym,
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": f"{quantity:.8f}".rstrip("0").rstrip("."),
            "newClientOrderId": client_id or f"ftb_{int(time.time()*1000)}",
        }
        if type_.upper() == "LIMIT":
            assert price is not None
            params["price"] = f"{price:.8f}".rstrip("0").rstrip(".")
            params["timeInForce"] = "GTC"

        # Пре-чек шагов и minNotional можно добавить здесь, используя exchangeInfo

        return await self._post("/api/v3/order", params=params, signed=True)

    async def cancel(self, symbol: str, order_id: str | None = None, client_id: str | None = None) -> Dict[str, Any]:
        sym = await self._normalize_symbol(symbol)
        params: Dict[str, Any] = {"symbol": sym}
        if order_id:
            params["orderId"] = order_id
        if client_id:
            params["origClientOrderId"] = client_id
        return await self._delete("/api/v3/order", params=params, signed=True)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _delete(self, path: str, params: Dict[str, Any] | None = None, signed: bool = False):
        async with self.limiter:
            if signed:
                if params is None:
                    params = {}
                params["timestamp"] = int(time.time() * 1000)
                params = self._sign(params)
            r = await self._client.delete(path, params=params, headers=(await self._auth_headers() if signed else None))
            r.raise_for_status()
            return r.json()

    async def get_balance(self, asset: str) -> float:
        data = await self._get("/api/v3/account", signed=True)
        for b in data.get("balances", []):
            if b["asset"] == asset.upper():
                return float(b["free"])
        return 0.0
