#strategies.percent.py
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_price, place_market_order_safe, has_enough_balance, safe_add_strategy
from state import make_job_key, add_job, get_jobs, remove_job
from menus import get_main_menu
from decorators import resilient_strategy


@resilient_strategy
async def percent_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    amount = float(data.get("amount", 0))
    step = float(data.get("step", 0))
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
            ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, amount)
            if not ok:
                msg = f"❌ Percent остановлен: {reason}"
                job.schedule_removal()
                remove_job(context.application.user_data.get(chat_id, {}), job.name)
            else:
                await place_market_order_safe(symbol, side, amount)
                job.data["base_price"] = price
                msg = f"🚀 Percent {symbol}: {side.upper()} {amount}, Δ={diff:.2f}%"
        else:
            msg = f"📊 {symbol}: {price:.2f} (Δ={diff:.3f}% / цель {step}%)"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    await context.bot.send_message(chat_id, msg, reply_markup=keyboard)



async def start_percent_strategy(update, context, symbol, amount, step, interval):
    """Запуск стратегии Percent с пользовательским интервалом (в минутах)."""
    job_key = make_job_key("percent", symbol, amount=amount, step=step, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return

    job = context.job_queue.run_repeating(
        percent_job, interval * 60,  # минуты -> секунды
        chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount, "step": step}
    )
    add_job(context.user_data, job_key, job)

    # ✅ Используем безопасную версию, которая правильно сохраняет chat_id
    safe_add_strategy(update, context, "percent", {
        "symbol": symbol,
        "amount": amount,
        "step": step,
        "interval": interval
    })

    await update.message.reply_text(
        f"🚀 Percent-бот запущен для {symbol}\n"
        f"Шаг: {step}% / Объём: {amount}\nИнтервал: {interval} мин.",
        reply_markup=get_main_menu()
    )
