# src/sandbox/seccomp/seccomp_helper.py
from __future__ import annotations
import sys
from pathlib import Path
import json

try:
    import yaml  # optional, but convenient
except Exception:
    yaml = None
# src/sandbox/seccomp/seccomp_helper.py
try:
    import pyseccomp as sc   # bản này hay gặp trên PyPI
    SC_BINDING = "pyseccomp"
except ModuleNotFoundError:
    try:
        import seccomp as sc  # bản từ python-libseccomp
        SC_BINDING = "seccomp"
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "No libseccomp Python binding found. Install one of:\n"
            "  pip install pyseccomp   (requires libseccomp-dev)\n"
            "  or pip install seccomp"
        ) from e

# Map string action -> pyseccomp action
def _action_from_string(s: str, errno_val: int):
    s = (s or "ERRNO").upper()
    if s == "ALLOW":
        return sc.ALLOW
    if s == "KILL_PROCESS":
        return sc.KILL_PROCESS
    if s == "KILL":
        return sc.KILL
    if s == "TRAP":
        return sc.TRAP
    if s == "LOG":
        # LOG không phải lúc nào kernel cũng hỗ trợ, nhưng pyseccomp có constant
        return sc.LOG
    if s == "ERRNO":
        return sc.ERRNO(errno_val)
    # mặc định EPERM
    return sc.ERRNO(errno_val)

def _load_config(cfg_path: str):
    p = Path(cfg_path)
    if not p.exists():
        raise FileNotFoundError(cfg_path)
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text())
    # yaml
    if yaml is None:
        raise RuntimeError("YAML not available. Install PyYAML or use JSON policy.")
    return yaml.safe_load(p.read_text())

def create_seccomp_from_config(cfg_path: str) -> bool:
    cfg = _load_config(cfg_path)
    default_action = cfg.get("default_action", "ERRNO")
    errno_val = int(cfg.get("errno", 1))
    allow = [x.strip().rstrip(";") for x in (cfg.get("allow") or [])]
    block = [x.strip().rstrip(";") for x in (cfg.get("block") or [])]

    filt = sc.SyscallFilter(_action_from_string(default_action, errno_val))

    # ALLOW rules
    for name in allow:
        try:
            filt.add_rule(sc.ALLOW, name)
        except Exception as e:
            print(f"[seccomp] WARN allow {name}: {e}", file=sys.stderr)

    # BLOCK rules: khi default_action = ERRNO, block mạnh hơn ta để KILL;
    # nếu default_action = KILL_PROCESS, bạn có thể đổi block thành ERRNO để "hạ nhẹ".
    block_action = sc.KILL if default_action.upper() == "ERRNO" else sc.ERRNO(errno_val)
    for name in block:
        try:
            filt.add_rule(block_action, name)
        except Exception as e:
            print(f"[seccomp] WARN block {name}: {e}", file=sys.stderr)

    filt.load()
    return True

def create_seccomp(default_errno: int = 1, extra_allow=None, extra_block=None) -> bool:
    """
    Fallback nhanh nếu không dùng file cấu hình — permissive: ERRNO(EPERM) + allowlist tối thiểu.
    """
    base_allow = [
        "read","write","close","fstat","lseek","mmap","mprotect","munmap","brk",
        "rt_sigreturn","rt_sigaction","sigaltstack","rt_sigprocmask",
        "clock_gettime","nanosleep","getrandom",
        "exit","exit_group","futex","madvise","prlimit64","arch_prctl",
        "set_tid_address","set_robust_list","getpid","getppid","getuid",
        "geteuid","getgid","getegid","uname",
        "openat","access","stat","fstat","readlink","getdents64","fcntl",
        "dup","dup2","getcwd","statfs","mremap","getrlimit",
        "epoll_create1","epoll_ctl","epoll_wait","poll"
    ]
    allow = list(dict.fromkeys((extra_allow or []) + base_allow))
    filt = sc.SyscallFilter(sc.ERRNO(default_errno))
    for n in allow:
        try:
            filt.add_rule(sc.ALLOW, n)
        except Exception as e:
            print(f"[seccomp] WARN allow {n}: {e}", file=sys.stderr)
    for n in (extra_block or []):
        try:
            filt.add_rule(sc.KILL, n)
        except Exception as e:
            print(f"[seccomp] WARN block {n}: {e}", file=sys.stderr)
    filt.load()
    return True
