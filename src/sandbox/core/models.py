# TODO: implement src/sandbox/core/models.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class Status(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"

@dataclass
class Limits:
    cpu_seconds: int
    memory_bytes: int
    nofile: int
    wall_timeout_seconds: int

@dataclass
class Job:
    job_id: str
    lang: str         # "python" | "node" | "bash" | ...
    entry: str        # tên file chính (vd main.py, script.js, run.sh)
    workspace: Path   # thư mục job/<id>
    script_path: Path # đường dẫn đầy đủ tới entry

@dataclass
class Result:
    status: Status
    rc: int
    reason: Optional[str]
    stdout: str
    stderr: str
    duration_s: float
