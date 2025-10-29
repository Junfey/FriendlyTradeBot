from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

class DCAConfig(BaseModel):
    symbol: str = Field(..., description="Пара, например BTC/USDT")
    amount: Decimal = Field(..., gt=Decimal("0"), description="Объём покупки в базовой валюте")
    interval: int = Field(..., gt=0, le=1440, description="Интервал повторения в минутах")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")
