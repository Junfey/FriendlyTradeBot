# load_manager.py
import asyncio
import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

# === Конфигурация ===
MAX_API_CALLS_PER_MIN = 1100           # лимит Binance API
WARNING_THRESHOLD = 0.85               # при 85% начнём замедлять
CRITICAL_THRESHOLD = 0.95              # при 95% — пауза
ADAPTIVE_INTERVAL_STEP = 1.25          # множитель увеличения интервала

_api_calls_log = deque(maxlen=MAX_API_CALLS_PER_MIN)

def record_api_call():
    """Регистрирует вызов API"""
    _api_calls_log.append(time.time())

def get_api_load() -> float:
    """Возвращает текущую нагрузку на API (0.0–1.0)"""
    now = time.time()
    one_min_ago = now - 60
    calls = sum(1 for t in _api_calls_log if t >= one_min_ago)
    return calls / MAX_API_CALLS_PER_MIN

async def adaptive_delay(base_interval: float) -> float:
    """Корректирует интервал в зависимости от нагрузки"""
    load = get_api_load()
    if load >= CRITICAL_THRESHOLD:
        logger.error(f"🔥 Критическая нагрузка ({load*100:.1f}%), пауза 30 сек.")
        await asyncio.sleep(30)
        return base_interval * ADAPTIVE_INTERVAL_STEP
    elif load >= WARNING_THRESHOLD:
        new_interval = base_interval * ADAPTIVE_INTERVAL_STEP
        logger.warning(f"⚠️ Высокая нагрузка ({load*100:.1f}%), увеличиваем интервал до {new_interval:.2f}")
        return new_interval
    return base_interval


_active_strategies = {}

def register_strategy(user_id: int, job_key: str) -> bool:
    user_jobs = _active_strategies.setdefault(user_id, set())
    if len(user_jobs) >= 20:
        logger.warning(f"⚠️ Превышен лимит стратегий (20) у пользователя {user_id}")
        return False
    user_jobs.add(job_key)
    return True

def unregister_strategy(user_id: int, job_key: str):
    if user_id in _active_strategies:
        _active_strategies[user_id].discard(job_key)
