# TODO: implement src/sandbox/runner/node_runner.py
import os
import signal
import subprocess
import time
from typing import Dict, List, Optional, Callable
from ..core.models import Result, Status, Job, Limits

class NodeRunner:
    def __init__(self, node_bin: str = "node"):
        self.node_bin = node_bin

    def run(self, job: Job, limits: Limits, env: Dict[str, str], wrap_cmd: Optional[Callable[[List[str]], List[str]]] = None) -> Result:
        """
        Chạy mã Node.js trong workspace, áp dụng các giới hạn tài nguyên.
        """
        if not job.script_path.exists():
            job.script_path.write_text("# empty\n", encoding="utf-8")

        cmd = [self.node_bin, str(job.script_path)]
        if wrap_cmd:
            cmd = wrap_cmd(cmd)

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(job.workspace),
                timeout=limits.wall_timeout_seconds,
                env={**os.environ, **env},
            )
            status = Status.FINISHED if proc.returncode == 0 else Status.FAILED
            rc = proc.returncode
            reason = None if rc == 0 else f"exit_{rc}"
            out, err = proc.stdout, proc.stderr

        except subprocess.TimeoutExpired as e:
            status = Status.FAILED
            rc = -signal.SIGKILL
            reason = f"timeout_{limits.wall_timeout_seconds}s"
            out = (e.stdout or "")
            err = (e.stderr or "") + f"\n[timeout] exceeded {limits.wall_timeout_seconds}s"

        except Exception as e:
            status = Status.FAILED
            rc = -1
            reason = f"runner_error:{e}"
            out, err = "", str(e)

        dur = time.time() - start
        return Result(status=status, rc=rc, reason=reason, stdout=out, stderr=err, duration_s=dur)
