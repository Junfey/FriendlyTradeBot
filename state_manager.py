# state_manager.py
import json
import os
from datetime import datetime

STATE_FILE = "strategies.json"


def load_strategies():
    """Загружает все стратегии из файла"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[ERROR] Ошибка при загрузке {STATE_FILE}: {e}")
    return {}


def save_strategies(all_data):
    """Сохраняет все стратегии в файл"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Ошибка при сохранении {STATE_FILE}: {e}")


def add_strategy(user_data, strategy_type, symbol, params):
    """Добавляет стратегию пользователя и сохраняет"""
    all_data = load_strategies()

    chat_id = user_data.get("chat_id")
    if not isinstance(chat_id, (str, int)):
        print(f"[WARN] Некорректный chat_id: {chat_id}")
        chat_id = "unknown"
    chat_id = str(chat_id)

    if chat_id not in all_data:
        all_data[chat_id] = {}

    key = f"{strategy_type}_{symbol}_{datetime.now().strftime('%H%M%S')}"
    all_data[chat_id][key] = {
        "strategy": strategy_type,
        "symbol": symbol,
        "params": params,
        "created": datetime.now().isoformat()
    }

    save_strategies(all_data)


def remove_strategy(user_data, key):
    """Удаляет стратегию по ключу"""
    all_data = load_strategies()
    chat_id = str(user_data.get("chat_id", "unknown"))

    if chat_id in all_data and key in all_data[chat_id]:
        del all_data[chat_id][key]
        save_strategies(all_data)