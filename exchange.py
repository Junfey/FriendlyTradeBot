import ccxt
from settings import settings, EXCHANGE_NAME, USE_TESTNET

def create_exchange():
    """Создаёт объект биржи CCXT с учётом тестнета и безопасных параметров."""
    exchange_class = getattr(ccxt, EXCHANGE_NAME)
    exchange = exchange_class({
        "apiKey": settings.api_key,
        "secret": settings.api_secret,
        "enableRateLimit": True,
        "options": {
            "adjustForTimeDifference": True,
            "recvWindow": 10000,
        },
    })

    # Если включён тестнет — активируем его
    if USE_TESTNET and hasattr(exchange, "set_sandbox_mode"):
        exchange.set_sandbox_mode(True)
        print("🧪 Binance запущен в TESTNET режиме")

    return exchange


# Глобальный экземпляр — можно просто импортировать из других файлов
exchange = create_exchange()
