from __future__ import annotations
import subprocess
import time
import signal
import os
from typing import Dict, Optional, Callable, List
from ..core.models import Result, Status, Job, Limits
from .rlimits import apply_rlimits
from pathlib import Path

class PythonRunner:
    def __init__(self, python_bin: str = "python3"):
        self.python_bin = python_bin

    def run(
        self,
        job: Job,
        limits: Limits,
        env: Dict[str, str],
        wrap_cmd: Optional[Callable[[List[str]], List[str]]] = None,
        preexec=None,
    ) -> Result:
        """
        Chạy file Python trong workspace, áp rlimits + pipeline isolation (wrap_cmd, preexec).
        """

        if not job.script_path.exists():
            job.script_path.write_text("# empty\n", encoding="utf-8")

        # Lệnh chạy Python entry với seccomp
        # Đây sẽ là python3 -m sandbox.runner.seccomp_entry <policy_path> <script_path>
        # mà seccomp entry file sẽ xử lý seccomp như lớp cuối cùng
        policy_path = Path("conf/seccomp.min.yaml").resolve()  # Đảm bảo dùng absolute path
        cmd = [
            self.python_bin,
            "-m",
            "sandbox.runner.seccomp_entry",  # chạy module entry của sandbox
            str(policy_path),  # file seccomp policy
            str(job.script_path),  # script Python thực thi
        ]

        if wrap_cmd:
            cmd = wrap_cmd(cmd)

        # preexec thực sự chạy trong child, trước execve("python3", ...)
        def _preexec():
            # Áp rlimits
            apply_rlimits(
                limits.cpu_seconds,
                limits.memory_bytes,
                limits.nofile
            )
            # Không áp seccomp nữa vì seccomp sẽ được xử lý trong entry (seccomp_entry.py)

        start = time.time()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(job.workspace),
                env={**os.environ, **env},
                preexec_fn=_preexec,
            )

            out, err = proc.communicate(timeout=limits.wall_timeout_seconds)
            rc = proc.returncode
            status = Status.FINISHED if rc == 0 else Status.FAILED
            reason = None if rc == 0 else f"exit_{rc}"

        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            status = Status.FAILED
            rc = -signal.SIGKILL
            reason = f"timeout_{limits.wall_timeout_seconds}s"
            err = (err or "") + f"\n[timeout] exceeded {limits.wall_timeout_seconds}s"

        except Exception as e:
            status = Status.FAILED
            rc = -1
            reason = f"runner_error:{e}"
            out, err = "", str(e)

        dur = time.time() - start
        return Result(status=status, rc=rc, reason=reason, stdout=out, stderr=err, duration_s=dur)
