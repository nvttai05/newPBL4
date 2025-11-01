from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- core paths / flags ----
    rootfs: Path = Path("/srv/sbx/rootfs")
    jobs_dir: Path = Path("/srv/sbx/jobs")

    default_timeout_s: int = 8
    enable_loopback: bool = False
    noexec_work: bool = True
    bind_full_etc: bool = False

    # ---- config files ----
    limits_file: Path = Path("conf/limits.yaml")

    # ---- runtime merged limits (read from YAML) ----
    limits: Dict[str, Any] = {}  # <- thêm field này để Pydantic không báo lỗi

    # env prefix SBX_*
    model_config = SettingsConfigDict(env_prefix="SBX_", extra="ignore")

    # ---- seccomp ----
    seccomp_enabled: bool = False
    seccomp_policy: Path = Path("conf/seccomp.min.yaml")


def load_settings() -> Settings:
    # load base from env (SBX_*), sau đó merge YAML nếu có
    s = Settings()

    # 1) sandbox.yaml (đường dẫn có thể override bằng env SANDBOX_CONF)
    sbx_yaml = os.environ.get("SANDBOX_CONF", "conf/sandbox.yaml")
    p = Path(sbx_yaml)
    if p.exists():
        d = yaml.safe_load(p.read_text()) or {}
        defs = d.get("defaults", {}) if isinstance(d, dict) else {}
        # Lấy block seccomp (nếu có)
        sec = defs.get("seccomp", {}) if isinstance(defs, dict) else {}

        # dùng model_copy(update=...) cho đúng kiểu pydantic v2
        s = s.model_copy(
            update={
                "rootfs": Path(d.get("rootfs", s.rootfs)),
                "jobs_dir": Path(d.get("jobs_dir", s.jobs_dir)),
                "default_timeout_s": int(defs.get("timeout_s", s.default_timeout_s)),
                "enable_loopback": bool(defs.get("enable_loopback", s.enable_loopback)),
                "noexec_work": bool(defs.get("noexec_work", s.noexec_work)),
                "bind_full_etc": bool(defs.get("bind_full_etc", s.bind_full_etc)),
                # --- NEW: seccomp (đọc từ defaults.seccomp.*) ---
                "seccomp_enabled": bool(sec.get("enabled", s.seccomp_enabled)),
                "seccomp_policy": Path(sec.get("policy", s.seccomp_policy)),
            }
        )

    # 2) limits.yaml
    limits: Dict[str, Any] = {}
    if s.limits_file.exists():
        limits = yaml.safe_load(s.limits_file.read_text()) or {}
    # cập nhật lại settings với trường limits
    s = s.model_copy(update={"limits": limits})

    return s
