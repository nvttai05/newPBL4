from pathlib import Path

class ArtifactStore:
    def __init__(self, jobs_dir: Path):
        self.jobs_dir = jobs_dir

    def job_workdir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id / "work"

    def write_code(self, job_id: str, entry: str, code: str):
        wd = self.job_workdir(job_id); wd.mkdir(parents=True, exist_ok=True)
        (wd / entry).write_text(code, encoding="utf-8")

    def read_logs(self, job_id: str) -> dict:
        wd = self.job_workdir(job_id)
        out = (wd/"stdout.log").read_text() if (wd/"stdout.log").exists() else ""
        err = (wd/"stderr.log").read_text() if (wd/"stderr.log").exists() else ""
        return {"stdout": out, "stderr": err}
