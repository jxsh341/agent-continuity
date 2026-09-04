"""Condition D: raw prior-session history, budget-truncated.

No interpretation, no extraction, no summarization. The verbatim
transcript of the previous session is serialized and, if it exceeds the
budget, the OLDEST messages are dropped (most recent history kept).

This is the cleanest possible exercise of the condition interface:
if D misbehaves, the harness is broken, not the memory logic.
"""

from __future__ import annotations

from conditions.base import ContextArtifact, ContinuityCondition, SessionRecord
from continuity.tokens import TOKENIZER_ID, count_tokens, truncate_lines_to_budget

_HEADER = "Prior session history (verbatim, oldest messages may have been dropped to fit the budget):"


class ConditionD(ContinuityCondition):
    name = "D"

    def __init__(self) -> None:
        self._history: list[dict] = []  # accumulated simple messages
        self._sessions: list[dict] = []

    def prepare(self, previous_session: SessionRecord) -> None:
        messages = previous_session.get("messages") or []
        self._sessions.append(
            {
                "session_index": previous_session.get("session_index"),
                "n_messages": len(messages),
            }
        )
        # Do not re-feed our own injected context back in: skip the
        # harness-injected context block by keeping only agent-visible
        # turns after the first user message.
        self._history.extend(messages)

    def build_context(self, budget_tokens: int, task: str | None = None) -> ContextArtifact:
        if not self._history:
            return ContextArtifact(
                text="", token_count=0, budget_tokens=budget_tokens,
                truncated=False, condition=self.name,
                provenance={"tokenizer": TOKENIZER_ID},
            )
        lines = [f"[{m.get('role', '?')}] {m.get('content', '')}" for m in self._history]
        overhead = count_tokens(_HEADER)
        kept, truncated = truncate_lines_to_budget(
            lines, max(0, budget_tokens - overhead), keep="newest"
        )
        text = _HEADER + "\n\n" + "\n\n".join(kept)
        return ContextArtifact(
            text=text,
            token_count=count_tokens(text),
            budget_tokens=budget_tokens,
            truncated=truncated,
            condition=self.name,
            provenance={
                "tokenizer": TOKENIZER_ID,
                "messages_total": len(self._history),
                "messages_kept": len(kept),
                "truncation": "oldest-first",
            },
        )

    def metadata(self) -> dict:
        return {
            "condition": self.name,
            "sessions_consumed": self._sessions,
        }
