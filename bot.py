# bot.py
from logging_config import setup_logging
setup_logging()

import logging
import asyncio
from typing import Dict, Any, List, Tuple

from telegram import Update
from telegram.ext import (
    Application, CommandHandler,
    ConversationHandler, ContextTypes, MessageHandler,
    CallbackQueryHandler, filters
)

from decimal import Decimal, InvalidOperation
from settings import TELEGRAM_TOKEN
from menus import get_main_menu, get_strategies_menu, get_back_menu
from state import stop_all_jobs, get_jobs, remove_job
from strategies.percent import start_percent_strategy
from strategies.dca import start_dca_strategy
from strategies.range import start_range_strategy
from utils import get_price as sync_get_price, get_balance as sync_get_balance, place_market_order_safe as sync_place_market_order
from state_manager import load_strategies, save_strategies
from restore_strategies import restore_strategies
from constants import MIN_ORDER_USD, MIN_USD_VALUE, MAX_PRICE_CHECKS, MAJOR_ASSETS



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния диалогов
PERCENT_SYMBOL, PERCENT_AMOUNT, PERCENT_STEP, PERCENT_INTERVAL = range(0, 4)
DCA_SYMBOL, DCA_AMOUNT, DCA_INTERVAL = range(4, 7)
RANGE_SYMBOL, RANGE_AMOUNT, RANGE_MIN, RANGE_MAX, RANGE_INTERVAL = range(7, 12)
BUY_SYMBOL, BUY_AMOUNT = range(12, 14)
SELL_SYMBOL, SELL_AMOUNT = range(14, 16)
PRICE_SYMBOL = 16

# ----------------- Start -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я торговый бот (demo).", reply_markup=get_main_menu())

# ----------------- Helper -----------------
def _user_from(update=None, context=None):
    """Возвращает {'chat_id': <id>} безопасно из update/context."""
    try:
        if update is not None and hasattr(update, "effective_chat") and update.effective_chat is not None:
            return {"chat_id": getattr(update.effective_chat, "id", "unknown")}
    except Exception:
        pass
    try:
        if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
            if "chat_id" in context.user_data:
                return {"chat_id": context.user_data.get("chat_id")}
    except Exception:
        pass
    try:
        if context is not None and hasattr(context, "bot") and hasattr(context.bot, "id"):
            return {"chat_id": getattr(context.bot, "id", "unknown")}
    except Exception:
        pass
    return {"chat_id": "unknown"}
# -----------------






