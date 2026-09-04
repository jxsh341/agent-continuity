"""Condition B: conventional memory via self-hosted Mem0.

Mem0: 2.0.19, pinned commit 19cb89aff472325c707f64b2f34ae6afdbf7faf7
(local clone at C:/Users/user/mem0, installed editable).

Exactly what we invoke — no more, no less:
    prepare():        mem0.Memory.add(transcript_messages,
                                       user_id=run, infer=True)
                      -> Mem0's own single extraction LLM call,
                         fact extraction, dedup/hash machinery,
                         vector persistence (local Qdrant-on-disk).
    build_context():  mem0.Memory.search(query=next_task,
                                         user_id=run)
                      -> Mem0's own retrieval. No custom reranking.
                         Serialized and handed to the shared budget
                         enforcement in the runner.

Extractor LLM: shared frozen config from continuity.extraction
(same model/temp/top_p/max_tokens as C will use).
Embedder: local deterministic HuggingFace model (dependency of Mem0's
retrieval, not an experimental variable; endpoint account has no
embedding models enabled, recorded here for reproducibility).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conditions.base import ContextArtifact, ContinuityCondition, SessionRecord
from continuity.extraction import (
    EXTRACTOR_MAX_TOKENS,
    EXTRACTOR_MODEL,
    EXTRACTOR_TEMPERATURE,
    EXTRACTOR_TOP_P,
)
from continuity.tokens import TOKENIZER_ID, count_tokens

MEM0_VERSION = "2.0.19"
MEM0_COMMIT = "19cb89aff472325c707f64b2f34ae6afdbf7faf7"
EMBEDDER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384

_HEADER = "Retrieved project memories from prior sessions:"


class ConditionB(ContinuityCondition):
    name = "B"

    def __init__(self, store_root: Path | None = None):
        self._root = Path(store_root) if store_root else None
        self._memory = None  # lazy: no LLM/embedder touched until prepare()
        self._memory_count = 0
        self._sessions: list[dict] = []
        self._retrieval_log: list[dict] = []

    # -- mem0 plumbing --------------------------------------------------

    def _client(self):
        if self._memory is None:
            from mem0 import Memory  # pinned: see module docstring

            from agent.config import ModelConfig  # reuse endpoint conf

            mc = ModelConfig.from_env()
            config: dict[str, Any] = {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": EXTRACTOR_MODEL.replace("openai/", ""),
                        "api_key": mc.api_key,
                        "openai_base_url": mc.base_url,
                        "temperature": EXTRACTOR_TEMPERATURE,
                        "top_p": EXTRACTOR_TOP_P,
                        "max_tokens": EXTRACTOR_MAX_TOKENS,
                    },
                },
                "embedder": {
                    "provider": "huggingface",
                    "config": {"model": EMBEDDER_MODEL},
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": "condition_b",
                        "path": str((self._root or Path(".mem0_run")) / "qdrant"),
                        "embedding_model_dims": EMBEDDING_DIMS,
                        "on_disk": True,
                    },
                },
                "version": "v1.1",
            }
            self._memory = Memory.from_config(config)
        return self._memory

    # -- condition contract ---------------------------------------------

    def prepare(self, previous_session: SessionRecord) -> None:
        messages = previous_session.get("messages") or []
        if not messages:
            return
        # Chunked add() calls: whole-session transcripts hit the LLM
        # API timeout inside Mem0 (600s client default we cannot tune
        # without forking Mem0). Chunking is a usage choice, not a code
        # change; recorded in metadata.
        chunk_size = 8
        max_chunk_attempts = 3  # infrastructure retry: Mem0 2.0.19 logs
        # "Error parsing extraction response" and returns zero results on
        # LLM output flakes, with no retry of its own. Attempts are
        # recorded in metadata; content is never modified by us.
        added_ids: list = []
        attempts_log: list[dict] = []
        for start in range(0, len(messages), chunk_size):
            chunk = messages[start : start + chunk_size]
            chunk_added: list = []
            for attempt in range(1, max_chunk_attempts + 1):
                try:
                    result = self._client().add(chunk, user_id="continuity-run", infer=True)
                    ids = (
                        [m.get("id") for m in result.get("results", [])]
                        if isinstance(result, dict) else []
                    )
                except Exception:  # endpoint flake; retry, never crash the run
                    ids = []
                if ids or attempt == max_chunk_attempts:
                    chunk_added = ids
                    attempts_log.append(
                        {"chunk_start": start, "attempts": attempt,
                         "stored": len(ids)}
                    )
                    break
            added_ids.extend(chunk_added)
        self._memory_count += len(added_ids)
        self._sessions.append(
            {
                "session_index": previous_session.get("session_index"),
                "n_messages": len(messages),
                "n_chunks": (len(messages) + chunk_size - 1) // chunk_size,
                "memories_added": added_ids,
                "chunk_attempts": attempts_log,
            }
        )

    def build_context(self, budget_tokens: int, task: str | None = None) -> ContextArtifact:
        if self._memory_count == 0:
            return ContextArtifact(
                text="", token_count=0, budget_tokens=budget_tokens,
                truncated=False, condition=self.name,
                provenance=self._provenance(budget_tokens, [], 0),
            )
        query = task or "project state, decisions, and open work"
        hits = self._client().search(
            query,
            filters={"user_id": "continuity-run"},
            top_k=50,
        )
        results = hits.get("results", []) if isinstance(hits, dict) else hits
        memory_ids = [r.get("id") for r in results]
        self._retrieval_log.append(
            {"query": query, "memory_ids": memory_ids,
             "scores": [r.get("score") for r in results]}
        )
        lines = [f"- {r.get('memory', '')}" for r in results]
        text_unbounded = _HEADER + "\n" + "\n".join(lines)
        before = count_tokens(text_unbounded)
        # Fit-first within the interface; the runner's shared budgeter
        # independently verifies/enforces the ceiling on the artifact.
        kept: list[str] = []
        total = count_tokens(_HEADER)
        truncated = False
        for line in lines:
            n = count_tokens(line)
            if total + n > budget_tokens:
                truncated = True
                break
            kept.append(line)
            total += n
        text = "" if not kept else _HEADER + "\n" + "\n".join(kept)
        return ContextArtifact(
            text=text,
            token_count=count_tokens(text) if kept else 0,
            budget_tokens=budget_tokens,
            truncated=truncated,
            condition=self.name,
            provenance=self._provenance(
                budget_tokens, memory_ids, before,
                kept=len(kept), total=len(lines),
            ),
        )

    def metadata(self) -> dict:
        return {
            "condition": self.name,
            "system": "mem0",
            "version": MEM0_VERSION,
            "commit": MEM0_COMMIT,
            "extractor": {
                "model": EXTRACTOR_MODEL,
                "temperature": EXTRACTOR_TEMPERATURE,
                "top_p": EXTRACTOR_TOP_P,
                "max_tokens": EXTRACTOR_MAX_TOKENS,
            },
            "embedder": {"provider": "huggingface", "model": EMBEDDER_MODEL},
            "vector_store": "qdrant (local, on-disk)",
            "retrieval_method": "mem0.Memory.search (native)",
            "add_chunk_size": 8,
            "add_chunk_max_attempts": 3,
            "sessions_consumed": self._sessions,
            "retrieval_log": self._retrieval_log,
        }

    def _provenance(self, budget, memory_ids, before, kept=None, total=None) -> dict:
        d = {
            "system": f"mem0 {MEM0_VERSION}",
            "commit": MEM0_COMMIT,
            "tokenizer": TOKENIZER_ID,
            "budget": budget,
            "tokens_before_budget": before,
            "memory_ids": memory_ids,
            "extractor_model": EXTRACTOR_MODEL,
        }
        if kept is not None:
            d["memories_kept"] = kept
            d["memories_returned"] = total
        return d
