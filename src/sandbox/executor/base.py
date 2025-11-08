from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

@dataclass
class ExecSpec:
    cmd: List[str]
    workdir: Path
    env: Dict[str,str]
    timeout_s: int

class Executor:
    def prepare(self, job_id: str, workdir: Path, limits: dict): ...
    def run(self, job_id: str, spec: ExecSpec) -> int: ...
    def cleanup(self, job_id: str): ...
