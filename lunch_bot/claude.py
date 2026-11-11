from __future__ import annotations

import logging
import os

import anthropic
from pydantic import BaseModel, ValidationError

from .config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Thinking counts against this too; at 4000 the two-source horoscope prompt
# was cut off mid-JSON about half the time. Billing is per token used.
MAX_OUTPUT_TOKENS = 16000
ATTEMPTS = 2


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
    for attempt in range(1, ATTEMPTS + 1):
        output = _ask_once(prompt, output_format, model=model, effort=effort)
        if output is not None:
            return output
        logger.warning("Claude attempt failed", extra={"attempt": attempt})
    return None


def _ask_once[Output: BaseModel](
    prompt: str, output_format: type[Output], *, model: str, effort: str
) -> Output | None:
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
    except ValidationError as error:
        # The SDK parses inside .parse(), so a cut-off reply raises here
        # before its stop_reason can be checked; it once took down the
        # whole morning card.
        logger.warning("Claude reply was not valid JSON", extra={"error": str(error)})
        return None
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        logger.warning("Claude content unusable", extra={"stop": response.stop_reason})
        return None
    return response.parsed_output
