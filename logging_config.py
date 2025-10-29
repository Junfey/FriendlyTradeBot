import logging
import logging.config
import os
import sys
from pathlib import Path

# ---------------------------
# 🌈 Цвета для консоли (ANSI)
# ---------------------------
COLORS = {
    "DEBUG": "\033[37m",    # серый
    "INFO": "\033[32m",     # зелёный
    "WARNING": "\033[33m",  # жёлтый
    "ERROR": "\033[31m",    # красный
    "CRITICAL": "\033[41m", # белый текст на красном фоне
    "RESET": "\033[0m"      # сброс цвета
}


class ColorFormatter(logging.Formatter):
    """Форматтер, который добавляет цвет в зависимости от уровня логов."""
    def format(self, record):
        color = COLORS.get(record.levelname, COLORS["RESET"])
        message = super().format(record)
        return f"{color}{message}{COLORS['RESET']}"


def setup_logging():
    """
    Настраивает красивое логирование:
    - вывод в консоль с цветами
    - запись в файл logs/app.log
    - уровень логов можно задать через .env (LOG_LEVEL=DEBUG)
    """

    # 1️⃣ создаём папку logs, если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 2️⃣ определяем уровень логирования (по умолчанию INFO)
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    # 3️⃣ формат сообщений (время + уровень + имя + текст)
    formatter = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    # 4️⃣ создаём обработчики (куда выводить)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter(formatter, datefmt))
    console_handler.setLevel(level)

    file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(formatter, datefmt))
    file_handler.setLevel(level)

    # 5️⃣ подключаем обработчики к "root" логгеру
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 6️⃣ чтобы избежать дублирования, очищаем старые обработчики
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.info(f"✅ Логирование инициализировано (уровень = {level})")
