# src/sandbox/executor/ns_chroot.py
from __future__ import annotations
import os, sys, shlex, signal, subprocess
from pathlib import Path

from .base import ExecSpec, Executor
from .cgroups import ensure_v2, create_leaf, set_limits, attach, teardown
from ..settings import load_settings  # cần có seccomp_enabled, seccomp_policy

class NsChrootExecutor(Executor):
    """
    Hai chế độ:
      - HOST mode (mặc định): chạy trên host, áp cgroup + (nếu bật) seccomp bằng chính .venv của service.
      - CHROOT mode: chỉ khi rootfs sẵn sàng; vẫn dùng seccomp trên host (không cần pyseccomp trong rootfs).
    """

    def __init__(self, rootfs: Path, *, enable_loopback: bool=False, noexec_work: bool=False, bind_full_etc: bool=False):
        self.rootfs = rootfs
        self.enable_loopback = enable_loopback
        self.noexec_work = noexec_work
        self.bind_full_etc = bind_full_etc

        self.leaf: Path | None = None
        self._rlimit_mem_bytes: int | None = None
        self._rlimit_nproc: int | None = None

        # Luôn dùng interpreter của service (.venv)
        self._python = sys.executable

    # ------------ lifecycle ------------

    def prepare(self, job_id: str, workdir: Path, limits: dict):
        ensure_v2()
        self.leaf = create_leaf(job_id)
        set_limits(self.leaf, limits)

        # KHÔNG bật RLIMIT_AS lúc debug để tránh fork lỗi sớm
        mem = (limits.get("memory") or {}).get("max")
        nproc = (limits.get("pids") or {}).get("max")
        self._rlimit_mem_bytes = None  # int(mem) if mem and str(mem).isdigit() else None
        # self._rlimit_nproc = int(nproc) if (nproc and str(nproc).isdigit()) else None
        self._rlimit_nproc=None
        workdir.mkdir(parents=True, exist_ok=True)

        # Chuẩn bị secwrap nếu bật
        s = load_settings()
        if getattr(s, "seccomp_enabled", False):
            # chép _secwrap.py + seccomp_helper.py + policy vào workdir
            import sandbox.seccomp.secwrap as _secwrap
            import sandbox.seccomp.seccomp_helper as _helper
            (workdir / "_secwrap.py").write_text(Path(_secwrap.__file__).read_text(encoding="utf-8"), encoding="utf-8")
            (workdir / "seccomp_helper.py").write_text(Path(_helper.__file__).read_text(encoding="utf-8"), encoding="utf-8")
            policy_host = Path(getattr(s, "seccomp_policy"))
            (workdir / "seccomp.yaml").write_text(policy_host.read_text(encoding="utf-8"), encoding="utf-8")

    @staticmethod
    def _preexec_set_rlimits(mem_bytes: int | None, nproc: int | None):
        def _fn():
            import resource, os
            # >>> TẠM THỜI COMMENT 3 DÒNG DƯỚI <<<
            # if mem_bytes:
            #     headroom = 16 * 1024 * 1024
            #     cap = max(64 * 1024 * 1024, mem_bytes - headroom)
            #     resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

            # if nproc:
            #     resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
            resource.setrlimit(resource.RLIMIT_STACK, (8 * 1024 * 1024, 8 * 1024 * 1024))
            os.setsid()

        return _fn

    def _rootfs_ready(self) -> bool:
        return (self.rootfs / "bin/bash").exists()

    # ---------- command builders ----------

    def _host_argv(self, spec: ExecSpec) -> list[str]:
        s = load_settings()
        if getattr(s, "seccomp_enabled", False):
            return [self._python, str(spec.workdir / "_secwrap.py"),
                    "--config", str(spec.workdir / "seccomp.yaml"), "--", *spec.cmd]
        # Không seccomp: chạy trực tiếp command, không qua bash
        return list(spec.cmd)

    def _chroot_argv(self, spec: ExecSpec) -> list[str]:
        """
        Vẫn mount/chroot để cô lập FS, nhưng seccomp được APPLY TRƯỚC ở host (vì dùng .venv).
        Cách này: chạy unshare+mount+chroot bằng bash, còn code user chạy qua _secwrap.py (host .venv).
        """
        mnt_work = str(self.rootfs / "work")
        mnt_proc = str(self.rootfs / "proc")

        # Lệnh bên trong chroot chạy: python (từ host .venv) đã không dùng trong chroot.
        # Ta sẽ chroot chỉ để cô lập FS, nhưng chuỗi chạy cuối cùng vẫn là: cd /work && <user cmd>
        # => Ở đây ta pass nguyên "cd /work && <cmd>" làm payload cho chroot bash.
        inner = " ".join(map(shlex.quote, spec.cmd))
        remount_flags = "noexec,nosuid,nodev" if self.noexec_work else "defaults"

        shell = (
            "set -e;"
            f"mkdir -p '{mnt_work}' '{mnt_proc}';"
            f"mount --bind '{spec.workdir}' '{mnt_work}';"
            f"mount -t proc proc '{mnt_proc}';"
            f"mount -o remount,bind,{remount_flags} '{mnt_work}';"
            f"chroot '{self.rootfs}' /bin/bash --noprofile --norc -c 'cd /work && {inner}';"
            "rc=$?;"
            f"umount '{mnt_proc}' || true;"
            f"umount '{mnt_work}' || true;"
            "exit $rc"
        )
        return [
            "unshare", "--mount", "--uts", "--ipc", "--pid", "--net",
            "--user", "--map-root-user",
            "env", "-i", "HOME=/root", "PATH=/usr/sbin:/usr/bin:/bin", "DEBUGINFOD_URLS=",
            "bash", "--noprofile", "--norc", "-c", shell
        ]

    # ---------- run ----------

    def run(self, job_id: str, spec: ExecSpec) -> int:
        # Mặc định: host mode (ổn định nhất). Nếu rootfs đủ mới dùng chroot argv.
        argv = self._host_argv(spec) if not self._rootfs_ready() else self._chroot_argv(spec)

        # Nếu bật seccomp, ensure argv là _secwrap.py -- ... để chặn ngay từ đầu
        s = load_settings()
        if getattr(s, "seccomp_enabled", False) and argv and "_secwrap.py" not in " ".join(argv):
            argv = [self._python, str(spec.workdir / "_secwrap.py"), "--config", str(spec.workdir / "seccomp.yaml"), "--"] + argv

        p = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(spec.workdir),
            env=spec.env or {},
            preexec_fn=self._preexec_set_rlimits(self._rlimit_mem_bytes, self._rlimit_nproc),
        )

        # gắn vào cgroup leaf NGAY sau khi fork
        attach(self.leaf, p.pid)

        try:
            out, err = p.communicate(timeout=spec.timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            try:
                out, err = p.communicate(timeout=2)
            except Exception:
                out, err = "", "TIMEOUT\n"
            (spec.workdir / "stdout.log").write_text(out or "")
            (spec.workdir / "stderr.log").write_text(
                (err or "") + ("TIMEOUT\n" if "TIMEOUT" not in (err or "") else ""))
            return 124

        (spec.workdir / "stdout.log").write_text(out or "")
        (spec.workdir / "stderr.log").write_text(err or "")
        return p.returncode

    def cleanup(self, job_id: str):
        if self.leaf:
            teardown(self.leaf)
            self.leaf = None
