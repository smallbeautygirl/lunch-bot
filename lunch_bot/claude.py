from __future__ import annotations

import logging
import os

import anthropic
from pydantic import BaseModel

from .config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 4000


def ask_claude[Output: BaseModel](
    prompt: str,
    output_format: type[Output],
    *,
    model: str = CLAUDE_MODEL,
    effort: str = "medium",
) -> Output | None:
    """None on any failure, so a post never blocks on the generated parts."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        # The SDK raises TypeError (not APIError) when it has no credentials.
        logger.warning("ANTHROPIC_API_KEY not set, skipping generated content")
        return None
    try:
        response = anthropic.Anthropic().messages.parse(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
            output_format=output_format,
        )
    except anthropic.APIError as error:
        logger.warning("Claude content failed", extra={"error": str(error)})
        return None
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        logger.warning("Claude content unusable", extra={"stop": response.stop_reason})
        return None
    return response.parsed_output
