import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

def make_job_key(strategy: str, symbol: str, **params) -> str:
    base = f"{strategy}:{symbol}"
    if not params:
        return base
    parts = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, float):
            vs = f"{v:.12g}"
        else:
            vs = str(v)
        parts.append(f"{k}={vs}")
    return base + ":" + ":".join(parts)

def get_jobs(user_data: Dict[str, Any]) -> Dict[str, Any]:
    return user_data.get("grid_jobs", {})

def add_job(user_data: Dict[str, Any], key: str, job: Any):
    if "grid_jobs" not in user_data:
        user_data["grid_jobs"] = {}
    user_data["grid_jobs"][key] = job
    logger.info(f"Добавлена стратегия: {key}")

def job_exists(user_data: Dict[str, Any], key: str) -> bool:
    return key in get_jobs(user_data)

def remove_job(user_data: Dict[str, Any], key: str) -> Tuple[str, Any] | None:
    jobs = get_jobs(user_data)
    job = jobs.pop(key, None)
    if job:
        try:
            job.schedule_removal()
        except Exception as e:
            logger.warning(f"Ошибка при удалении job {key}: {e}")
        logger.info(f"Остановлена стратегия: {key}")
        return key, job
    return None

def stop_all_jobs(user_data: Dict[str, Any]) -> List[str]:
    jobs = get_jobs(user_data)
    stopped = []
    for key, job in list(jobs.items()):
        try:
            job.schedule_removal()
            stopped.append(key)
            logger.info(f"Остановлена стратегия: {key}")
        except Exception as e:
            logger.warning(f"Ошибка при остановке стратегии {key}: {e}")
    user_data["grid_jobs"] = {}
    return stopped
