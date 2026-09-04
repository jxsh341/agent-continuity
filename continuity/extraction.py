"""Frozen shared extractor configuration.

B (Mem0) and C (structured state) MUST use the same extraction model
with identical sampling parameters and the same extraction input, so a
later B-vs-C difference can only be attributed to the representation,
not the extractor. C imports these constants directly; B hands them to
Mem0 as its LLM config.
"""

from __future__ import annotations

import os

# Frozen extractor model. Chosen by probe (scripts/probe_extractors.py):
# must (a) reliably emit the structured output Mem0's extraction prompt
# requires, (b) be shared verbatim by B and C. muse-glimmer-30b (the
# agent model) fails Mem0's JSON parsing on multi-fact transcripts;
# deepseek-v4-flash hangs on this account; gpt-oss-120b extracts 0 facts.
# Override with EXTRACTOR_MODEL env if the pin changes (record it).
EXTRACTOR_MODEL = os.getenv(
    "EXTRACTOR_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"
)
EXTRACTOR_TEMPERATURE = 0.0
EXTRACTOR_TOP_P = 1.0
EXTRACTOR_MAX_TOKENS = 2048


def extractor_identity() -> dict:
    return {
        "model": EXTRACTOR_MODEL,
        "temperature": EXTRACTOR_TEMPERATURE,
        "top_p": EXTRACTOR_TOP_P,
        "max_tokens": EXTRACTOR_MAX_TOKENS,
    }
