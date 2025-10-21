#utils.py
import logging
import asyncio
import ccxt
import time
from typing import Dict, Any, Tuple, List
from state_manager import load_strategies, save_strategies
from config import EXCHANGE_API_KEY, EXCHANGE_API_SECRET, EXCHANGE_NAME, USE_TESTNET

exchange = None  # глобальная переменная


logger = logging.getLogger(__name__)

COMMON_QUOTES = ["USDT", "BTC", "ETH", "BUSD", "USDC", "USD", "EUR"]

# Локи по символам (чтобы не было одновременных ордеров на одной паре)
_order_locks: Dict[str, asyncio.Lock] = {}



# utils.py
import logging
import asyncio
import ccxt
import time
from typing import Dict, Any, Tuple, List
from state_manager import load_strategies, save_strategies
from config import EXCHANGE_API_KEY, EXCHANGE_API_SECRET, EXCHANGE_NAME, USE_TESTNET

exchange = None
logger = logging.getLogger(__name__)

COMMON_QUOTES = ["USDT", "BTC", "ETH", "BUSD", "USDC", "USD", "EUR"]
_order_locks: Dict[str, asyncio.Lock] = {}


def get_exchange(force_reconnect: bool = False):
    """
    Создаёт или восстанавливает подключение к бирже (например Binance).
    При обрыве связи — делает повтор через 10 секунд.
    """
    global exchange

    # ✅ Не пересоздаём соединение, если уже живое
    if not force_reconnect and exchange and hasattr(exchange, "markets") and exchange.markets:
        try:
            # Проверка соединения лёгким запросом
            exchange.fetch_time()
            return exchange
        except Exception:
            logging.warning("⚠️ Старое соединение мертво, переподключение...")

    while True:
        try:
            logging.info("🔄 Подключение к бирже...")

            exchange_class = getattr(ccxt, EXCHANGE_NAME)
            exchange = exchange_class({
                "apiKey": EXCHANGE_API_KEY,
                "secret": EXCHANGE_API_SECRET,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True
                }
            })

            if USE_TESTNET and hasattr(exchange, "set_sandbox_mode"):
                exchange.set_sandbox_mode(True)
                logging.info("🧪 Используется тестовая сеть Binance (Testnet).")

            exchange.check_required_credentials()
            exchange.load_markets()
            exchange.fetch_time()  # пробное обращение
            logging.info("✅ Успешное подключение к бирже.")
            return exchange

        except ccxt.NetworkError as e:
            logging.warning(f"⚠️ Ошибка сети: {e}. Повтор через 10 сек...")
        except ccxt.AuthenticationError:
            logging.error("❌ Ошибка API-ключей. Проверь config.py.")
            raise
        except Exception as e:
            logging.error(f"❌ Неизвестная ошибка подключения: {e}")

        time.sleep(10)



async def reconnect_exchange(delay: int = 10):
    """
    Асинхронное и безопасное переподключение к бирже.
    Не блокирует event loop и не мешает работе других задач.
    """
    global exchange
    logging.warning(f"♻️ Переподключение к бирже через {delay} секунд...")
    await asyncio.sleep(delay)  # не блокирует

    try:
        new_exchange = await asyncio.to_thread(get_exchange, True)  # форсируем reconnect
        if new_exchange:
            exchange = new_exchange
            logging.info("✅ Переподключение успешно.")
    except Exception as e:
        logging.warning(f"⚠️ Ошибка переподключения: {e}")





async def reconnect_exchange(delay: int = 10):
    """
    Асинхронное и безопасное переподключение к бирже.
    Не блокирует event loop и не мешает работе других задач.
    """
    global exchange
    logging.warning(f"♻️ Переподключение к бирже через {delay} секунд...")
    await asyncio.sleep(delay)  # не блокирует

    try:
        new_exchange = await asyncio.to_thread(get_exchange)  # выполняет в отдельном потоке
        if new_exchange:
            exchange = new_exchange
            logging.info("✅ Переподключение успешно.")
    except Exception as e:
        logging.warning(f"⚠️ Ошибка переподключения: {e}")


