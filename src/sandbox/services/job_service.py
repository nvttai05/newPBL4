from __future__ import annotations
from pathlib import Path
from typing import Dict

from ..core.models import Job, Limits, Result, Status
from ..core.settings import settings
from ..core.db import DB
from ..core.utils import new_job_id, infer_lang_from_entry
from .storage import LocalFSStorage
from ..runner.python_runner import PythonRunner
from ..isolation.isolation import IsolationPipeline, probe_capabilities



class JobService:
    """
    Orchestrator: ghép DB + Storage + Isolation pipeline + chọn runner theo ngôn ngữ.
    """

    def __init__(self):
        # DB nhúng (SQLite)
        self.db = DB(Path("sandbox.db"))

        # FS storage
        self.storage = LocalFSStorage(settings.jobs_dir)

        # Runners khả dụng
        self.python = PythonRunner(
            python_bin=settings.sandbox.get("runtimes", {}).get("python", "python3")
        )
        # TODO: thêm Node/Bash runner sau

        # Isolation pipeline (ns/chroot, cgroups, seccomp)
        self.iso = IsolationPipeline(
            strategy=settings.sandbox.get("iso_strategy", "none"),
            allow_network=bool(settings.sandbox.get("allow_network", False))
        )

    def _limits(self) -> Limits:
        lim = settings.limits
        return Limits(
            cpu_seconds=int(lim.get("cpu_seconds", 2)),
            memory_bytes=int(lim.get("memory_bytes", 128 * 1024 * 1024)),
            nofile=int(lim.get("nofile", 64)),
            wall_timeout_seconds=int(lim.get("wall_timeout_seconds", 5)),
        )

    def create_job(self, entry: str, code: str) -> str:
        job_id = new_job_id()
        lang = infer_lang_from_entry(entry)

        ws = self.storage.create_workspace(job_id)
        script_path = ws / entry
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(code, encoding="utf-8")

        self.db.insert_job(job_id, lang=lang, entry=entry)
        return job_id

    def run_job(self, job_id: str) -> None:
        row = self.db.get_job(job_id)
        if not row:
            raise ValueError("job_not_found")

        self.db.set_running(job_id)

        ws_abs = (settings.jobs_dir / job_id).resolve()
        ws_abs.mkdir(parents=True, exist_ok=True)

        script_abs = ws_abs / row["entry"]
        if not script_abs.exists():
            raise ValueError(f"script_not_found:{script_abs}")

        job = Job(
            job_id=job_id,
            lang=row["lang"],
            entry=row["entry"],
            workspace=ws_abs,
            script_path=script_abs,
        )
        limits = self._limits()

        # Xây pipeline isolation
        wrap_cmd, preexec = self.iso.build(job, limits)

        # === DIAG: tính lệnh thực tế + khả năng môi trường ===
        planned_cmd = None
        try:
            base_cmd = (
                [self.python.python_bin, str(job.script_path)]
                if job.lang == "python"
                else ["<unsupported_lang>"]
            )
            planned_cmd = wrap_cmd(base_cmd) if wrap_cmd else base_cmd
        except Exception:
            planned_cmd = ["<wrap_cmd_error>"]

        caps = probe_capabilities(
            allow_network=bool(settings.sandbox.get("allow_network", False)),
            strategy=settings.sandbox.get("iso_strategy", "none"),
        )

        # Chạy runner theo ngôn ngữ
        if job.lang == "python":
            res = self.python.run(
                job,
                limits,
                env={"PYTHONUNBUFFERED": "1"},
                wrap_cmd=wrap_cmd,
                preexec=preexec,
            )
        else:
            res = Result(
                status=Status.FAILED,
                rc=1,
                reason=f"lang_unsupported:{job.lang}",
                stdout="",
                stderr=f"language '{job.lang}' is not supported yet",
                duration_s=0.0,
            )

        # Ghi meta có kèm DIAG
        meta = {
            "job_id": job.job_id,
            "status": res.status.value,
            "rc": res.rc,
            "reason": res.reason,
            "duration_s": res.duration_s,
            "limits_applied": limits.__dict__,
            "strategy": settings.sandbox.get("iso_strategy", "none"),
            "planned_cmd": planned_cmd,  # <=== thêm
            "capabilities": caps,  # <=== thêm
        }
        self.storage.save_artifacts(job.job_id, res.stdout, res.stderr, meta)

        status = "FINISHED" if res.rc == 0 and res.status == Status.FINISHED else "FAILED"
        rc = res.rc if status == "FAILED" else 0
        self.db.finalize(job.job_id, status=status, rc=rc, reason=res.reason or None)

    def get_status(self, job_id: str) -> Dict:
        row = self.db.get_job(job_id)
        if not row:
            raise ValueError("job_not_found")
        return {
            "id": row["id"],
            "status": row["status"],
            "exit_code": row["exit_code"] if row["exit_code"] is not None else 0,
            "reason": row["reason"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "entry": row["entry"],
            "lang": row["lang"],
        }

    def get_logs(self, job_id: str) -> Dict[str, str]:
        if not self.db.get_job(job_id):
            raise ValueError("job_not_found")
        out, err = self.storage.read_logs(job_id)
        return {"stdout": out or "", "stderr": err or ""}
