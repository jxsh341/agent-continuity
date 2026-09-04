"""Thin adapter: the ONLY module in this project that imports OpenHands.

Boundary contract
-----------------
OpenHands owns:  "given the context I was provided, reason and operate
                 the computer."
We own:          "what context the agent receives when a fresh session
                 starts."

Each `run_session` call creates a BRAND NEW LLM, Agent, and
Conversation. Nothing conversational survives between calls. The only
thing that crosses the session boundary is the serialized transcript we
harvest from the events afterward (which the experiment layer then
feeds to condition B/C/D extractors).

Pinned dependency: see configs/framework_pin.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Event, Tool
from openhands.sdk.event import LLMConvertibleEvent
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool

from agent.config import ModelConfig
from agent.models import AgentSessionResult
from agent.prompts import build_session_message

# Deliberately boring capability set for the continuity experiment.
# No web browsing / MCP: external information sources would be an
# uncontrolled variable.
DEFAULT_TOOLS = [TerminalTool, FileEditorTool]


class CodingAgent(Protocol):
    """The interface the experiment runner depends on.

    The runner must not be able to tell that OpenHands is underneath.
    """

    def run_session(
        self,
        task: str,
        workspace: Path,
        initial_context: str = "",
    ) -> AgentSessionResult: ...


class OpenHandsCodingAgent:
    def __init__(self, model_config: ModelConfig, framework_commit: str = ""):
        self.model_config = model_config
        self.framework_commit = framework_commit

    def run_session(
        self,
        task: str,
        workspace: Path,
        initial_context: str = "",
    ) -> AgentSessionResult:
        result = AgentSessionResult(
            task=task,
            workspace=str(workspace),
            initial_context=initial_context,
            agent_framework_commit=self.framework_commit,
        )

        events: list[dict] = []
        messages: list[dict] = []

        def collect(event: Event) -> None:
            try:
                events.append(event.model_dump(mode="json"))
            except Exception:  # transcript capture must never break a run
                events.append({"type": type(event).__name__})
            if isinstance(event, LLMConvertibleEvent):
                try:
                    msg = event.to_llm_message()
                    text = "".join(
                        c.text for c in msg.content if hasattr(c, "text")
                    )
                    if text:
                        messages.append({"role": msg.role, "content": text})
                except Exception:
                    pass

        llm = self._build_llm()
        agent = Agent(
            llm=llm,
            tools=[Tool(name=t.name) for t in DEFAULT_TOOLS],
        )
        conversation = Conversation(
            agent=agent,
            workspace=str(workspace),
            callbacks=[collect],
            max_iteration_per_run=self.model_config.max_iterations,
        )

        try:
            conversation.send_message(
                build_session_message(task=task, initial_context=initial_context)
            )
            conversation.run()
        except Exception as e:  # agent failure is a result, not a crash
            result.error = f"{type(e).__name__}: {e}"
        finally:
            conversation.close()

        result.events = events
        result.messages = messages
        if llm.metrics is not None:
            result.llm_metrics = llm.metrics.model_dump()
        return result

    def _build_llm(self) -> LLM:
        return LLM(
            usage_id="agent",
            model=self.model_config.model,
            api_key=SecretStr(self.model_config.api_key)
            if self.model_config.api_key
            else None,
            base_url=self.model_config.base_url,
            # Rate-limit-tolerant retry policy for shared/free-tier endpoints.
            num_retries=10,
            retry_min_wait=15,
            retry_max_wait=180,
            retry_multiplier=2.0,
        )


# Re-export for type-checking convenience; unused import otherwise.
_ = LLMConvertibleEvent
