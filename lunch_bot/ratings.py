"""A shop's Google rating. lunch-map carries it as a googleRating field on
some shops and only inside the note text (「Google 4.3★」) on most others."""

from __future__ import annotations

import re

# Below this a shop is not suggested; unrated shops stay in, since a quarter
# of the list (mostly small stalls) has no rating at all.
MIN_GOOGLE_RATING = 4.0
RATING_IN_NOTE = re.compile(r"Google ([\d.]+)★")


def google_rating(shop: dict) -> float | None:
    if shop.get("googleRating"):
        return float(shop["googleRating"])
    match = RATING_IN_NOTE.search(shop.get("note") or "")
    return float(match.group(1)) if match else None


def is_rated_well_enough(shop: dict) -> bool:
    rating = google_rating(shop)
    return rating is None or rating >= MIN_GOOGLE_RATING
