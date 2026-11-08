from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CustomerInput(BaseModel):
    """One customer. Spend is read in the same currency as the training data (GBP)."""

    recency_days: float = Field(ge=0, le=3650, description="Days since the last purchase")
    orders: int = Field(ge=1, le=5000)
    total_spend: float = Field(gt=0, le=10_000_000)
    tenure_days: float = Field(ge=0, le=7300, description="Days since the first purchase")
    product_variety: int = Field(ge=1, le=20000, description="Different products bought")


SegmentKey = Literal["vip", "regular", "deal", "new"]


class SegmentStats(BaseModel):
    """Group averages only. No customer rows are accepted here."""

    key: SegmentKey
    customers: int = Field(ge=0)
    customer_share: float = Field(ge=0, le=1)
    revenue: float = Field(ge=0, default=0)
    revenue_share: float = Field(ge=0, le=1)
    medians: dict[str, float] = {}


class PersonaRequest(BaseModel):
    segment: SegmentStats
    currency: str = Field(default="", max_length=3)


class PriorityRow(BaseModel):
    customer_id: str = Field(max_length=64)
    total_spend: float
    reason: str = Field(max_length=200)
    action: str = Field(max_length=80)


class ReportRequest(BaseModel):
    source_label: str = Field(max_length=200)
    currency: str = Field(default="", max_length=3)
    customers: int = Field(ge=0)
    total_revenue: float = Field(ge=0)
    segments: list[SegmentStats] = Field(max_length=4)
    priority: list[PriorityRow] = Field(default=[], max_length=25)


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
    message: str = Field(min_length=10, max_length=5000)
    botcheck: bool = False

    @field_validator("name", "message")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()
