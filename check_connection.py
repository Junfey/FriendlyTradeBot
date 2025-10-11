# check_connection.py
import ccxt
import logging
import os
from config import EXCHANGE_API_KEY, EXCHANGE_API_SECRET

# Временно устанавливаем уровень логов для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_connection():
    try:
        logger.info("Попытка подключения к Binance Spot Testnet...")

        # Создаем объект биржи
        exchange = ccxt.binance({
            "apiKey": EXCHANGE_API_KEY,
            "secret": EXCHANGE_API_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                "default_spot_url": "https://testnet.binance.vision"
            }
        })
        exchange.set_sandbox_mode(True)

        # 🔹 Добавляем обновление данных и проверку ключей
        exchange.check_required_credentials()
        exchange.load_markets()
        logger.info("✅ Данные о рынках обновлены, ключи проверены.")

        # Пытаемся получить баланс
        balance = exchange.fetch_balance()
        logger.info("✅ Успешное подключение! Баланс получен:")

        for asset, amount in balance['total'].items():
            if amount > 0:
                print(f"  {asset}: {amount}")

    except ccxt.NetworkError as e:
        logger.error(f"❌ Ошибка сети (возможно, таймаут): {e}")
    except ccxt.AuthenticationError:
        logger.error("❌ Ошибка аутентификации: проверьте ключи API.")
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка: {e}")

if __name__ == "__main__":
    check_connection()

