# decorators.py
import ccxt
import logging
import asyncio
from datetime import datetime, timedelta

from utils import get_exchange
from state import remove_job

logger = logging.getLogger(__name__)

async def reconnect_exchange():
    """
    Переподключение к бирже.
    """
    logger.info("🔁 Переподключение к бирже...")
    await asyncio.sleep(5)
    return await get_exchange()


async def safe_notify(context, chat_id, text):
    """Безопасная отправка сообщений пользователю."""
    try:
        await context.bot.send_message(chat_id, text)
    except Exception as e:
        logger.debug(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")

def resilient_strategy(func):
    """
    Универсальный декоратор для стратегий:
    - защищает от сетевых и API-ошибок;
    - делает переподключение через reconnect_exchange();
    - не падает даже при временной потере интернета.
    """
    async def wrapper(context, *args, **kwargs):
        job = getattr(context, "job", None)
        chat_id = getattr(job, "chat_id", None)
        retry_count = 0
        max_retries = 5
        retry_delay = 30  # секунд между попытками

        while retry_count < max_retries:
            try:
                await func(context, *args, **kwargs)
                if retry_count > 0:
                    logger.info(f"✅ Стратегия {func.__name__} восстановилась после {retry_count} попыток.")
                return

            except ccxt.NetworkError as e:
                retry_count += 1
                logger.warning(f"🌐 NetworkError ({retry_count}/{max_retries}) в {func.__name__}: {e}")
                await safe_notify(context, chat_id, f"🌐 Потеря связи, переподключение #{retry_count}...")
                await reconnect_exchange(delay=10)
                await asyncio.sleep(retry_delay)

            except ccxt.ExchangeError as e:
                retry_count += 1
                logger.warning(f"⚠️ ExchangeError ({retry_count}/{max_retries}) в {func.__name__}: {e}")
                await safe_notify(context, chat_id, f"⚠️ Ошибка API, попытка #{retry_count}...")
                await asyncio.sleep(retry_delay)

            except Exception as e:
                logger.exception(f"💥 Ошибка в {func.__name__}: {e}")
                if job:
                    job.schedule_removal()
                    if chat_id:
                        remove_job(context.application.user_data.get(chat_id, {}), job.name)
                        await safe_notify(context, chat_id, f"❌ Ошибка {func.__name__}: {e}")
                break

        # Если после 5 попыток не восстановилось
        if retry_count >= max_retries:
            logger.error(f"❌ Стратегия {func.__name__} упала окончательно после {max_retries} попыток.")
            if chat_id:
                await safe_notify(context, chat_id, f"❌ {func.__name__} не удалось восстановить связь. Попробует снова через 5 мин...")
            if job:
                try:
                    new_run_time = datetime.now() + timedelta(minutes=5)
                    job.reschedule(trigger='date', run_date=new_run_time)
                    logger.info(f"♻️ Перезапуск {func.__name__} запланирован на {new_run_time}")
                except Exception as e:
                    logger.error(f"Не удалось перепланировать задачу {func.__name__}: {e}")
    return wrapper
