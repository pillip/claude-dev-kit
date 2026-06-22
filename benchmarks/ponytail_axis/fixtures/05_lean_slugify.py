"""Convert a title into a URL slug."""

import re


def slugify(title: str) -> str:
    lowered = title.strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
