# TODO: implement src/sandbox/runner/rlimits.py
from __future__ import annotations
import resource

def apply_rlimits(cpu_seconds: int, memory_bytes: int, nofile: int) -> None:
    """
    Áp giới hạn ở cấp tiến trình: CPU time, bộ nhớ ảo, số file descriptor.
    Nếu hệ điều hành không hỗ trợ một limit nhất định, Python sẽ raise -> ta để mặc định.
    """
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (nofile, nofile))
    except Exception:
        pass
