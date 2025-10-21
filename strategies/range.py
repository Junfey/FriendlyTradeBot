# strategies/range.py
import asyncio
from decimal import Decimal, InvalidOperation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_price, place_market_order_safe, has_enough_balance, safe_add_strategy
from state import make_job_key, add_job, get_jobs, remove_job
from menus import get_main_menu
from decorators import resilient_strategy
import logging

logger = logging.getLogger(__name__)

MIN_ORDER_USD = Decimal("5.0")


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
        low = 0.0
        high = 0.0
    chat_id = job.chat_id

    price = await asyncio.to_thread(get_price, symbol)
    if price is None:
        msg = f"❌ Нет цены для {symbol}"
    else:
        # проверка минимального ордера
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
                except Exception:
                    logger.warning("Не удалось schedule_removal() в range_job.")
                try:
                    remove_job(context.application.user_data.get(chat_id, {}), job.name)
                except Exception:
                    logger.warning(f"Ошибка при удалении job {job.name} в range_job.")
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
                except Exception:
                    logger.warning("Не удалось schedule_removal() в range_job.")
                try:
                    remove_job(context.application.user_data.get(chat_id, {}), job.name)
                except Exception:
                    logger.warning(f"Ошибка при удалении job {job.name} в range_job.")
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


async def start_range_strategy(update, context, symbol, amount, low, high, interval):
    """Запуск Range с пользовательским интервалом (в минутах)."""
    job_key = make_job_key("range", symbol, amount=amount, low=low, high=high, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return False

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return False

    job = context.job_queue.run_repeating(
        range_job, interval * 60,
        chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount, "low": low, "high": high}
    )
    add_job(context.user_data, job_key, job)


    safe_add_strategy(update, "range", symbol, {
        "amount": amount,
        "low": low,
        "high": high,
        "interval": interval,
    })

    await update.message.reply_text(
        f"🚀 Range-бот запущен для {symbol}\n"
        f"Диапазон {low}-{high} / Объём {amount}\nИнтервал: {interval} мин.",
        reply_markup=get_main_menu()
    )
    return True
