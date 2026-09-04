"""Token accounting for context artifacts, outside any agent framework.

Single counting function used by every condition and by the runner, so
context budgets mean the same thing across A/B/C/D. The encoding is a
fixed harness constant; it need not match the LLM's exact tokenizer to
enforce consistent ceilings (it is recorded in every metadata blob).
"""

from __future__ import annotations

import tiktoken

_ENCODING_NAME = "cl100k_base"
_enc = tiktoken.get_encoding(_ENCODING_NAME)


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def truncate_lines_to_budget(
    lines: list[str], budget_tokens: int, keep: str = "newest"
) -> tuple[list[str], bool]:
    """Return (kept_lines, truncated?). Deterministic.

    keep="newest": drop from the front (oldest history first).
    """
    kept: list[str] = []
    total = 0
    ordered = list(reversed(lines)) if keep == "newest" else list(lines)
    for line in ordered:
        n = count_tokens(line)
        if total + n > budget_tokens:
            break
        kept.append(line)
        total += n
    if keep == "newest":
        kept.reverse()
    return kept, len(kept) < len(lines)


TOKENIZER_ID = _ENCODING_NAME
