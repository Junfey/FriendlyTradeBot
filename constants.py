
# constants.py

"""
Глобальные константы для торгового бота FriendlyTradeBot.
Хранятся отдельно, чтобы избежать циклических импортов и дублирования.
"""

from decimal import Decimal


# === Минимальные лимиты и фильтры ===
MIN_ORDER_USD = Decimal("5.0")     # минимальная сумма ордера в долларах
MIN_USD_VALUE = 5.0                # минимальная стоимость позиции для отображения
MAX_PRICE_CHECKS = 40              # максимум запросов цены при выводе баланса

# === Интервалы и тайминги ===
DEFAULT_STRATEGY_INTERVAL = 5      # интервал по умолчанию (минуты)
MAX_STRATEGIES_PER_USER = 10       # лимит на количество активных стратегий

# === Биржевые настройки ===
DEFAULT_EXCHANGE = "binance"       # биржа по умолчанию
DEFAULT_USE_TESTNET = True         # использовать тестовую сеть, если не указано иное

# === Отображение и логика ===
MAJOR_ASSETS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "LTC", "DOT", "TRX", "MATIC"]