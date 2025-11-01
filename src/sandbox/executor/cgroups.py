# src/sandbox/executor/cgroups.py
from __future__ import annotations
from pathlib import Path
import os, time

CGROOT = Path("/sys/fs/cgroup")

def ensure_v2():
    assert (CGROOT / "cgroup.controllers").exists(), "cgroup v2 is required"

def _self_cgroup_base() -> Path:
    # unified v2: '0::/<relative>'
    with open("/proc/self/cgroup") as f:
        rel = ""
        for line in f:
            if line.startswith("0::/"):
                rel = line.split("::", 1)[1].strip()
                break
    return (CGROOT / rel.lstrip("/")).resolve()

def _env_base() -> Path | None:
    val = os.environ.get("SBX_CGROUP_BASE")
    if not val:
        return None
    base = Path(val)
    if not str(base).startswith(str(CGROOT)):
        raise ValueError(f"SBX_CGROUP_BASE must start with {CGROOT}, got {base}")
    return base

def get_sbx_base() -> Path:
    # Ưu tiên SBX_CGROUP_BASE (ví dụ …/sandbox.service/sbx), nếu không có thì dùng cgroup hiện tại + /sbx
    return _env_base() or (_self_cgroup_base() / "sbx")

def _enable_controllers(node: Path):
    """Bật controller cho children ở node (yêu cầu node rỗng theo cgroup v2)."""
    cnt_file = node / "cgroup.controllers"
    if not cnt_file.exists():
        return
    have = set(cnt_file.read_text().split())
    want = [f"+{c}" for c in ("memory", "pids", "cpu") if c in have]
    if not want:
        return
    # Node phải rỗng trước khi bật subtree_control
    if (node / "cgroup.procs").read_text().strip():
        # báo lỗi rõ ràng để phía gọi biết phải move PID/stop service trước
        raise PermissionError(f"{node} has PIDs; cannot set subtree_control")
    (node / "cgroup.subtree_control").write_text(" ".join(want))

def create_leaf(job_id: str) -> Path:
    base = get_sbx_base()
    base.mkdir(parents=True, exist_ok=True)
    # Đảm bảo base có controller cho con
    try:
        _enable_controllers(base)
    except PermissionError:
        # để lỗi nổi bọt ra API thay vì EPERM mập mờ khi ghi memory.max ở leaf
        raise
    leaf = base / job_id
    leaf.mkdir(parents=True, exist_ok=True)
    return leaf

def set_limits(leaf: Path, limits: dict):
    """
    Hỗ trợ conf/limits.yaml dạng:
      memory: {max: <bytes|max>, swap_max: <bytes|max>, oom_group: <bool>}
      pids:   {max: <n|max>}
      cpu:    {max: "<quota> <period>"}  # ví dụ "10000 10000"
    """
    mem = (limits.get("memory") or {}).get("max")
    if mem is not None:
        (leaf / "memory.max").write_text(str(mem))
    swap = (limits.get("memory") or {}).get("swap_max")
    if swap is not None:
        (leaf / "memory.swap.max").write_text(str(swap))
    oomg = (limits.get("memory") or {}).get("oom_group")
    if oomg is not None:
        (leaf / "memory.oom.group").write_text("1" if oomg else "0")
    pids = (limits.get("pids") or {}).get("max")
    if pids is not None:
        (leaf / "pids.max").write_text(str(pids))
    cpu = (limits.get("cpu") or {}).get("max")
    if cpu is not None:
        (leaf / "cpu.max").write_text(str(cpu))

def attach(leaf: Path, pid: int):
    (leaf / "cgroup.procs").write_text(str(pid))

def read_metrics(leaf: Path) -> dict:
    out: dict[str, str] = {}
    for name in ("memory.current", "memory.events", "cpu.stat", "pids.current"):
        p = leaf / name
        if p.exists():
            out[name] = p.read_text().strip()
    return out

def teardown(leaf: Path):
    # leaf phải rỗng, best-effort retry
    for _ in range(5):
        try:
            leaf.rmdir()
            return
        except OSError:
            time.sleep(0.1)
