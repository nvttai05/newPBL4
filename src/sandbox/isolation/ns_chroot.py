# TODO: implement src/sandbox/isolation/ns_chroot.py
from __future__ import annotations
from typing import List
import shutil, os

def wrap_with_ns_chroot(cmd: List[str], job, allow_network: bool) -> List[str]:
    """
    Best-effort: tách user+mount namespace, KHÔNG chroot (tránh thiếu runtime).
    - Không dùng --net nếu không chạy root (đa số máy user không tạo net ns được).
    - Dùng đường dẫn ABS để không bị systemd-run làm lệch working dir.
    """
    unshare = shutil.which("unshare")
    if not unshare:
        return cmd  # fallback

    sh = shutil.which("sh") or "/bin/sh"
    flags = ["--user", "--mount", "--map-root-user", "--pid", "--fork"]

    use_net = (allow_network is False) and (os.geteuid() == 0)
    if use_net:
        flags += ["--net"]

    ws_abs = os.path.abspath(str(job.workspace))
    inner = f'cd "{ws_abs}" && ' + " ".join(cmd)
    return [unshare] + flags + [sh, "-c", inner]
