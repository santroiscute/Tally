from decimal import Decimal, ROUND_HALF_UP


def as_money(value: Decimal | int | float | str) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    cleaned = str(value).replace(",", "").strip()
    return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
