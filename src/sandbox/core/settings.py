# TODO: implement src/sandbox/core/settings.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import os
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Load cấu hình từ conf/*.yaml + cho phép override bằng SBX_* env."""
    root_dir: Path = Path.cwd()

    # paths
    limits_file: Path = Path("conf/limits.yaml")
    sandbox_file: Path = Path("conf/sandbox.yaml")
    seccomp_policy: Path = Path("conf/seccomp.min.yaml")

    # dynamic
    jobs_dir: Path = Path("jobs")
    limits: Dict[str, Any] = {}
    sandbox: Dict[str, Any] = {}

    model_config = SettingsConfigDict(env_prefix="SBX_", extra="ignore")

    def load(self) -> None:
        with open(self.limits_file, "r", encoding="utf-8") as f:
            self.limits = yaml.safe_load(f) or {}
        with open(self.sandbox_file, "r", encoding="utf-8") as f:
            self.sandbox = yaml.safe_load(f) or {}

        # normalize
        self.jobs_dir = Path(self.sandbox.get("jobs_dir", "jobs"))

        # allow env overrides (optional)
        if os.getenv("SBX_JOBS_DIR"):
            self.jobs_dir = Path(os.getenv("SBX_JOBS_DIR"))  # type: ignore
        if os.getenv("SBX_ISO_STRATEGY"):
            self.sandbox["iso_strategy"] = os.getenv("SBX_ISO_STRATEGY")

settings = Settings()
settings.load()
