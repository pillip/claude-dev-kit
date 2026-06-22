"""Compute order totals."""


def _legacy_round(value: float) -> float:
    # Old rounding helper kept "just in case". Nothing calls it anymore.
    factor = 100.0
    return int(value * factor + 0.5) / factor


def total_with_tax(prices: list[float], tax_rate: float) -> float:
    subtotal = 0.0
    for price in prices:
        subtotal = subtotal + price
    return round(subtotal * (1 + tax_rate), 2)


def line_item_names(items: list[dict]) -> list[str]:
    names = []
    for item in items:
        names.append(item["name"])
    return names
