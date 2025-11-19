# TODO: implement src/sandbox/services/storage.py
from __future__ import annotations
from pathlib import Path
from typing import Tuple
import json


class LocalFSStorage:
    """
    Lưu trữ artifact/logs trên filesystem theo cấu trúc:
      jobs/<job_id>/
        ├─ <entry>         (file code user gửi)
        ├─ stdout.txt
        ├─ stderr.txt
        └─ meta.json       (tổng hợp rc/status/reason/limits...)
    """

    def __init__(self, jobs_dir: Path):
        # đảm bảo là absolute path
        self.jobs_dir = jobs_dir if jobs_dir.is_absolute() else jobs_dir.resolve()
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, job_id: str) -> Path:
        p = self.jobs_dir / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p  # -> ABS path vì self.jobs_dir là ABS

    def save_artifacts(self, job_id: str, stdout: str, stderr: str, meta: dict) -> None:
        """
        Ghi stdout/stderr/meta ra file.
        """
        p = self.jobs_dir / job_id
        (p / "stdout.txt").write_text(stdout or "", encoding="utf-8")
        (p / "stderr.txt").write_text(stderr or "", encoding="utf-8")
        (p / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def read_logs(self, job_id: str) -> Tuple[str, str]:
        """
        Đọc lại stdout/stderr (dùng cho GET /jobs/{id}/logs).
        """
        p = self.jobs_dir / job_id
        out = (p / "stdout.txt").read_text(encoding="utf-8") if (p / "stdout.txt").exists() else ""
        err = (p / "stderr.txt").read_text(encoding="utf-8") if (p / "stderr.txt").exists() else ""
        return out, err