# --- Безопасное добавление стратегии ---
def safe_add_strategy(update_or_user, strategy_type, symbol, params):
    """
    Безопасно добавляет стратегию (через state_manager),
    проверяя дубликаты и сохраняя в общем формате.
    """
    from state_manager import load_strategies, save_strategies
    import datetime

    try:
        if hasattr(update_or_user, "effective_chat"):
            chat_id = str(update_or_user.effective_chat.id)
        elif isinstance(update_or_user, dict):
            chat_id = str(update_or_user.get("chat_id", "unknown"))
        else:
            chat_id = "unknown"

        all_data = load_strategies()
        if chat_id not in all_data:
            all_data[chat_id] = {}

        # Проверяем дубликаты
        exists = any(
            s.get("symbol") == symbol and s.get("type") == strategy_type
            for s in all_data[chat_id].values()
        )
        if exists:
            logger.warning(f"[safe_add_strategy] ⚠️ Стратегия {strategy_type}:{symbol} уже существует — пропуск.")
            return False

        # Генерация ID
        strategy_id = f"{strategy_type}_{symbol}_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')}"

        all_data[chat_id][strategy_id] = {
            "type": strategy_type,
            "symbol": symbol,
            "parameters": params,
            "created_at": datetime.datetime.now().isoformat()
        }

        save_strategies(all_data)
        logger.info(f"[safe_add_strategy] ✅ Добавлена стратегия {strategy_type}:{symbol} ({strategy_id})")
        return True

    except Exception as e:
        logger.exception(f"[safe_add_strategy] ❌ Ошибка добавления стратегии: {e}")
        return False







# --- Нормализация символа ---
def normalize_symbol(symbol: str) -> str:
    s = symbol.replace(" ", "").replace("-", "").upper()
    if "/" in s:
        return s
    for quote in COMMON_QUOTES:
        if s.endswith(quote):
            base = s[:-len(quote)]
            return f"{base}/{quote}"
    return s


# --- Получение баланса ---
def get_balance() -> Dict[str, float]:
    try:
        bal = exchange.fetch_balance()
        totals = bal.get("total", bal)
        result = {
            asset: float(amt)
            for asset, amt in totals.items()
            if isinstance(amt, (int, float)) and amt > 0
        }
        return result
    except Exception:
        logger.exception("get_balance error")
        raise


# --- Получение цены ---
def get_price(symbol: str):
    try:
        if symbol not in exchange.symbols:
            logger.warning(f"❌ Пара {symbol} не поддерживается")
            return None
        ticker = exchange.fetch_ticker(symbol)
        return ticker.get("last")
    except Exception as e:
        logger.error(f"Ошибка get_price {symbol}: {e}")
        return None


# --- Проверка минимального ордера ---
def _check_min_order(symbol: str, amount: float) -> Tuple[bool, str]:
    market = exchange.markets.get(symbol)
    if not market:
        return False, f"❌ Пара {symbol} не найдена."

    price = get_price(symbol)
    if not price:
        return False, f"❌ Не удалось получить цену {symbol}"

    cost = amount * price
    min_cost = market["limits"]["cost"]["min"]
    if min_cost and cost < min_cost:
        return False, f"❌ Ордер слишком мал: {cost:.2f} < {min_cost:.2f} USDT"
    return True, ""


# --- Проверка баланса ---
def has_enough_balance(symbol: str, side: str, amount: float) -> Tuple[bool, str]:
    try:
        balance = get_balance()
        base, quote = symbol.split("/")
        price = get_price(symbol)

        if not price:
            return False, "❌ Не удалось получить цену"

        if side == "buy":
            required_quote = price * amount
            available_quote = float(balance.get(quote, 0))
            return (
                available_quote >= required_quote,
                f"Баланс {quote}={available_quote:.4f}, нужно {required_quote:.4f}"
            )
        elif side == "sell":
            available_base = float(balance.get(base, 0))
            return (
                available_base >= amount,
                f"Баланс {base}={available_base:.4f}, нужно {amount:.4f}"
            )

        return False, "❌ Неизвестный side"
    except Exception as e:
        return False, f"❌ Ошибка проверки баланса: {e}"


# --- Размещение ордера с блокировкой ---
async def place_market_order_safe(symbol: str, side: str, amount: float):
    symbol = normalize_symbol(symbol)
    if symbol not in _order_locks:
        _order_locks[symbol] = asyncio.Lock()

    async with _order_locks[symbol]:
        ok, msg = _check_min_order(symbol, amount)
        if not ok:
            raise Exception(msg)

        ok, msg = has_enough_balance(symbol, side, amount)
        if not ok:
            raise Exception(msg)

        try:
            order = await asyncio.to_thread(exchange.create_market_order, symbol, side, amount)
            logger.info(f"✅ Market order {side} {amount} {symbol} executed.")
            return order
        except Exception as e:
            logger.error(f"place_market_order error: {e}")
            raise

# --- Инициализация соединения ---
exchange = get_exchange()
