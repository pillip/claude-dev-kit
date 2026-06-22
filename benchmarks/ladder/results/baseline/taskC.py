"""Feature flag management module.

Provides a simple, immutable interface for checking whether named feature flags
are enabled, treating unknown flags as disabled.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional


class FeatureFlags:
    """Immutable feature flag registry.

    Parameters
    ----------
    flags:
        A mapping of flag names to their enabled state.  The mapping is
        copied on construction so later mutations to the source dict do not
        affect this instance.

    Examples
    --------
    >>> flags = FeatureFlags({"dark_mode": True, "beta_ui": False})
    >>> flags.is_enabled("dark_mode")
    True
    >>> flags.is_enabled("beta_ui")
    False
    >>> flags.is_enabled("unknown_flag")
    False
    """

    def __init__(self, flags: Mapping[str, bool]) -> None:
        if not isinstance(flags, Mapping):
            raise TypeError(f"flags must be a Mapping, got {type(flags).__name__!r}")
        self._flags: dict[str, bool] = {
            self._validate_key(k): bool(v) for k, v in flags.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_enabled(self, name: str) -> bool:
        """Return ``True`` if *name* is a known, enabled flag; ``False`` otherwise.

        An unknown flag is treated as disabled.

        Parameters
        ----------
        name:
            The feature flag name to check.

        Returns
        -------
        bool
            Enabled state of the flag (``False`` for unknown flags).
        """
        if not isinstance(name, str):
            raise TypeError(f"flag name must be a str, got {type(name).__name__!r}")
        return self._flags.get(name, False)

    def get(self, name: str, default: Optional[bool] = None) -> Optional[bool]:
        """Return the flag value, or *default* if the flag is not registered.

        Unlike :meth:`is_enabled`, this preserves the distinction between an
        explicitly disabled flag and an unknown flag when *default* differs
        from ``False``.

        Parameters
        ----------
        name:
            The feature flag name.
        default:
            Value returned when *name* is not present in the registry.
            Defaults to ``None``.
        """
        if not isinstance(name, str):
            raise TypeError(f"flag name must be a str, got {type(name).__name__!r}")
        return self._flags.get(name, default)

    def __contains__(self, name: object) -> bool:
        """Return ``True`` if *name* is a registered flag (enabled or not)."""
        return name in self._flags

    def __len__(self) -> int:
        return len(self._flags)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}({self._flags!r})"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_key(key: object) -> str:
        if not isinstance(key, str):
            raise TypeError(f"flag names must be str, got {type(key).__name__!r}")
        if not key:
            raise ValueError("flag name must not be empty")
        return key


def is_enabled(flags: Mapping[str, bool], name: str) -> bool:
    """Check whether a feature flag is enabled in a plain mapping.

    Functional convenience wrapper that avoids constructing a
    :class:`FeatureFlags` instance for one-off checks.

    Parameters
    ----------
    flags:
        A mapping of flag names to their enabled state.
    name:
        The feature flag name to check.

    Returns
    -------
    bool
        ``True`` if the flag exists and is ``True``; ``False`` otherwise.
        An unknown flag is treated as disabled.

    Examples
    --------
    >>> is_enabled({"dark_mode": True}, "dark_mode")
    True
    >>> is_enabled({"dark_mode": True}, "missing")
    False
    """
    if not isinstance(flags, Mapping):
        raise TypeError(f"flags must be a Mapping, got {type(flags).__name__!r}")
    if not isinstance(name, str):
        raise TypeError(f"flag name must be a str, got {type(name).__name__!r}")
    return bool(flags.get(name, False))