# ----------------- Price (CLI) -----------------
async def check_price_cli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /price BTC/USDT (CLI)"""
    if not context.args:
        await update.message.reply_text("Укажи валютную пару (например `/price BTC/USDT`).", parse_mode="Markdown")
        return
    symbol = context.args[0].strip().upper()
    if "/" not in symbol:
        symbol = f"{symbol}/USDT"
    try:
        price = await asyncio.to_thread(sync_get_price, symbol)
        if price is None:
            await update.message.reply_text(f"❌ Пара {symbol} не поддерживается.")
        else:
            await update.message.reply_text(f"💹 Цена {symbol}: {price:.2f}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении цены: {e}")


# ----------------- Price (интерактивная проверка) -----------------
async def price_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару для проверки (например BTC/USDT или просто BTC):", reply_markup=get_back_menu())
    return PRICE_SYMBOL

async def price_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().upper()
    if not raw:
        await update.message.reply_text("❌ Пустой ввод. Возврат в главное меню.", reply_markup=get_main_menu())
        return ConversationHandler.END

    # если пользователь ввёл просто 'BTC' — дописываем /USDT
    if "/" not in raw:
        symbol = f"{raw}/USDT"
    else:
        symbol = raw

    # защитимся от случайных вводов, начинающихся с '/'
    if symbol.startswith("/"):
        await update.message.reply_text("❌ Неверная пара.", reply_markup=get_main_menu())
        return ConversationHandler.END

    try:
        price = await asyncio.to_thread(sync_get_price, symbol)
        if price is None:
            await update.message.reply_text(f"❌ Пара {symbol} не поддерживается.", reply_markup=get_main_menu())
        else:
            await update.message.reply_text(f"💹 Цена {symbol}: {price:.2f}", reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении цены: {e}", reply_markup=get_main_menu())

    return ConversationHandler.END


# ----------------- Список основных курсов (USDT) -----------------
async def list_major_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines: List[str] = []
    for asset in MAJOR_ASSETS:
        if asset == "USDT":  # пропускаем бессмысленную пару
            continue
        pair = f"{asset}/USDT"
        try:
            price = await asyncio.to_thread(sync_get_price, pair)
            if price is None:
                lines.append(f"{pair}: ❌ Ошибка")
            else:
                lines.append(f"{pair}: {price:.2f}")
        except Exception:
            lines.append(f"{pair}: ❌ Ошибка")
    await update.message.reply_text("💹 Курсы основных валют (USDT):\n" + "\n".join(lines), reply_markup=get_main_menu())


# ----------------- Список стратегий -----------------
async def list_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Берем из общего хранилища, где restore_strategies записывает активные стратегии
    all_active = context.application.bot_data.get("active_strategies", {})

    user_strats = all_active.get(chat_id, [])

    if not user_strats:
        await update.message.reply_text("⚠️ Нет запущенных стратегий.")
        return

    lines = []
    for s in user_strats:
        lines.append(
            f"📊 {s['symbol']}: шаг {s.get('params', {}).get('step', '?')}% / "
            f"объём {s.get('params', {}).get('amount', '?')}"
        )

    await update.message.reply_text("📋 Активные стратегии:\n" + "\n".join(lines))



# ----------------- Стоп всех стратегий -----------------
async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stopped = stop_all_jobs(context.user_data)
    if stopped:
        text = "🛑 Остановлены стратегии:\n" + "\n".join(stopped)
    else:
        text = "⚠️ Нет запущенных стратегий."
    await update.message.reply_text(text)


# ----------------- Покупка / Продажа -----------------

# ----------------- Покупка -----------------
async def buy_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару (например BTC/USDT или просто BTC):", reply_markup=get_back_menu())
    return BUY_SYMBOL

async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # нормализуем хранение пары как верхний регистр без лишних пробелов
    context.user_data["buy_symbol"] = update.message.text.strip().upper()
    await update.message.reply_text("Введите сумму БАЗОВОЙ валюты (например 0.001 для BTC):", reply_markup=get_back_menu())
    return BUY_AMOUNT

async def buy_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils import normalize_symbol, place_market_order_safe

    # ---- идемпотентность (защита от двойного клика) ----
    if context.user_data.get("op_lock"):
        await update.message.reply_text("⏳ Предыдущая операция ещё обрабатывается. Подождите пару секунд.", reply_markup=get_main_menu())
        return ConversationHandler.END
    context.user_data["op_lock"] = True

    try:
        # Парс суммы
        try:
            amount = Decimal(update.message.text.strip())
            if amount <= 0:
                raise InvalidOperation()
        except Exception:
            await update.message.reply_text("❌ Неверная сумма. Введите положительное число.", reply_markup=get_main_menu())
            return ConversationHandler.END

        # Символ
        raw_symbol = (context.user_data.get("buy_symbol") or "").strip().upper()
        if not raw_symbol:
            await update.message.reply_text("❌ Валютная пара не указана.", reply_markup=get_main_menu())
            return ConversationHandler.END

        # BTC -> BTC/USDT
        symbol = normalize_symbol(raw_symbol)
        if "/" not in symbol:
            await update.message.reply_text("❌ Неверная пара. Пример: BTC/USDT", reply_markup=get_main_menu())
            return ConversationHandler.END
        base, quote = symbol.split("/")

        # Цена и баланс
        price = await asyncio.to_thread(sync_get_price, symbol)
        if not price:
            await update.message.reply_text(f"❌ Пара {symbol} не поддерживается.", reply_markup=get_main_menu())
            return ConversationHandler.END

        balance = await asyncio.to_thread(sync_get_balance)
        quote_balance = Decimal(str(balance.get(quote, 0)))

        # Проверка минимального ордера и достаточности средств
        order_value_usd = Decimal(str(price)) * amount  # покупаем amount базовой валюты
        if order_value_usd < MIN_ORDER_USD:
            await update.message.reply_text(
                f"⚠️ Слишком маленький ордер: ≈ {order_value_usd:.2f} USDT < {MIN_ORDER_USD} USDT.",
                reply_markup=get_main_menu()
            )
            return ConversationHandler.END

        required_quote = order_value_usd  # в USDT (или другой quote)
        if quote_balance < required_quote:
            await update.message.reply_text(
                f"❌ Недостаточно {quote}: баланс {quote_balance:.4f}, требуется ≈ {required_quote:.2f}.",
                reply_markup=get_main_menu()
            )
            return ConversationHandler.END

        # Размещаем ордер (amount — в базовой валюте)
        await place_market_order_safe(symbol, "buy", float(amount))
        await update.message.reply_text(f"✅ Куплено {amount.normalize()} {base} по рынку {symbol}.", reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при покупке: {e}", reply_markup=get_main_menu())
    finally:
        context.user_data["op_lock"] = False

    return ConversationHandler.END



# ----------------- Продажа -----------------
async def sell_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару (например BTC/USDT или просто BTC):", reply_markup=get_back_menu())
    return SELL_SYMBOL

async def sell_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sell_symbol"] = update.message.text.strip().upper()
    await update.message.reply_text("Введите сумму БАЗОВОЙ валюты (например 0.001 BTC):", reply_markup=get_back_menu())
    return SELL_AMOUNT

async def sell_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils import normalize_symbol, place_market_order_safe

    # ---- идемпотентность ----
    if context.user_data.get("op_lock"):
        await update.message.reply_text("⏳ Предыдущая операция ещё обрабатывается. Подождите пару секунд.", reply_markup=get_main_menu())
        return ConversationHandler.END
    context.user_data["op_lock"] = True

    try:
        # Парс суммы
        try:
            amount = Decimal(update.message.text.strip())
            if amount <= 0:
                raise InvalidOperation()
        except Exception:
            await update.message.reply_text("❌ Неверная сумма. Введите положительное число.", reply_markup=get_main_menu())
            return ConversationHandler.END

        # Символ
        raw_symbol = (context.user_data.get("sell_symbol") or "").strip().upper()
        if not raw_symbol:
            await update.message.reply_text("❌ Валютная пара не указана.", reply_markup=get_main_menu())
            return ConversationHandler.END

        symbol = normalize_symbol(raw_symbol)
        if "/" not in symbol:
            await update.message.reply_text("❌ Неверная пара. Пример: BTC/USDT", reply_markup=get_main_menu())
            return ConversationHandler.END
        base, quote = symbol.split("/")

        # Цена и баланс
        price = await asyncio.to_thread(sync_get_price, symbol)
        if not price:
            await update.message.reply_text(f"❌ Пара {symbol} не поддерживается.", reply_markup=get_main_menu())
            return ConversationHandler.END

        balance = await asyncio.to_thread(sync_get_balance)
        base_balance = Decimal(str(balance.get(base, 0)))

        if base_balance < amount:
            await update.message.reply_text(
                f"❌ Недостаточно {base}: баланс {base_balance.normalize()}, требуется {amount.normalize()}.",
                reply_markup=get_main_menu()
            )
            return ConversationHandler.END

        # Проверка минимального ордера (в USD-экв.)
        order_value_usd = Decimal(str(price)) * amount
        if order_value_usd < MIN_ORDER_USD:
            await update.message.reply_text(
                f"⚠️ Слишком маленький ордер: ≈ {order_value_usd:.2f} USDT < {MIN_ORDER_USD} USDT.",
                reply_markup=get_main_menu()
            )
            return ConversationHandler.END

        # Размещаем ордер (amount — в базовой валюте)
        await place_market_order_safe(symbol, "sell", float(amount))
        await update.message.reply_text(f"✅ Продано {amount.normalize()} {base} по рынку {symbol}.", reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при продаже: {e}", reply_markup=get_main_menu())
    finally:
        context.user_data["op_lock"] = False

    return ConversationHandler.END


# ----------------- Percent / DCA / Range (Conversation flows) -----------------

# ----------------- Percent -----------------
async def percent_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару (например BTC/USDT):", reply_markup=get_back_menu())
    return PERCENT_SYMBOL

async def percent_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["percent_symbol"] = update.message.text.strip().upper()
    await update.message.reply_text("Введите сумму (например 0.001):", reply_markup=get_back_menu())
    return PERCENT_AMOUNT

async def percent_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["percent_amount"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат суммы. Операция отменена.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите процент шага (например 0.5):", reply_markup=get_back_menu())
    return PERCENT_STEP

async def percent_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["percent_step"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат шага.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите интервал в минутах:", reply_markup=get_back_menu())
    return PERCENT_INTERVAL

async def percent_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # поддержка дробных и запятых
        interval = float(update.message.text.strip().replace(",", "."))
        if interval <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ Неверный формат интервала. Введите положительное число (например 1 или 0.5).",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    symbol = context.user_data.get("percent_symbol")
    amount = context.user_data.get("percent_amount")
    step = context.user_data.get("percent_step")

    if not symbol or amount is None or step is None:
        await update.message.reply_text("❌ Ошибка параметров.", reply_markup=get_main_menu())
        return ConversationHandler.END

    started = await start_percent_strategy(update, context, symbol, amount, step, interval)
    if started:
        await update.message.reply_text("✅ Percent-стратегия запущена.", reply_markup=get_main_menu())
    return ConversationHandler.END


# ----------------- DCA -----------------
# ----------------- DCA -----------------
async def dca_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару (например ETH/USDT):", reply_markup=get_back_menu())
    return DCA_SYMBOL


async def dca_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dca_symbol"] = update.message.text.strip().upper()
    await update.message.reply_text("Введите сумму (например 0.002):", reply_markup=get_back_menu())
    return DCA_AMOUNT


async def dca_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["dca_amount"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат суммы. Операция отменена.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите интервал в минутах:", reply_markup=get_back_menu())
    return DCA_INTERVAL


async def dca_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        interval = float(update.message.text.strip().replace(",", "."))
        if interval <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ Неверный формат интервала. Введите положительное число (например 1 или 0.5).",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    symbol = context.user_data.get("dca_symbol")
    amount = context.user_data.get("dca_amount")

    if not symbol or amount is None:
        await update.message.reply_text("❌ Ошибка параметров.", reply_markup=get_main_menu())
        return ConversationHandler.END

    started = await start_dca_strategy(update, context, symbol, amount, interval)
    if started:
        await update.message.reply_text("✅ DCA-стратегия запущена.", reply_markup=get_main_menu())
    return ConversationHandler.END




# ----------------- Range -----------------
async def range_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите валютную пару (например BNB/USDT):", reply_markup=get_back_menu())
    return RANGE_SYMBOL

async def range_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["range_symbol"] = update.message.text.strip().upper()
    await update.message.reply_text("Введите сумму (например 0.001):", reply_markup=get_back_menu())
    return RANGE_AMOUNT

async def range_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["range_amount"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат суммы. Операция отменена.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите нижнюю границу диапазона:", reply_markup=get_back_menu())
    return RANGE_MIN

async def range_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["range_min"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат минимума. Операция отменена.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите верхнюю границу диапазона:", reply_markup=get_back_menu())
    return RANGE_MAX

async def range_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["range_max"] = float(update.message.text.strip())
    except Exception:
        await update.message.reply_text("❌ Неверный формат максимума.", reply_markup=get_main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Введите интервал в минутах:", reply_markup=get_back_menu())
    return RANGE_INTERVAL

async def range_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        interval = float(update.message.text.strip().replace(",", "."))
        if interval <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text(
            "❌ Неверный формат интервала. Введите положительное число (например 1 или 0.5).",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    symbol = context.user_data.get("range_symbol")
    amount = context.user_data.get("range_amount")
    min_val = context.user_data.get("range_min")
    max_val = context.user_data.get("range_max")

    if not symbol or amount is None or min_val is None or max_val is None:
        await update.message.reply_text("❌ Ошибка параметров.", reply_markup=get_main_menu())
        return ConversationHandler.END

    started = await start_range_strategy(update, context, symbol, amount, min_val, max_val, interval)
    if started:
        await update.message.reply_text("✅ Range-стратегия запущена.", reply_markup=get_main_menu())
    return ConversationHandler.END


# ----------------- STOP callback -----------------
async def stop_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    job_key = query.data.replace("STOP:", "")

    res = remove_job(context.user_data, job_key)
    if res:
        # remove_job возвращает (key, job) по твоему обновлённому state.py
        key, _ = res
        await query.edit_message_text(f"🛑 Стратегия {key} остановлена.")
    else:
        await query.edit_message_text("⚠️ Стратегия уже не активна.")


# ----------------- Баланс (с фильтрацией и порогами) -----------------
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_bal: Dict[str, Any] = await asyncio.to_thread(sync_get_balance)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка получения баланса: {e}")
        return

    # Оставляем только ненулевые
    items = [(k, float(v)) for k, v in raw_bal.items() if float(v) > 0]
    if not items:
        await update.message.reply_text("⚠️ Баланс пуст.")
        return

    # Сортируем по количеству (примерно) — и будем проверять цену для топ-N
    items.sort(key=lambda x: x[1], reverse=True)

    display: List[str] = []
    checks = 0

    # Сначала обеспечим показ мажорных активов (BTC/ETH/USDT и т.д.)
    prefer_set = set(MAJOR_ASSETS)
    preferred_items = [it for it in items if it[0] in prefer_set]
    others = [it for it in items if it[0] not in prefer_set]

    # Обработаем preferred (попытаемся получить их USD-стоимость)
    for asset, amt in preferred_items:
        if asset == "USDT":
            display.append(f"{asset}: {amt:.6g} (≈ {amt:.2f} USDT)")
            continue
        pair = f"{asset}/USDT"
        try:
            price = await asyncio.to_thread(sync_get_price, pair)
            usd = price * amt
            display.append(f"{asset}: {amt} (≈ {usd:.2f} USDT)")
        except Exception:
            display.append(f"{asset}: {amt}")

    # Обрабатываем остальных, делая не более MAX_PRICE_CHECKS запросов цен
    for asset, amt in others:
        if checks >= MAX_PRICE_CHECKS:
            break
        # простая фильтрация по количеству (минимум 1 unit) — чтобы убрать мелкие фанты
        if amt < 1.0:
            # но если это небольшая позиция BTC/ETH - нам бы хотелось показать, поэтому:
            if asset in ("BTC", "ETH"):
                pass
            else:
                continue
        pair = f"{asset}/USDT"
        try:
            price = await asyncio.to_thread(sync_get_price, pair)
            usd = price * amt
            checks += 1
            if usd >= MIN_USD_VALUE:
                display.append(f"{asset}: {amt} (≈ {usd:.2f} USDT)")
        except Exception:
            checks += 1
            # пропускаем, если не удаётся получить цену
            continue

    if not display:
        await update.message.reply_text("⚠️ Не найдено подходящих позиций для отображения (фильтр).")
        return

    # Отправляем чанками, чтобы не получить 'Message is too long'
    CHUNK = 3500
    chunk = ""
    for line in display:
        if len(chunk) + len(line) + 1 > CHUNK:
            await update.message.reply_text("💰 Баланс:\n" + chunk.strip())
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await update.message.reply_text("💰 Баланс:\n" + chunk.strip())


# ----------------- Общий обработчик (кнопки меню) -----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⚡ Стратегии":
        await update.message.reply_text("Выберите стратегию:", reply_markup=get_strategies_menu())

    elif text == "⬅️ Назад в главное меню":
        await update.message.reply_text("Главное меню:", reply_markup=get_main_menu())

    elif text == "📋 Активные стратегии":
        return await list_strategies(update, context)

    elif text == "Percent":
        return await percent_symbol(update, context)

    elif text == "DCA":
        return await dca_symbol(update, context)

    elif text == "Range":
        return await range_symbol(update, context)

    elif text == "🛑 Стоп все":
        return await stop_all(update, context)

    elif text == "📊 Баланс":
        return await show_balance(update, context)

    elif text == "💵 Купить":
        return await buy_symbol(update, context)

    elif text == "💰 Продать":
        return await sell_symbol(update, context)

    elif text == "🔍 Проверить цену":
        return await price_symbol(update, context)

    elif text == "📋 Все основные валюты":
        return await list_major_prices(update, context)

    # прочие текстовые события обрабатываются ConversationHandler'ами


# ----------------- Main -----------------
def main():
    logger.info("🚀 Запуск Telegram-бота...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list_strategies", list_strategies))
    app.add_handler(CommandHandler("stop_grid", stop_all))
    app.add_handler(CommandHandler("price", check_price_cli))
    app.add_handler(CallbackQueryHandler(stop_strategy_callback, pattern="^STOP:"))

    # ConversationHandlers
    conv_price = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 Проверить цену$"), price_symbol)],
        states={PRICE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_run)]},
        fallbacks=[],
        name="conv_price",
        persistent=False,
    )
    app.add_handler(conv_price)

    conv_percent = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Percent$"), percent_symbol)],
        states={
            PERCENT_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, percent_amount)],
            PERCENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, percent_step)],
            PERCENT_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, percent_interval)],
            PERCENT_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, percent_run)],
        },
        fallbacks=[],
        name="conv_percent",
        persistent=False,
    )
    app.add_handler(conv_percent)

    conv_dca = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^DCA$"), dca_symbol)],
        states={
            DCA_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, dca_amount)],
            DCA_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, dca_interval)],
            DCA_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, dca_run)],
        },
        fallbacks=[],
        name="conv_dca",
        persistent=False,
    )
    app.add_handler(conv_dca)

    conv_range = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Range$"), range_symbol)],
        states={
            RANGE_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, range_amount)],
            RANGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, range_min)],
            RANGE_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, range_max)],
            RANGE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, range_interval)],
            RANGE_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, range_run)],
        },
        fallbacks=[],
        name="conv_range",
        persistent=False,
    )
    app.add_handler(conv_range)

    conv_buy = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💵 Купить$"), buy_symbol)],
        states={
            BUY_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount)],
            BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_run)],
        },
        fallbacks=[],
        name="conv_buy",
        persistent=False,
    )
    app.add_handler(conv_buy)

    conv_sell = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Продать$"), sell_symbol)],
        states={
            SELL_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_amount)],
            SELL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_run)],
        },
        fallbacks=[],
        name="conv_sell",
        persistent=False,
    )
    app.add_handler(conv_sell)

    # Общий обработчик текста
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started")

    # --- Асинхронное восстановление стратегий при запуске ---
    # --- Асинхронное восстановление стратегий при запуске ---
    async def on_startup(app):
        logger.info("🔁 Восстановление стратегий при старте...")
        from restore_strategies import restore_strategies
        from datetime import datetime

        # Восстанавливаем
        await restore_strategies(app)
        logger.info("✅ Стратегии восстановлены.")

        bot = app.bot
        restored = app.bot_data.get("active_strategies", {})

        # Если ничего не восстановлено
        if not restored:
            logger.info("⚠️ Нет сохранённых стратегий для уведомления.")
            return

        # Формируем время
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Рассылаем уведомления пользователям
        for chat_id, strategies in restored.items():
            if not strategies:
                continue

            msg = (
                    f"✅ Стратегии успешно восстановлены\n"
                    f"🕒 Перезапуск: {time_now}\n\n"
                    f"📋 Активные стратегии:\n"
                    + "\n".join(f"• {s['type'].upper()} — {s['symbol']}" for s in strategies)
            )

            try:
                await bot.send_message(chat_id=chat_id, text=msg)
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {chat_id}: {e}")

    # Привязываем хук
    app.post_init = on_startup

    # 🚀 Запуск polling
    logger.info("✅ Telegram-бот запущен. Ожидаю команды...")
    app.run_polling()  # теперь без close_loop=False


if __name__ == "__main__":
    main()
