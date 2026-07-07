from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator


ZERO = Decimal("0")


def parse_money(value: Any) -> Decimal:
    """Convert API money input to Decimal while avoiding Python floats."""

    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, bool):
        raise ValueError("Money values must not be booleans")
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, float):
        raise ValueError("Money values must be sent as strings or whole-number integers, not floats")
    elif isinstance(value, str):
        try:
            amount = Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Invalid money value") from exc
    else:
        raise ValueError("Invalid money value")

    if not amount.is_finite():
        raise ValueError("Money values must be finite")
    return amount


Money = Annotated[Decimal, BeforeValidator(parse_money)]
