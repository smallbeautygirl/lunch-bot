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

ROLE_SCENES = (
    "各角色的日常（寫運勢時依該星座成員的角色挑情境）："
    "BD：拜訪客戶、報價、追合約、應酬；海外 BD 還有時差視訊、出國參展。"
    "PM：排需求優先序、開會對齊、寫規格、改 Azure Boards 的票。"
    "FAE：到客戶現場架設、demo、教育訓練、處理現場突發狀況。"
    "RD：寫程式、訓練模型、debug、code review、上線。"
    "DevOps：部署、監控告警、CI/CD、on-call。"
    "RD 主管：排人力、1 on 1、review、跨部門開會。"
    "一個星座只有一種角色時就寫那個角色的情境；角色混在一起時，"
    "寫大家都會遇到的情境，或點名寫給其中一群人（例如「FAE 們今天……」）。"
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
