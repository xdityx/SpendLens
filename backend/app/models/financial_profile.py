from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class FinancialProfile(Base, TimestampMixin):
    __tablename__ = "financial_profiles"

    id = uuid_pk()
    monthly_savings_target: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    salary_day: Mapped[int] = mapped_column(nullable=False)
