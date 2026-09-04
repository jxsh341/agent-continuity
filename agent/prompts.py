"""Frozen session-message construction.

Design decision (recorded for the protocol):
    The agent's SYSTEM prompt is the SDK default, frozen implicitly by
    pinning the SDK to an exact commit. We do NOT inject any
    experiment-specific text into the system prompt, and we do NOT tell
    the agent it is part of a continuity experiment.

    Experimental variation enters ONLY via the first user message,
    through the `initial_context` slot below. Conditions A/B/C/D differ
    solely in what (if anything) fills that slot.

Edit freeze: this template must not change after Stage 0 without
bumping the protocol version.
"""

SESSION_MESSAGE_TEMPLATE = """Your assigned task is:

{task}
{context_block}"""

_CONTEXT_BLOCK = """
The following project context is available:

{context}"""


def build_session_message(task: str, initial_context: str = "") -> str:
    """Build the single user message that starts a fresh session.

    initial_context == ""  -> Condition A (no memory survives).
    Otherwise              -> Condition B/C/D content, serialized by the
                              experiment layer. The agent cannot tell
                              which condition produced it.
    """
    context_block = (
        _CONTEXT_BLOCK.format(context=initial_context) if initial_context else ""
    )
    return SESSION_MESSAGE_TEMPLATE.format(task=task, context_block=context_block)
