# strategies/range.py
import asyncio
from strategies.range_config import RangeConfig
from decimal import Decimal, InvalidOperation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_price, place_market_order_safe, has_enough_balance, safe_add_strategy
from state import make_job_key, add_job, get_jobs, remove_job
from menus import get_main_menu
from decorators import resilient_strategy
from constants import MIN_ORDER_USD
import logging

logger = logging.getLogger(__name__)


@resilient_strategy
async def range_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, TypeError):
        amount = Decimal("0")

    try:
        low = float(data.get("low", 0))
        high = float(data.get("high", 0))
    except Exception:
        low, high = 0.0, 0.0

    chat_id = job.chat_id
    price = await asyncio.to_thread(get_price, symbol)

    if price is None:
        msg = f"❌ Нет цены для {symbol}"
    else:
        try:
            order_value = amount * Decimal(str(price))
        except Exception:
            order_value = Decimal("0")

        if order_value < MIN_ORDER_USD:
            msg = f"⚠️ Range: пропуск ордера {symbol}: {order_value:.2f} USDT < минимум {MIN_ORDER_USD} USDT"
            logger.info(msg)
        elif price <= low:
            side = "buy"
            ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, float(amount))
            if not ok:
                msg = f"❌ Range остановлен: {reason}"
                try:
                    job.schedule_removal()
                    remove_job(context.application.user_data.get(chat_id, {}), job.name)
                except Exception:
                    logger.warning("Ошибка при остановке range_job.")
            else:
                await place_market_order_safe(symbol, side, float(amount))
                msg = f"🟢 BUY {symbol} @ {price:.2f} (<= {low})"
        elif price >= high:
            side = "sell"
            ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, float(amount))
            if not ok:
                msg = f"❌ Range остановлен: {reason}"
                try:
                    job.schedule_removal()
                    remove_job(context.application.user_data.get(chat_id, {}), job.name)
                except Exception:
                    logger.warning("Ошибка при остановке range_job.")
            else:
                await place_market_order_safe(symbol, side, float(amount))
                msg = f"🔴 SELL {symbol} @ {price:.2f} (>= {high})"
        else:
            msg = f"📊 {symbol}: {price:.2f} (диапазон {low}-{high})"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    try:
        await context.bot.send_message(chat_id, msg, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение в range_job: {e}")

    # === Адаптивная корректировка интервала ===
    from load_manager import adaptive_delay
    job.interval = await adaptive_delay(job.interval)


async def start_range_strategy(update, context, symbol, amount, low, high, interval):
    """Запуск Range с пользовательским интервалом (в минутах)."""

    from load_manager import register_strategy
    chat_id = update.effective_chat.id

    # === 1️⃣ Проверка параметров ===
    try:
        cfg = RangeConfig(symbol=symbol, amount=amount, low=low, high=high, interval=interval)
    except Exception as e:
        await update.message.reply_text(f"❌ Неверные параметры: {e}", reply_markup=get_main_menu())
        return False

    # === 2️⃣ Создание ключа стратегии ===
    job_key = make_job_key("range", symbol, amount=amount, low=low, high=high, interval=interval)

    # === 3️⃣ Проверка дубликатов ===
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return False

    # === 4️⃣ Проверка лимита стратегий ===
    if not register_strategy(chat_id, job_key):
        await update.message.reply_text("⚠️ Лимит активных стратегий достигнут.", reply_markup=get_main_menu())
        return False

    # === 5️⃣ Проверка баланса ===
    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return False

    # === 6️⃣ Добавление задачи ===
    job = context.job_queue.run_repeating(
        range_job,
        interval * 60,
        chat_id=chat_id,
        name=job_key,
        data={"symbol": symbol, "amount": amount, "low": low, "high": high}
    )
    add_job(context.user_data, job_key, job)

    # === 7️⃣ Сохранение в state ===
    safe_add_strategy(update, "range", symbol, {
        "amount": amount,
        "low": low,
        "high": high,
        "interval": interval,
    })

    # === 8️⃣ Подтверждение ===
    await update.message.reply_text(
        f"🚀 Range-бот запущен для {symbol}\n"
        f"Диапазон {low}-{high} / Объём {amount}\nИнтервал: {interval} мин.",
        reply_markup=get_main_menu()
    )
    logger.info(f"✅ Range-стратегия {job_key} запущена для {chat_id}")
    return True
