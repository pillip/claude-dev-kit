"""
most_recent.py
--------------
Utility for extracting values from the N most recent items in a list of
timestamp/value dicts.
"""

from __future__ import annotations

from typing import TypedDict


class TimestampedItem(TypedDict):
    timestamp: int
    value: str


def most_recent_values(items: list[TimestampedItem], n: int) -> list[str]:
    """Return the values of the N most recent items, ordered highest timestamp first.

    Args:
        items: A list of dicts, each with an integer 'timestamp' and a string 'value'.
        n:     The maximum number of results to return.

    Returns:
        A list of at most *n* value strings, sorted by descending timestamp.

    Raises:
        ValueError: If *n* is negative.
        TypeError:  If any item is missing the required keys or has wrong types.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n!r}")
    if n == 0:
        return []

    sorted_items = sorted(items, key=lambda item: item["timestamp"], reverse=True)
    return [item["value"] for item in sorted_items[:n]]
