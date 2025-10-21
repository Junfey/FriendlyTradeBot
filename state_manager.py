# state_manager.py
import json
import os
from datetime import datetime
from typing import Dict, Any, List

STATE_FILE = os.path.join(os.path.dirname(__file__), "strategies.json")


def _clean_data(obj):
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _clean_data(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple, set)):
        return [_clean_data(v) for v in obj]
    try:
        s = str(obj)
        return s if len(s) <= 300 else s[:300]
    except Exception:
        return None


def _load_raw() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        print("[WARNING] strategies.json повреждён или недоступен — создаём новый.")
        return {}


def _save_raw(data: Dict[str, Any]):
    tmp = STATE_FILE + ".tmp"
    try:
        clean = _clean_data(data)
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        print(f"[ERROR] Не удалось сохранить стратегии: {e}")


def _migrate_to_list_format(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Приводит к формату:
    { "chat_id": [ {"type":..., "symbol":..., "params": {...}}, ... ] }
    Поддерживает старый вид: {chat_id: {strategy_id: {"type":..,"symbol":..,"parameters":{...}}}}
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for chat_id, blob in (data or {}).items():
        lst: List[Dict[str, Any]] = []
        if isinstance(blob, list):
            # уже новый формат
            for item in blob:
                if not isinstance(item, dict):
                    continue
                typ = item.get("type")
                sym = item.get("symbol")
                params = item.get("params") or item.get("parameters") or {}
                if typ and sym:
                    lst.append({"type": typ, "symbol": sym, "params": params})
        elif isinstance(blob, dict):
            # старый формат со strategy_id
            for _sid, item in blob.items():
                if not isinstance(item, dict):
                    continue
                typ = item.get("type")
                sym = item.get("symbol")
                params = item.get("parameters") or item.get("params") or {}
                if typ and sym:
                    lst.append({"type": typ, "symbol": sym, "params": params})
        else:
            # что-то неожиданное — пропустим
            pass
        out[str(chat_id)] = lst
    return out


def load_strategies() -> Dict[str, List[Dict[str, Any]]]:
    raw = _load_raw()
    return _migrate_to_list_format(raw)


def save_strategies(data: Dict[str, List[Dict[str, Any]]]):
    # Ждём уже мигрированный формат
    _save_raw(_migrate_to_list_format(data))


def add_strategy(user: Dict[str, Any], strategy_type: str, symbol: str, parameters: Dict[str, Any]):
    """Дедуп по (type, symbol). Обновляем params если такая стратегия уже есть."""
    chat_id = str(user.get("chat_id"))
    all_data = load_strategies()
    all_data.setdefault(chat_id, [])
    strategies = all_data[chat_id]

    # есть ли уже такая стратегия
    for s in strategies:
        if s.get("type") == strategy_type and s.get("symbol") == symbol:
            s["params"] = parameters or {}
            save_strategies(all_data)
            print(f"[INFO] Стратегия {strategy_type}:{symbol} обновлена (params).")
            return f"{strategy_type}:{symbol}"

    strategies.append({"type": strategy_type, "symbol": symbol, "params": parameters or {}})
    save_strategies(all_data)
    print(f"[INFO] Стратегия '{strategy_type}' для {symbol} добавлена.")
    return f"{strategy_type}:{symbol}"


def remove_strategy(user: Dict[str, Any], strategy_type: str, symbol: str) -> bool:
    chat_id = str(user.get("chat_id"))
    all_data = load_strategies()
    if chat_id not in all_data:
        return False
    before = len(all_data[chat_id])
    all_data[chat_id] = [s for s in all_data[chat_id] if not (s.get("type") == strategy_type and s.get("symbol") == symbol)]
    changed = len(all_data[chat_id]) != before
    if changed:
        save_strategies(all_data)
    return changed


def clear_user_strategies(user: Dict[str, Any]):
    chat_id = str(user.get("chat_id"))
    all_data = load_strategies()
    all_data[chat_id] = []
    save_strategies(all_data)


def get_user_strategies(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    return load_strategies().get(str(user.get("chat_id")), [])
