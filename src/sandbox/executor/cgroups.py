# src/sandbox/executor/cgroups.py
from __future__ import annotations
from pathlib import Path
import os, time
import subprocess  # NEW

USE_CGROUP = os.getenv("USE_CGROUP", "1") == "1"

CGROOT = Path("/sys/fs/cgroup")
# --- NEW: base path cố định cho service ---
CG_SERVICE_BASE = Path("/sys/fs/cgroup/system.slice/sandbox.service")
CG_SBX_BASE     = CG_SERVICE_BASE / "sbx"

def _write_then_check(p: Path, val: str | int):
    val = str(val)
    p.write_text(val)
    back = p.read_text().strip()
    if back != val:
        # In/raise để biết chính xác kernel đã nhận gì
        raise RuntimeError(f"[cgroup] write {p}='{val}' but read-back='{back}'")

# def _ensure_cgroup_job(job_id: str) -> Path:
#     """
#     Gọi script mkjob để tạo /system.slice/sandbox.service/sbx/<job_id> và cấp ACL
#     (sudoers đã cho phép chạy không cần mật khẩu).
#     """
#     env = os.environ.copy()  # để SBX_USER từ unit (nếu có) truyền xuống
#     subprocess.run(
#         ["sudo", "/usr/local/bin/sbx-cg-mkjob.sh", job_id],
#         check=True,
#         env=env,
#     )
#     return CG_SBX_BASE / job_id
def _ensure_cgroup_job(job_id: str) -> Path:
    """
    Service chạy root => tạo leaf trực tiếp, không cần sudo/script/ACL.
    """
    leaf = CG_SBX_BASE / job_id
    leaf.mkdir(parents=True, exist_ok=True)
    return leaf



def ensure_v2():
    assert (CGROOT / "cgroup.controllers").exists(), "cgroup v2 is required"

def assert_controllers_on():
    # Cho phép disable kiểm tra cgroup bằng biến môi trường
    if os.getenv("USE_CGROUP", "1") == "0":
        print("[WARN] Skipping cgroup controller check (USE_CGROUP=0)")
        return

    base = Path("/sys/fs/cgroup/system.slice/sandbox.service")
    need = {"cpu", "memory", "pids"}

    svc_ctrl_file = base / "cgroup.subtree_control"
    sbx_ctrl_file = base / "sbx" / "cgroup.subtree_control"

    if not svc_ctrl_file.exists() or not sbx_ctrl_file.exists():
        print("[WARN] cgroup files not found, skipping")
        return

    svc = set(svc_ctrl_file.read_text().split())
    sbx = set(sbx_ctrl_file.read_text().split())

    if not need.issubset(svc) or not need.issubset(sbx):
        print(f"[WARN] cgroup controllers not fully enabled: svc={svc}, sbx={sbx}")
        # không raise nữa
        return


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
    # Ưu tiên SBX_CGROUP_BASE (ví dụ …/sandbox.service/sbx)
    env_base = _env_base()
    if env_base:
        return env_base

    # Không có env: suy từ /proc/self/cgroup. Nếu đang ở payload/, nhảy về service/ rồi vào sbx/
    self_base = _self_cgroup_base()  # ví dụ: /sys/fs/cgroup/system.slice/sandbox.service/payload
    parts = self_base.parts
    try:
        # Tìm cụm .../system.slice/sandbox.service ở path hiện tại
        idx = parts.index("system.slice")
        if idx + 1 < len(parts) and parts[idx + 1] == "sandbox.service":
            # Lấy .../system.slice/sandbox.service, bỏ payload đi nếu có
            service_base = Path("/".join(parts[: idx + 2]))  # /sys/fs/cgroup/system.slice/sandbox.service
            return service_base / "sbx"
    except ValueError:
        pass

    # Fallback cũ: /<self>/sbx
    return self_base / "sbx"


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
    if not USE_CGROUP:
        print(f"[WARN] Skipping create_leaf for {job_id} (USE_CGROUP=0)")
        # chỉ tạo folder giả trong /tmp để code phía trên không lỗi
        fake_leaf = Path(f"/tmp/fake_cgroup_{job_id}")
        fake_leaf.mkdir(parents=True, exist_ok=True)
        return fake_leaf

    ensure_v2()
    assert_controllers_on()

    base = get_sbx_base()
    base.mkdir(parents=True, exist_ok=True)

    try:
        _enable_controllers(base)
    except PermissionError:
        raise

    leaf = _ensure_cgroup_job(job_id)
    leaf.mkdir(parents=True, exist_ok=True)
    return leaf



def set_limits(leaf: Path, limits: dict):
    """
    Hỗ trợ conf/limits.yaml dạng:
      memory: {max: <bytes|max>, swap_max: <bytes|max>, oom_group: <bool>}
      pids:   {max: <n|max>}
      cpu:    {max: "<quota> <period>"}  # ví dụ "10000 10000" hoặc "max 100000"
    """
    # ---- memory ----
    if os.getenv("USE_CGROUP", "1") == "0":
        print(f"[WARN] Skipping set_limits for {leaf} (USE_CGROUP=0)")
        return
    mem_cfg = (limits.get("memory") or {})
    if "max" in mem_cfg:
        _write_then_check(leaf / "memory.max", mem_cfg["max"])
    if "swap_max" in mem_cfg:
        try:
            _write_then_check(leaf / "memory.swap.max", mem_cfg["swap_max"])
        except FileNotFoundError:
            # hệ thống không bật memcg swap: bỏ qua
            pass
    if "oom_group" in mem_cfg:
        _write_then_check(leaf / "memory.oom.group", 1 if mem_cfg["oom_group"] else 0)

    # ---- pids ----
    pids_cfg = (limits.get("pids") or {})
    if "max" in pids_cfg:
        _write_then_check(leaf / "pids.max", pids_cfg["max"])

    # ---- cpu ----
    cpu_cfg = (limits.get("cpu") or {})
    if "max" in cpu_cfg:
        # cpu.max cho phép chuỗi "quota period" (vd: "10000 10000") hoặc "max 100000"
        (leaf / "cpu.max").write_text(str(cpu_cfg["max"]))


def attach(leaf: Path, pid: int):
    if not USE_CGROUP:
        print(f"[WARN] Skipping attach for {pid} (USE_CGROUP=0)")
        return

    try:
        (leaf / "cgroup.procs").write_text(str(pid))
    except Exception as e:
        import traceback
        print(f"[DEBUG attach] leaf={leaf} pid={pid} err={e}")
        print(f"[DEBUG attach] exists? {(leaf / 'cgroup.procs').exists()}")
        traceback.print_exc()
        raise

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
