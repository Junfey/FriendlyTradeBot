# menus.py
from telegram import ReplyKeyboardMarkup

# Главное меню
def get_main_menu():
    return ReplyKeyboardMarkup(
        [
            ["📊 Баланс"],
            ["💵 Купить", "💰 Продать"],
            ["⚡ Стратегии"],
            ["🔍 Проверить цену", "📋 Все основные валюты"],
            ["📋 Активные стратегии"],
            ["🛑 Стоп все"],
        ],
        resize_keyboard=True
    )

# Меню стратегий
def get_strategies_menu():
    return ReplyKeyboardMarkup(
        [
            ["Percent", "Range", "DCA"],
            ["⬅️ Назад в главное меню"]
        ],
        resize_keyboard=True
    )

# Универсальное меню "Назад"
def get_back_menu():
    return ReplyKeyboardMarkup(
        [
            ["⬅️ Назад в главное меню"]
        ],
        resize_keyboard=True
    )
