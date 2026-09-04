"""Probe: does Mem0 extraction parse fail on the single S1 task message?"""
import json
from pathlib import Path
from mem0 import Memory

task_events = json.loads(
    Path("results/stage0_4/A-1-500dd77e/session_1_events.json").read_text()
)
msg = next(e for e in task_events if e.get("llm_message"))
text = "".join(p.get("text", "") for p in msg["llm_message"]["content"])

m = Memory.from_config({
    "llm": {"provider": "openai", "config": {
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "api_key": __import__("os").environ["LLM_API_KEY"],
        "openai_base_url": "https://integrate.api.nvidia.com/v1",
        "temperature": 0.0}},
    "embedder": {"provider": "huggingface",
                 "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}},
    "vector_store": {"provider": "qdrant", "config": {
        "collection_name": "diag2", "path": "results/b_diag2/qdrant",
        "embedding_model_dims": 384, "on_disk": True}},
    "version": "v1.1",
})
r = m.add([{"role": "user", "content": text}], user_id="d", infer=True)
print("stored:", len(r.get("results", [])))
for x in r.get("results", []):
    print(" -", x.get("memory"))
