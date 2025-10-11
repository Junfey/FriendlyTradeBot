# settings.py — пользовательские настройки отображения

# Основные валюты для кнопки "📋 Все основные валюты"
MAIN_COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA",
    "LTC", "DOT", "TRX", "MATIC", "USDT"
]

# Игнорируемые фантики и клоны стейблов
IGNORE_COINS = {
    "USD1", "XUSD", "BFUSD", "USDP", "AEUR", "USDE", "EURI"
}

# Минимальный порог (например, скрывать балансы < 0.01)
MIN_BALANCE = 0.01
