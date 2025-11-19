# TODO: implement src/sandbox/isolation/isolation.py
from __future__ import annotations
from typing import List, Tuple, Callable, Optional
from pathlib import Path
# thay vì: from sandbox.core.models import Job, Limits
from ..core.models import Job, Limits
from .ns_chroot import wrap_with_ns_chroot
from .cgroups import wrap_with_cgroups
from .seccomp import make_seccomp_preexec

from .ns_chroot import wrap_with_ns_chroot
from .cgroups import wrap_with_cgroups
from .seccomp import make_seccomp_preexec
import shutil, os

class IsolationPipeline:
    def __init__(self, strategy: str, allow_network: bool):
        self.strategy = (strategy or "none").lower()
        self.allow_network = allow_network

    def build(self, job: Job, limits: Limits):
        def composer(cmd: List[str]) -> List[str]:
            out = cmd
            if "ns_chroot" in self.strategy:
                out = wrap_with_ns_chroot(out, job, self.allow_network)
            if "cgroups" in self.strategy:
                out = wrap_with_cgroups(out, limits)
            return out

        # KHÔNG còn preexec seccomp ở đây
        return composer, None


    # ... giữ nguyên phần trên

def probe_capabilities(allow_network: bool, strategy: str) -> dict:
        """Trả về thông tin môi trường để debug isolation."""
        return {
            "strategy": strategy,
            "allow_network": allow_network,
            "euid": os.geteuid() if hasattr(os, "geteuid") else None,
            "has_unshare": bool(shutil.which("unshare")),
            "has_chroot": bool(shutil.which("chroot")),
            "has_systemd_run": bool(shutil.which("systemd-run")),
            "has_sh": bool(shutil.which("sh") or shutil.which("bash")),
            "seccomp_policy_path": str(getattr(Path, "__call__", lambda x: x)(Path(".")) and str(Path(".")))
            # dummy to keep pure
        }

