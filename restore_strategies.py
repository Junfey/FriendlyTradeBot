# restore_strategies.py
import asyncio
import sys
import os
from datetime import datetime
from types import SimpleNamespace
from state_manager import load_strategies
from utils import get_exchange

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "restore.log")

sys.path.append(os.path.dirname(__file__))

def log_restore(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[ERROR writing restore log]: {e}")

async def restore_strategies(app=None):
    log_restore("🔁 Запуск восстановления стратегий...")

    try:
        data = load_strategies()
    except Exception as e:
        log_restore(f"❌ Ошибка загрузки сохранённых стратегий: {e}")
        return

    if not data:
        log_restore("⚠️ Нет сохранённых стратегий для восстановления.")
        return

    exchange = None
    for attempt in range(1, 6):
        try:
            exchange = get_exchange()
            log_restore(f"✅ Соединение с биржей установлено (попытка {attempt}).")
            break
        except Exception as e:
            wait = min(60, 2 ** attempt * 2)
            log_restore(f"⚠️ Ошибка подключения (попытка {attempt}/5): {e}. Повтор через {wait}s...")
            await asyncio.sleep(wait)
    if exchange is None:
        log_restore("❌ Не удалось подключиться к бирже. Отмена.")
        return

    total = sum(len(v) for v in data.values() if isinstance(v, list))
    restored_count = 0
    log_restore(f"🔁 Восстановление стратегий ({len(data)} пользователей, всего {total})...")

    app.bot_data.setdefault("active_strategies", {})

    for chat_id, strategies in data.items():
        try:
            chat_id = int(chat_id)
        except Exception:
            continue

        app.bot_data["active_strategies"].setdefault(chat_id, [])

        async def fake_reply_text(*args, **kwargs):
            msg = ' '.join(str(a) for a in args)
            print(f"[restore_info] {msg}")

        fake_update = SimpleNamespace(
            message=SimpleNamespace(reply_text=fake_reply_text),
            effective_chat=SimpleNamespace(id=chat_id)
        )
        fake_context = SimpleNamespace(
            bot=None,
            application=app,
            job_queue=getattr(app, "job_queue", None),
            user_data={"chat_id": chat_id}
        )

        for strat in strategies:
            strategy = strat.get("type")
            symbol = strat.get("symbol")
            params = strat.get("params", {})

            if not strategy or not symbol:
                continue

                # НЕ добавляем в bot_data заранее — сначала пробуем запустить стратегию
                try:
                    st = str(strategy).lower()
                    started = False

                    if st in ("range", "rng", "r"):
                        from strategies.range import start_range_strategy
                        started = await start_range_strategy(
                            fake_update,
                            fake_context,
                            symbol,
                            params.get("amount"),
                            params.get("low"),
                            params.get("high"),
                            params.get("interval"),
                        )

                    elif st == "dca":
                        from strategies.dca import start_dca_strategy
                        started = await start_dca_strategy(
                            fake_update,
                            fake_context,
                            symbol,
                            params.get("amount"),
                            params.get("interval"),
                        )

                    elif st in ("percent", "pct", "percentual"):
                        from strategies.percent import start_percent_strategy
                        started = await start_percent_strategy(
                            fake_update,
                            fake_context,
                            symbol,
                            params.get("amount"),
                            params.get("step"),
                            params.get("interval"),
                        )

                    else:
                        log_restore(f"⚠️ Неизвестный тип стратегии '{strategy}' ({symbol}) — пропуск.")
                        continue

                    if started:
                        # Добавляем только успешные старты в bot_data и считаем в restored_count
                        app.bot_data.setdefault("active_strategies", {})
                        app.bot_data["active_strategies"].setdefault(chat_id_int, [])
                        app.bot_data["active_strategies"][chat_id_int].append({
                            "type": strategy,
                            "symbol": symbol,
                            "params": params,
                            "timestamp": datetime.now().isoformat()
                        })
                        restored_count += 1
                        log_restore(f"✅ Восстановлена {strategy.upper()} для {symbol} (user {chat_id})")
                    else:
                        log_restore(
                            f"⚠️ Пропуск запуска {strategy} для {symbol} (user {chat_id}) — старт отменён/неуспешен.")

                except Exception as e:
                    log_restore(f"❌ Ошибка при восстановлении {strategy} ({symbol}): {e}")
                    continue

        # --- Завершение ---
        log_restore(f"🏁 Восстановление завершено. Успешно: {restored_count}/{total}")

        # Отправляем сообщение пользователям, если восстановление прошло
        bot = app.bot
        for chat_id, strategies in app.bot_data.get("active_strategies", {}).items():
            if not strategies:
                continue
            msg = "✅ Стратегии успешно восстановлены\n🕒 Перезапуск: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg += "\n\n📋 Активные стратегии:\n" + "\n".join(
                f"• {s['type'].upper()} — {s['symbol']}" for s in strategies)
            try:
                await bot.send_message(chat_id=chat_id, text=msg)
                log_restore(f"📨 Сообщение о восстановлении отправлено пользователю {chat_id}")
            except Exception as e:
                log_restore(f"⚠️ Ошибка при уведомлении {chat_id}: {e}")

    # --- Уведомление пользователю ---
    if restored_count > 0 and app:
        bot = app.bot
        for chat_id, strats in app.bot_data["active_strategies"].items():
            if not strats:
                continue
            msg = "✅ Стратегии успешно восстановлены\n🕒 Перезапуск: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg += "\n\n📋 Активные стратегии:\n" + "\n".join(
                f"• {s['type'].upper()} — {s['symbol']}" for s in strats
            )
            try:
                await bot.send_message(chat_id=chat_id, text=msg)
                log_restore(f"📨 Отправлено уведомление пользователю {chat_id}")
            except Exception as e:
                log_restore(f"⚠️ Ошибка отправки уведомления {chat_id}: {e}")

if __name__ == "__main__":
    asyncio.run(restore_strategies())
