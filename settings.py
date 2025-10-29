# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Универсальные поля (можно переиспользовать для любой биржи)
    TELEGRAM_TOKEN: str

    # Основные (нейтральные) ключи
    EXCHANGE_API_KEY: str | None = None
    EXCHANGE_API_SECRET: str | None = None
    EXCHANGE_NAME: str = "binance"  # по умолчанию Binance
    USE_TESTNET: bool = True

    # Альтернативные (Binance-специфичные)
    BINANCE_API_KEY: str | None = None
    BINANCE_API_SECRET: str | None = None
    MODE: str | None = None  # "testnet" | "mainnet"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def api_key(self) -> str:
        return self.EXCHANGE_API_KEY or self.BINANCE_API_KEY or ""

    @property
    def api_secret(self) -> str:
        return self.EXCHANGE_API_SECRET or self.BINANCE_API_SECRET or ""

    @property
    def is_testnet(self) -> bool:
        if self.MODE:
            return self.MODE.lower() == "testnet"
        return self.USE_TESTNET


# --- экземпляр глобальных настроек ---
settings = Settings()

# --- Для совместимости со старым кодом ---
EXCHANGE_API_KEY = settings.api_key
EXCHANGE_API_SECRET = settings.api_secret
EXCHANGE_NAME = settings.EXCHANGE_NAME
USE_TESTNET = settings.is_testnet
TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN