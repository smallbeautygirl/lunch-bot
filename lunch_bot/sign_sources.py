"""What the two weekly horoscopes say about one sign, and where they clash."""

from __future__ import annotations

from dataclasses import dataclass

from .mafalda import MafaldaReading, MafaldaSign, MafaldaTier
from .weekly_reading import SignReading, WeeklyReading

MIN_STARS = 1
MAX_STARS = 5
TANG_STAR_RANGES = {"讚的": (4, 5), "穩的": (2, 4), "累的": (1, 2)}
MAFALDA_STAR_RANGES = {
    MafaldaTier.TOP: (4, 5),
    MafaldaTier.NORMAL: (2, 4),
    MafaldaTier.SLIPPING: (1, 2),
}
# Only opposite verdicts count: 穩的 against 前段班 is a nuance, not a clash.
CLASHES = {("累的", MafaldaTier.TOP), ("讚的", MafaldaTier.SLIPPING)}


@dataclass(frozen=True)
class SignSources:
    tang: SignReading | None
    mafalda: MafaldaSign | None

    @property
    def mafalda_tier(self) -> MafaldaTier | None:
        return self.mafalda.tier if self.mafalda else None

    @property
    def is_clash(self) -> bool:
        if self.tang is None or self.mafalda_tier is None:
            return False
        return (self.tang.tier, self.mafalda_tier) in CLASHES

    @property
    def star_range(self) -> tuple[int, int]:
        """Within both sources' ranges where they overlap; between them (the
        nearer ends) where they clash, so neither verdict is simply dropped."""
        ranges = []
        if self.tang:
            ranges.append(TANG_STAR_RANGES[self.tang.tier])
        if self.mafalda_tier:
            ranges.append(MAFALDA_STAR_RANGES[self.mafalda_tier])
        if not ranges:
            return MIN_STARS, MAX_STARS
        low, high = max(lo for lo, _ in ranges), min(hi for _, hi in ranges)
        return (low, high) if low <= high else (high, low)


def collect_sources(
    signs: list[str], tang: WeeklyReading | None, mafalda: MafaldaReading | None
) -> dict[str, SignSources]:
    return {
        sign: SignSources(
            tang=tang.signs.get(sign) if tang else None,
            mafalda=mafalda.signs.get(sign) if mafalda else None,
        )
        for sign in signs
    }
