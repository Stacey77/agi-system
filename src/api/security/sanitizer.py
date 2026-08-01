"""Lightweight prompt injection sanitizer.

Strips common prompt injection patterns from user-supplied text before it
reaches any LLM.  This is a defence-in-depth measure; it is not a
substitute for proper input validation or output filtering.

Patterns targeted:
- Role / system override attempts  (e.g. "ignore previous instructions", "new system prompt:")
- Instruction-leak / exfiltration probes  (e.g. "print your instructions", "reveal your prompt")
- Jailbreak framing  (e.g. "DAN mode", "developer mode", "act as …")
- Delimiter injection  (sequences used to forge chat-message boundaries)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_ROLE_OVERRIDE_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"override\s+(your\s+)?(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*(you\s+are|act\s+as)", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
]

_INSTRUCTION_LEAK_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(r"(print|reveal|show|output|repeat|display)\s+(your\s+)?(system\s+)?(prompt|instructions?|context|training)", re.IGNORECASE),
    re.compile(r"what\s+(are|were)\s+your\s+(original\s+)?instructions?", re.IGNORECASE),
    re.compile(r"(leak|exfiltrate)\s+(your\s+)?(prompt|instructions?|context)", re.IGNORECASE),
]

_JAILBREAK_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(r"\bDAN\s+mode\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?a\s+(different|unrestricted|unfiltered)\s+(AI|model|assistant)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(AI|model|assistant)\s+(without|with\s+no)\s+(restrictions?|rules?|guidelines?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?(unrestricted|unfiltered|uncensored)", re.IGNORECASE),
]

_ALL_PATTERNS: list[re.Pattern[str]] = [
    *_ROLE_OVERRIDE_PATTERNS,
    *_INSTRUCTION_LEAK_PATTERNS,
    *_JAILBREAK_PATTERNS,
]

# Maximum allowed input length (characters).  Inputs beyond this are truncated
# before pattern matching to prevent ReDoS via pathologically long strings.
_MAX_INPUT_LENGTH = 32_000


def sanitize(text: str) -> str:
    """Return *text* with prompt injection patterns removed.

    The original structure is preserved; matched substrings are replaced with
    an empty string.  The caller should treat the returned value as the
    canonical input to pass to the LLM.

    If *text* is not a string it is returned unchanged.
    """
    if not isinstance(text, str):
        return text  # type: ignore[return-value]

    # Truncate before matching to guard against ReDoS
    truncated = text[:_MAX_INPUT_LENGTH]
    cleaned = truncated

    for pattern in _ALL_PATTERNS:
        if pattern.search(cleaned):
            logger.warning(
                "Prompt injection pattern detected and stripped: pattern=%r",
                pattern.pattern,
            )
            cleaned = pattern.sub("", cleaned)

    # Collapse runs of whitespace introduced by stripping
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned
