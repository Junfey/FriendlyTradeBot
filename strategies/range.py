#strategies.range.py
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_price, place_market_order_safe, has_enough_balance, safe_add_strategy
from state import make_job_key, add_job, get_jobs, remove_job
from menus import get_main_menu
from decorators import resilient_strategy


@resilient_strategy
async def range_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    amount = float(data.get("amount", 0))
    low = float(data.get("low", 0))
    high = float(data.get("high", 0))
    chat_id = job.chat_id

    price = await asyncio.to_thread(get_price, symbol)
    if price is None:
        msg = f"❌ Нет цены для {symbol}"
    elif price <= low:
        side = "buy"
        ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, amount)
        if not ok:
            msg = f"❌ Range остановлен: {reason}"
            job.schedule_removal()
            remove_job(context.application.user_data.get(chat_id, {}), job.name)
        else:
            await place_market_order_safe(symbol, side, amount)
            msg = f"🟢 BUY {symbol} @ {price:.2f} (<= {low})"
    elif price >= high:
        side = "sell"
        ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, amount)
        if not ok:
            msg = f"❌ Range остановлен: {reason}"
            job.schedule_removal()
            remove_job(context.application.user_data.get(chat_id, {}), job.name)
        else:
            await place_market_order_safe(symbol, side, amount)
            msg = f"🔴 SELL {symbol} @ {price:.2f} (>= {high})"
    else:
        msg = f"📊 {symbol}: {price:.2f} (диапазон {low}-{high})"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    await context.bot.send_message(chat_id, msg, reply_markup=keyboard)




async def start_range_strategy(update, context, symbol, amount, low, high, interval):
    """Запуск Range с пользовательским интервалом (в минутах)."""
    job_key = make_job_key("range", symbol, amount=amount, low=low, high=high, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return

    job = context.job_queue.run_repeating(
        range_job, interval * 60,
        chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount, "low": low, "high": high}
    )
    add_job(context.user_data, job_key, job)


    # ✅ Используем безопасную версию, которая правильно сохраняет chat_id
    safe_add_strategy(update, context, "range",{
        "symbol": symbol,
        "amount": amount,
        "low": low,
        "high": high,
        "interval": interval
    })


    await update.message.reply_text(
        f"🚀 Range-бот запущен для {symbol}\n"
        f"Диапазон {low}-{high} / Объём {amount}\nИнтервал: {interval} мин.",
        reply_markup=get_main_menu()
    )

