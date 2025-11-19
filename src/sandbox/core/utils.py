# TODO: implement src/sandbox/core/utils.py
from __future__ import annotations
import random, string, time

def new_job_id() -> str:
    suf = "".join(random.choice(string.hexdigits.lower()) for _ in range(6))
    return f"{int(time.time())}-{suf}"

def infer_lang_from_entry(entry: str) -> str:
    entry = entry.lower()
    if entry.endswith(".py"):  return "python"
    if entry.endswith(".js"):  return "node"
    if entry.endswith(".sh"):  return "bash"
    # mở rộng dần: .c .cpp .java .go ...
    return "python"
