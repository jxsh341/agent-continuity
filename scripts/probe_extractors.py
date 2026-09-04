"""Probe: which candidate extractor models parse reliably in Mem0?"""

import json
import os
import shutil
import sys

from mem0 import Memory

KEY = os.environ["LLM_API_KEY"]
BASE = "https://integrate.api.nvidia.com/v1"
FACTS = (
    "Project facts: the max retry budget for pipeline workers is 17. "
    "The staging region is eu-west-3. The log retention is 45 days. "
    "The build sandbox has 8 vCPUs. Also: cache TTL is 900 seconds, "
    "payload limit 4 MiB, worker memory 3 GiB, on-call rotates Mondays, "
    "flags are kebab-case, deploy window Tue 02:00-04:00 UTC, JSON indent "
    "2 spaces, default branch renamed to trunk."
)
MSGS = [
    {"role": "user", "content": FACTS},
    {"role": "assistant", "content": "Understood, I will keep these outside the workspace."},
]

for model in sys.argv[1:]:
    path = f"C:/Users/user/AppData/Local/Temp/probe_{model.replace('/', '_')}"
    shutil.rmtree(path, ignore_errors=True)
    config = {
        "llm": {"provider": "openai", "config": {
            "model": model, "api_key": KEY, "openai_base_url": BASE,
            "temperature": 0.0, "top_p": 1.0, "max_tokens": 2048}},
        "embedder": {"provider": "huggingface", "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2"}},
        "vector_store": {"provider": "qdrant", "config": {
            "collection_name": "probe", "path": path,
            "embedding_model_dims": 384, "on_disk": True}},
        "version": "v1.1",
    }
    try:
        m = Memory.from_config(config)
        r = m.add(MSGS, user_id="probe", infer=True)
        results = r.get("results", [])
        print(f"== {model}: stored {len(results)}")
        for x in results:
            print("   -", (x.get("memory") or "")[:110])
    except Exception as e:
        print(f"== {model}: FAIL {type(e).__name__}: {str(e)[:140]}")
    finally:
        shutil.rmtree(path, ignore_errors=True)
