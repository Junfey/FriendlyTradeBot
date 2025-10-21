# strategies/percent.py
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
async def percent_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, TypeError):
        amount = Decimal("0")
    try:
        step = float(data.get("step", 0))
    except Exception:
        step = 0.0
    chat_id = job.chat_id

    base_price = job.data.get("base_price")
    if base_price is None:
        base_price = await asyncio.to_thread(get_price, symbol)
        job.data["base_price"] = base_price

    price = await asyncio.to_thread(get_price, symbol)
    if price is None or base_price is None:
        msg = f"❌ Нет цены для {symbol}"
    else:
        diff = (price - base_price) / base_price * 100
        if abs(diff) >= step:
            side = "buy" if diff < 0 else "sell"

            # проверка минимального ордера
            try:
                order_value = amount * Decimal(str(price))
            except Exception:
                order_value = Decimal("0")

            if order_value < MIN_ORDER_USD:
                msg = f"⚠️ Пропуск ордера {symbol}: {order_value:.2f} USDT < минимум {MIN_ORDER_USD} USDT"
                logger.info(msg)
            else:
                ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, float(amount))
                if not ok:
                    msg = f"❌ Percent остановлен: {reason}"
                    try:
                        job.schedule_removal()
                    except Exception:
                        logger.warning("Не удалось schedule_removal() в percent_job.")
                    try:
                        remove_job(context.application.user_data.get(chat_id, {}), job.name)
                    except Exception:
                        logger.warning(f"Ошибка при удалении job {job.name} в percent_job.")
                else:
                    await place_market_order_safe(symbol, side, float(amount))
                    job.data["base_price"] = price
                    msg = f"🚀 Percent {symbol}: {side.upper()} {amount} (Δ={diff:.2f}%)"
        else:
            msg = f"📊 {symbol}: {price:.2f} (Δ={diff:.3f}% / цель {step}%)"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    try:
        await context.bot.send_message(chat_id, msg, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение в percent_job: {e}")


async def start_percent_strategy(update, context, symbol, amount, step, interval):
    """Запуск стратегии Percent с пользовательским интервалом (в минутах).
       Возвращает True при успешном старте, False если запуск отменён."""
    job_key = make_job_key("percent", symbol, amount=amount, step=step, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return False

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return False

    job = context.job_queue.run_repeating(
        percent_job, interval * 60,  # минуты -> секунды
        chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount, "step": step}
    )
    add_job(context.user_data, job_key, job)

    # ✅ Сохраняем в persistent state
    safe_add_strategy(update, "percent", symbol, {
        "amount": amount,
        "step": step,
        "interval": interval
    })

    await update.message.reply_text(
        f"🚀 Percent-бот запущен для {symbol}\n"
        f"Шаг: {step}% / Объём: {amount}\nИнтервал: {interval} мин.",
        reply_markup=get_main_menu()
    )
    return True

