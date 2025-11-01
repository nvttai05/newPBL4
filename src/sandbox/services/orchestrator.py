import uuid
from datetime import datetime
from pathlib import Path
from .job_store import Job, JobStatus, JobStore
from .artifact_store import ArtifactStore
from ..executor.base import ExecSpec
from ..executor.ns_chroot import NsChrootExecutor
from ..settings import load_settings
from ..runners.python_runner import PythonRunner

class Orchestrator:
    def __init__(self, store: JobStore):
        self.s = load_settings()
        self.store = store
        self.art = ArtifactStore(self.s.jobs_dir)
        self.exec = NsChrootExecutor(
            self.s.rootfs,
            enable_loopback=self.s.enable_loopback,
            noexec_work=self.s.noexec_work,
            bind_full_etc=self.s.bind_full_etc,
        )

    def submit_python(self, code: str, entry: str="main.py") -> str:
        job_id = uuid.uuid4().hex[:12]
        self.art.write_code(job_id, entry, code)
        self.store.add(Job(
            id=job_id, status=JobStatus.QUEUED, created_at=datetime.utcnow(),
            lang="python", entry=entry
        ))
        return job_id

    def run(self, job_id: str):
        job = self.store.get(job_id); assert job, "job not found"
        job.status = JobStatus.RUNNING; job.started_at = datetime.utcnow(); self.store.update(job)

        workdir = self.art.job_workdir(job_id)
        spec = ExecSpec(
            cmd=PythonRunner().command(workdir / job.entry),
            workdir=workdir, env={}, timeout_s=self.s.default_timeout_s,
        )
        self.exec.prepare(job_id, workdir, getattr(self.s, "limits", {}))
        rc = self.exec.run(job_id, spec)
        job.exit_code = rc; job.finished_at = datetime.utcnow()
        job.status = JobStatus.TIMEOUT if rc == 124 else (JobStatus.FINISHED if rc == 0 else JobStatus.FAILED)
        self.store.update(job)
        self.exec.cleanup(job_id)

    def logs(self, job_id: str) -> dict:
        return self.art.read_logs(job_id)
