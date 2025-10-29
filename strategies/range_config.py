from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

class RangeConfig(BaseModel):
    symbol: str = Field(..., description="Пара, например BTC/USDT")
    amount: Decimal = Field(..., gt=Decimal("0"))
    low: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    interval: int = Field(..., gt=0, le=1440)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")

    @field_validator("high")
    @classmethod
    def check_range(cls, v, values):
        low = values.get("low")
        if low and v <= low:
            raise ValueError("high должен быть больше low")
        return v
