from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import Field
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
    # 0) Nạp base từ env SBX_*
    s = Settings()

    # 1) Đọc conf/sandbox.yaml (hoặc SANDBOX_CONF)
    sbx_yaml = os.environ.get("SANDBOX_CONF", "conf/sandbox.yaml")
    try:
        with open(sbx_yaml, "r") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        defaults = {}

    # block seccomp trong defaults
    sec = defaults.get("seccomp") or {}
    if not isinstance(sec, dict):
        sec = {}

    # 2) Merge vào Settings (dùng đúng kiểu Path/bool/int)
    s = s.model_copy(
        update={
            "rootfs": Path(str(data.get("rootfs", s.rootfs))),
            "jobs_dir": Path(str(data.get("jobs_dir", s.jobs_dir))),
            "default_timeout_s": int(defaults.get("timeout_s", s.default_timeout_s)),
            "enable_loopback": bool(defaults.get("enable_loopback", s.enable_loopback)),
            "noexec_work": bool(defaults.get("noexec_work", s.noexec_work)),
            "bind_full_etc": bool(defaults.get("bind_full_etc", s.bind_full_etc)),
            "seccomp_enabled": bool(sec.get("enabled", s.seccomp_enabled)),
            "seccomp_policy": Path(str(sec.get("policy", s.seccomp_policy))),
        }
    )

    # 3) Đọc conf/limits.yaml (tùy chọn)
    limits: Dict[str, Any] = {}
    try:
        if s.limits_file.exists():
            limits_raw = yaml.safe_load(s.limits_file.read_text()) or {}
            if isinstance(limits_raw, dict):
                limits = limits_raw
    except Exception:
        # Không làm app sập vì limits lỗi — giữ mặc định rỗng
        limits = {}

    s = s.model_copy(update={"limits": limits})
    return s

