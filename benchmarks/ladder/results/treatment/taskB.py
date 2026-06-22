from typing import Any


def recent_values(items: list[dict], n: int) -> list[str]:
    if not isinstance(items, list):
        raise TypeError("items must be a list")
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    return [
        item["value"]
        for item in sorted(items, key=lambda x: x["timestamp"], reverse=True)[:n]
    ]
