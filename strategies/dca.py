# strategies/dca.py
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
async def dca_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, TypeError):
        amount = Decimal("0")
    chat_id = job.chat_id

    # проверка минимального ордера
    price = await asyncio.to_thread(get_price, symbol)
    try:
        order_value = amount * Decimal(str(price)) if price is not None else Decimal("0")
    except Exception:
        order_value = Decimal("0")

    if order_value < MIN_ORDER_USD:
        msg = f"⚠️ DCA: пропуск ордера {symbol}: {order_value:.2f} USDT < минимум {MIN_ORDER_USD} USDT"
        logger.info(msg)
        # оповестим пользователя, но не завершим стратегию
    else:
        side = "buy"
        ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, float(amount))
        if not ok:
            msg = f"❌ DCA остановлен: {reason}"
            try:
                job.schedule_removal()
            except Exception:
                logger.warning("Не удалось schedule_removal() в dca_job.")
            try:
                remove_job(context.application.user_data.get(chat_id, {}), job.name)
            except Exception:
                logger.warning(f"Ошибка при удалении job {job.name} в dca_job.")
        else:
            await place_market_order_safe(symbol, side, float(amount))
            price_now = await asyncio.to_thread(get_price, symbol)
            msg = f"💰 DCA BUY {amount} {symbol} @ {price_now:.2f}"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    try:
        await context.bot.send_message(chat_id, msg, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение в dca_job: {e}")


async def start_dca_strategy(update, context, symbol, amount, interval):
    job_key = make_job_key("dca", symbol, amount=amount, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return False

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return False

    job = context.job_queue.run_repeating(
        dca_job, interval * 60, chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount}
    )
    add_job(context.user_data, job_key, job)

    safe_add_strategy(update, "dca", symbol, {"amount": amount, "interval": interval})

    await update.message.reply_text(
        f"🚀 DCA-бот запущен для {symbol}\nИнтервал: {interval} мин\nОбъём: {amount}",
        reply_markup=get_main_menu()
    )
    return True

