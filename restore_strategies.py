#restore_strategies.py
import asyncio
import sys
import os
from datetime import datetime
from state_manager import load_strategies
from utils import get_exchange  # ✅ для проверки подключения

# === Настройки логов ===
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "restore.log")
os.makedirs(LOG_DIR, exist_ok=True)

# Добавляем текущую папку в sys.path для корректного импорта стратегий
sys.path.append(os.path.dirname(__file__))


def log_restore(message: str):
    """Записывает сообщение в restore.log и выводит в консоль."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[Ошибка записи лога]: {e}")


async def restore_strategies(app):
    """Восстановление всех активных стратегий при запуске."""
    try:
        data = load_strategies()
    except Exception as e:
        log_restore(f"❌ Ошибка загрузки стратегий: {e}")
        return

    if not data:
        log_restore("❌ Нет сохранённых стратегий для восстановления.")
        return

    # Проверим подключение к бирже
    try:
        exchange = get_exchange()
        log_restore("✅ Соединение с биржей установлено.")
    except Exception as e:
        log_restore(f"❌ Ошибка подключения к бирже перед восстановлением: {e}")
        return

    total = sum(len(v) for v in data.values() if isinstance(v, dict))
    restored_count = 0

    log_restore(f"🔁 Восстановление стратегий ({len(data)} пользователей, всего {total})...")

    for chat_id, user_strategies in data.items():
        # Приведение chat_id к числу
        try:
            chat_id_int = int(chat_id)
        except (ValueError, TypeError):
            log_restore(f"⚠️ Пропуск некорректного chat_id: {chat_id}")
            continue

        if not isinstance(user_strategies, dict):
            log_restore(f"⚠️ Некорректный формат стратегий у пользователя {chat_id}")
            continue

        for key, info in user_strategies.items():
            strategy = info.get("strategy") or info.get("type")
            symbol = info.get("symbol")
            params = info.get("params", {})

            if not strategy or not symbol:
                log_restore(f"⚠️ Пропуск некорректной записи стратегии: {info}")
                continue

            # Подготовка фиктивных объектов для вызова start_функций
            fake_update = type("FakeUpdate", (), {
                "message": type("msg", (), {"reply_text": lambda *_: None})(),
                "effective_chat": type("chat", (), {"id": chat_id_int})()
            })()

            fake_context = type("FakeContext", (), {
                "job_queue": app.job_queue,
                "user_data": {"chat_id": chat_id_int}
            })()

            try:
                interval = params.get("interval", 5)
                amount = params.get("amount")

                # === Запуск нужной стратегии ===
                if strategy == "percent":
                    from strategies.percent import start_percent_strategy
                    await start_percent_strategy(
                        fake_update, fake_context, symbol,
                        amount, params.get("step"), interval
                    )

                elif strategy == "range":
                    from strategies.range import start_range_strategy
                    await start_range_strategy(
                        fake_update, fake_context, symbol,
                        amount, params.get("low"), params.get("high"), interval
                    )

                elif strategy == "dca":
                    from strategies.dca import start_dca_strategy
                    await start_dca_strategy(
                        fake_update, fake_context, symbol,
                        amount, interval
                    )

                restored_count += 1
                log_restore(f"✅ Восстановлена {strategy.upper()} для {symbol} (пользователь {chat_id})")

            except Exception as e:
                log_restore(f"⚠️ Ошибка при восстановлении {strategy} для {symbol} (пользователь {chat_id}): {e}")

    log_restore(f"🏁 Восстановление завершено. Успешно восстановлено: {restored_count}/{total}.")
