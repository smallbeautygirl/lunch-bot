"""The card goes out even when a part that only decorates it blows up.

Each source catches the failures it knows about. This is the last line for
the ones nobody thought of: on 2026-11-26 a mistyped date in a horoscope
headline raised ValueError and neither card was posted that day."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def or_none[Result](fetch: Callable[..., Result], *args: object) -> Result | None:
    try:
        return fetch(*args)
    except Exception:  # noqa: BLE001 - the boundary described above
        logger.exception("Optional part failed: %s", fetch.__name__)
        return None
