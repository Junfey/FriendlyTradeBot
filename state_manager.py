from typing import Dict, Any
from storage.state_storage import JsonStateStorage

_storage = JsonStateStorage()

def load_strategies() -> Dict[str, Any]:
    """Загружает все стратегии из файла (безопасно, атомично)."""
    return _storage.load()

def save_strategies(all_data: Dict[str, Any]) -> None:
    """Сохраняет все стратегии в файл (атомично)."""
    _storage.save(all_data)
