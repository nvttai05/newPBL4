from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional

from ..core.models import Job, Limits, Result, Status
from ..core.settings import settings
from ..core.db import DB
from ..core.utils import new_job_id, infer_lang_from_entry
from .storage import LocalFSStorage
from ..runner.python_runner import PythonRunner
from ..runner.go_runner import GoRunner
from ..isolation.isolation import IsolationPipeline, probe_capabilities


class JobService:
    """
    Service chịu trách nhiệm:
      - Tạo job (ghi code ra filesystem, insert DB)
      - Chạy job trong sandbox (isolation + rlimits)
      - Đọc status và logs của job
    """

    def __init__(self) -> None:
        # DB
        self.db = DB(Path("sandbox.db"))

        # FS storage
        self.storage = LocalFSStorage(settings.jobs_dir)

        # Runtimes từ conf/sandbox.yaml
        rt = settings.sandbox.get("runtimes", {})

        # Runners khả dụng, map theo lang
        self.runners = {
            "python": PythonRunner(
                python_bin=rt.get("python", "python3")
            ),
            "go": GoRunner(
                go_bin=rt.get("go", "go")
            ),
            # sau này có thể thêm:
            # "node": NodeRunner(node_bin=rt.get("node", "node")),
            # "bash": BashRunner(...),
        }

        # Isolation pipeline (ns/chroot, cgroups)
        self.iso = IsolationPipeline(
            strategy=settings.sandbox.get("iso_strategy", "none"),
            allow_network=bool(settings.sandbox.get("allow_network", False)),
        )

    def _limits(self) -> Limits:
        lim = settings.limits
        return Limits(
            cpu_seconds=int(lim.get("cpu_seconds", 2)),
            memory_bytes=int(lim.get("memory_bytes", 128 * 1024 * 1024)),
            nofile=int(lim.get("nofile", 64)),
            wall_timeout_seconds=int(lim.get("wall_timeout_seconds", 5)),
        )

    def _normalize_lang(self, entry: str, lang: Optional[str]) -> str:
        # ưu tiên lang truyền vào, nếu không có thì infer từ entry
        normalized = (lang or "").lower().strip()
        if not normalized:
            normalized = infer_lang_from_entry(entry)
        return normalized

    def create_job(self, entry: str, code: str, lang: Optional[str] = None) -> str:
        """
        Tạo job mới:
          - chuẩn hóa lang
          - tạo workspace + ghi code
          - insert DB record
        """
        job_id = new_job_id()
        lang = self._normalize_lang(entry, lang)

        ws = self.storage.create_workspace(job_id)
        script_path = ws / entry
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(code, encoding="utf-8")

        self.db.insert_job(job_id, lang=lang, entry=entry)
        return job_id

    def _build_job_from_row(self, job_id: str, row: Dict) -> Job:
        ws_abs = (settings.jobs_dir / job_id).resolve()
        ws_abs.mkdir(parents=True, exist_ok=True)
        script_abs = ws_abs / row["entry"]
        if not script_abs.exists():
            raise ValueError(f"script_not_found:{script_abs}")

        return Job(
            job_id=job_id,
            lang=row["lang"],
            entry=row["entry"],
            workspace=ws_abs,
            script_path=script_abs,
        )

    def _diag_planned_cmd(self, job: Job, wrap_cmd):
        """
        Tính trước lệnh dự kiến sẽ chạy (chỉ để ghi vào meta cho debug).
        Không ảnh hưởng đến việc thực thi thực tế.
        """
        try:
            if job.lang == "python":
                base_cmd = [self.runners["python"].python_bin, str(job.script_path)]
            elif job.lang == "go":
                base_cmd = [self.runners["go"].go_bin, "run", str(job.script_path)]
            else:
                base_cmd = ["<unsupported_lang>"]

            return wrap_cmd(base_cmd) if wrap_cmd else base_cmd
        except Exception:
            return ["<wrap_cmd_error>"]

    def run_job(self, job_id: str) -> None:
        row = self.db.get_job(job_id)
        if not row:
            raise ValueError("job_not_found")

        # set trạng thái RUNNING
        self.db.set_running(job_id)

        job = self._build_job_from_row(job_id, row)
        limits = self._limits()

        # Xây pipeline isolation
        wrap_cmd, preexec = self.iso.build(job, limits)

        # === DIAG: tính lệnh thực tế + capabilities môi trường ===
        planned_cmd = self._diag_planned_cmd(job, wrap_cmd)
        caps = probe_capabilities(
            allow_network=bool(settings.sandbox.get("allow_network", False)),
            strategy=settings.sandbox.get("iso_strategy", "none"),
        )

        # Chạy runner theo ngôn ngữ
        runner = self.runners.get(job.lang)
        if runner is None:
            res = Result(
                status=Status.FAILED,
                rc=1,
                reason=f"lang_unsupported:{job.lang}",
                stdout="",
                stderr=f"language '{job.lang}' is not supported yet",
                duration_s=0.0,
            )
        else:
            env: Dict[str, str] = {}
            if job.lang == "python":
                env["PYTHONUNBUFFERED"] = "1"

            res = runner.run(
                job,
                limits,
                env=env,
                wrap_cmd=wrap_cmd,
                preexec=preexec,
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
            "planned_cmd": planned_cmd,
            "capabilities": caps,
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
