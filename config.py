# config.py
# Безопасная загрузка ключей и токенов из окружения или приватного файла
import os
import json
from pathlib import Path


def _load_private():
    """Загружает конфиг из config_private.json, если он существует."""
    p = Path(__file__).parent / "config_private.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            print("[WARNING] config_private.json повреждён или пустой.")
            return {}
    return {}


_private = _load_private()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or _private.get("TELEGRAM_TOKEN")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY") or _private.get("EXCHANGE_API_KEY")
EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET") or _private.get("EXCHANGE_API_SECRET")
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME") or _private.get("EXCHANGE_NAME", "binance")
USE_TESTNET = (os.getenv("USE_TESTNET") or str(_private.get("USE_TESTNET", "true"))).lower() in ("1", "true", "yes")

# Подсказка:
# создайте файл config_private.json в корне проекта с содержимым:
# {
#   "TELEGRAM_TOKEN": "ваш_токен_бота",
#   "EXCHANGE_API_KEY": "ключ_от_биржи",
#   "EXCHANGE_API_SECRET": "секрет_от_биржи"
# }




# Конфиг для бота

#TELEGRAM_TOKEN = "8453891177:AAEar4e1YljvpI0euqPjjEOVQCddfBhMtL4"

# Ключи Binance Testnet (генерируй на https://testnet.binance.vision
#EXCHANGE_API_KEY = "wapArkIiQaCaNkfMTOtsWUPfLeLODVZJ49ffdc10lQEVwR2Z0LKFTxEiewP4MKJs"
#EXCHANGE_API_SECRET = "WPUuklw2e8WvQnNiLWZTtTXXiEHUPKsda55cqRtQigHCpM2Ksho320I3yxque0sd"

# Оставь "binance" если используешь Binance
#EXCHANGE_NAME = "binance"  # можно менять на другую биржу, которую поддерживает CCXT

# True — использовать тестовую (sandbox) сеть Binance
#USE_TESTNET = True
