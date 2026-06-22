from typing import Mapping


def is_enabled(flags: Mapping[str, bool], name: str) -> bool:
    """Return True if *name* is present and enabled in *flags*, False otherwise."""
    if not isinstance(name, str):
        raise TypeError(f"flag name must be a str, got {type(name).__name__!r}")
    return bool(flags.get(name, False))
