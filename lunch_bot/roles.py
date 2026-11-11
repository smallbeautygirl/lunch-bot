"""Who does what in the group (BD / PM / FAE / RD …), so each sign's fortune is
set in its members' own workday instead of an RD's GPU queue for everyone.

The MEMBER_ROLES secret maps the names used in GROUP_MEMBERS to a role. It
stays a secret for the same reason: this repo and its Actions logs are public."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter

logger = logging.getLogger(__name__)

# Core themes, not concrete events: "check the quote's units" misses on any
# day without a quote, while "what the client really cares about" fits every
# BD every day and still reads as theirs.
ROLE_SCENES = (
    "各職位每天都會碰到的核心課題（寫運勢時依該星座成員的職位挑一個）："
    "BD：讀懂對方真正在意什麼、關係與時機、耐心等回音；海外 BD 再加上跨文化與時差。"
    "PM：取捨優先順序、讓不同的人對齊、說不的勇氣。"
    "FAE：現場的應變、把技術翻成客戶聽得懂的話、在客戶和 RD 之間當橋樑。"
    "RD：把問題拆小、專注與被打斷、品質和速度的拉扯；模擬組的 RD 再加上"
    "「模擬和真實世界的落差」。"
    "DevOps：穩定與變更的平衡、預防勝於救火、被需要時才被想起。"
    "RD 主管：把人放對位置、替團隊擋事、放手與信任。"
    "寫法：停在課題的層次，最多用一個職位用語點出是在說誰，"
    "不要寫具體的物件、工具、數字或事件（例如報價單、分號、告警規則、某個會議），"
    "讓那個職位的人每天讀都對得上。"
    "一個星座有多種職位時，挑大家共通的課題（溝通、節奏、優先順序），"
    "或點名其中一群（例如「FAE 們」）。"
)


def read_member_roles() -> dict[str, str]:
    raw = os.getenv("MEMBER_ROLES", "").strip()
    if not raw:
        return {}
    try:
        roles = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("MEMBER_ROLES is not valid JSON")
        return {}
    if not isinstance(roles, dict):
        logger.warning("MEMBER_ROLES must be a JSON object")
        return {}
    return {str(name): str(role) for name, role in roles.items()}


def role_mix(names: list[str], roles: dict[str, str]) -> str:
    """「RD×2、PM×1」, most common first; "" when nobody's role is known."""
    counts = Counter(roles[name] for name in names if name in roles)
    return "、".join(f"{role}×{count}" for role, count in counts.most_common())


def role_mixes(members: dict[str, list[str]], roles: dict[str, str]) -> dict[str, str]:
    """Sign → role mix. Logs how many members have no role (never who), so a
    name spelled differently in the two secrets shows up in the Actions log."""
    names = [name for sign_names in members.values() for name in sign_names]
    unknown = sum(1 for name in names if name not in roles)
    if roles and unknown:
        logger.info("Members without a role: %d", unknown)
    mixes = {sign: role_mix(sign_names, roles) for sign, sign_names in members.items()}
    return {sign: mix for sign, mix in mixes.items() if mix}
