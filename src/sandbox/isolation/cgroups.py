# TODO: implement src/sandbox/isolation/cgroups.py
from __future__ import annotations
from typing import List
import shutil

def wrap_with_cgroups(cmd: List[str], limits) -> List[str]:
    """
    Ưu tiên systemd-run --scope để áp MemoryMax/CPUQuota.
    Nếu không có systemd-run (container tối giản, WSL...), trả về cmd gốc (fallback).
    """
    sdrun = shutil.which("systemd-run")
    if not sdrun:
        return cmd

    # CPUQuota=100% cho 1 vCPU; muốn siết hơn có thể chỉnh về 50%...
    # MemoryMax lấy từ limits.memory_bytes
    return [
        sdrun, "--scope",
        "-p", f"MemoryMax={limits.memory_bytes}",
        "-p", "CPUQuota=100%",
        "--"
    ] + cmd
