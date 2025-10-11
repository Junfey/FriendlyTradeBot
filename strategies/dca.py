#strategies.dca.py
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import get_price, place_market_order_safe, has_enough_balance, safe_add_strategy
from state import make_job_key, add_job, get_jobs, remove_job
from menus import get_main_menu
from decorators import resilient_strategy


@resilient_strategy
async def dca_job(context):
    job = context.job
    data = job.data or {}
    symbol = data.get("symbol")
    amount = float(data.get("amount", 0))
    chat_id = job.chat_id

    side = "buy"
    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, side, amount)
    if not ok:
        msg = f"❌ DCA остановлен: {reason}"
        job.schedule_removal()
        remove_job(context.application.user_data.get(chat_id, {}), job.name)
    else:
        await place_market_order_safe(symbol, side, amount)
        price = await asyncio.to_thread(get_price, symbol)
        msg = f"💰 DCA BUY {amount} {symbol} @ {price:.2f}"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Стоп", callback_data=f"STOP:{job.name}")]])
    await context.bot.send_message(chat_id, msg, reply_markup=keyboard)



async def start_dca_strategy(update, context, symbol, amount, interval):
    job_key = make_job_key("dca", symbol, amount=amount, interval=interval)
    if job_key in get_jobs(context.user_data):
        await update.message.reply_text(f"⚠️ Уже запущено: {job_key}", reply_markup=get_main_menu())
        return

    ok, reason = await asyncio.to_thread(has_enough_balance, symbol, "buy", amount)
    if not ok:
        await update.message.reply_text(f"❌ Запуск невозможен: {reason}", reply_markup=get_main_menu())
        return

    job = context.job_queue.run_repeating(
        dca_job, interval * 60, chat_id=update.effective_chat.id,
        name=job_key, data={"symbol": symbol, "amount": amount}
    )
    add_job(context.user_data, job_key, job)

    # 🟡 убираем старый add_strategy, оставляем только safe_add_strategy
    safe_add_strategy(update, context, "dca",{
        "symbol": symbol,
        "amount": amount
    })

    await update.message.reply_text(
        f"🚀 DCA-бот запущен для {symbol}\nИнтервал: {interval} мин\nОбъём: {amount}",
        reply_markup=get_main_menu()
    )
