from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

class PercentConfig(BaseModel):
    symbol: str = Field(..., description="Пара, например BTC/USDT")
    amount: Decimal = Field(..., gt=Decimal("0"), description="Объём в базовой валюте")
    step: float = Field(..., gt=0, lt=100, description="Процент изменения для ордера")
    interval: int = Field(..., gt=0, le=1440, description="Интервал проверки в минутах")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")
