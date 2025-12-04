from __future__ import annotations
import subprocess
import time
import signal
import os
from typing import Dict, Optional, Callable, List

from ..core.models import Result, Status, Job, Limits
from .rlimits import apply_rlimits   # vẫn import, đề phòng sau này dùng lại
import resource  # <--- thêm import này


class GoRunner:
    def __init__(self, go_bin: str = "go"):
        self.go_bin = go_bin

    def run(
        self,
        job: Job,
        limits: Limits,
        env: Dict[str, str],
        wrap_cmd: Optional[Callable[[List[str]], List[str]]] = None,
        preexec=None,
    ) -> Result:
        """
        Chạy file Go trong workspace bằng `go run <script_path>`,
        áp rlimits (CPU, NOFILE) + pipeline isolation (wrap_cmd, preexec).
        KHÔNG giới hạn RLIMIT_AS để Go runtime có thể reserve address space lớn.
        """

        if not job.script_path.exists():
            # Nếu vì lý do gì đó file không tồn tại, tạo file Go rỗng tối thiểu
            job.script_path.write_text(
                "package main\nfunc main(){}\n",
                encoding="utf-8",
            )

        cmd: List[str] = [
            self.go_bin,
            "run",
            str(job.script_path),
        ]

        if wrap_cmd:
            cmd = wrap_cmd(cmd)

        def _preexec():
            # --- TỰ SET RLIMIT CHO GO ---
            # Giới hạn CPU
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (limits.cpu_seconds, limits.cpu_seconds),
            )
            # Giới hạn số file mở
            # resource.setrlimit(
            #     resource.RLIMIT_NOFILE,
            #     (limits.nofile, limits.nofile),
            # )
            go_nofile = max(limits.nofile, 4096)
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (go_nofile, go_nofile),
            )
            # KHÔNG set RLIMIT_AS (address space) cho Go
            # để tránh lỗi "failed to reserve page summary memory"

            # Nếu pipeline có preexec riêng (ns/chroot/cgroups) thì gọi nó
            if preexec is not None:
                preexec()

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

        except subprocess.TimeoutExpired as e:
            # Hết thời gian → kill process
            proc.kill()
            try:
                _out, _err = proc.communicate(timeout=1)
                out = _out or ""
                err = _err or ""
            except Exception:
                out = ""
                err = ""

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
        return Result(
            status=status,
            rc=rc,
            reason=reason,
            stdout=out or "",
            stderr=err or "",
            duration_s=dur,
        )
