# src/sandbox/executor/ns_chroot.py
import os, subprocess, signal
import shlex
from pathlib import Path
from .base import ExecSpec, Executor
from .cgroups import ensure_v2, create_leaf, set_limits, attach, teardown
from ..settings import load_settings  # <- lấy cấu hình (seccomp_enabled, seccomp_policy)

class NsChrootExecutor(Executor):
    def __init__(self, rootfs: Path, *, enable_loopback: bool, noexec_work: bool, bind_full_etc: bool):
        self.rootfs = rootfs
        self.enable_loopback = enable_loopback
        self.noexec_work = noexec_work
        self.bind_full_etc = bind_full_etc
        self.leaf = None

    def prepare(self, job_id: str, workdir: Path, limits: dict):
        ensure_v2()
        self.leaf = create_leaf(job_id)
        set_limits(self.leaf, limits)
        workdir.mkdir(parents=True, exist_ok=True)

        # --- NEW: copy secwrap + policy vào workdir ---
        s = load_settings()  # 's' = Settings (sửa lỗi bạn gặp)
        if s.seccomp_enabled:
            # copy _secwrap.py vào work/
            import sandbox.seccomp.secwrap as _secwrap
            secwrap_src = Path(_secwrap.__file__)
            (workdir / "_secwrap.py").write_text(secwrap_src.read_text(), encoding="utf-8")

            # copy policy YAML vào work/
            policy_host = Path(s.seccomp_policy)
            (workdir / "seccomp.yaml").write_text(policy_host.read_text(), encoding="utf-8")

    def _rootfs_ready(self) -> bool:
        return (self.rootfs / "bin/bash").exists()

    def _build_host_cmd(self, spec: ExecSpec) -> list[str]:
        # Fallback khi rootfs chưa đủ: chạy trên host (có cgroup limit, KHÔNG seccomp)
        return ["bash","-lc", f"cd {spec.workdir} && {' '.join(spec.cmd)}"]

    def _build_chroot_cmd(self, spec: ExecSpec) -> list[str]:
        # Bind mount workdir -> /work trong rootfs, mount /proc, chroot rồi chạy entry
        mnt_work = str(self.rootfs / "work")
        mnt_proc = str(self.rootfs / "proc")

        # --- BỌC SECWRAP Ở BÊN TRONG CHROOT ---
        s = load_settings()
        if s.seccomp_enabled:
            inside_argv = [
                "/usr/bin/python3", "/work/_secwrap.py",
                "--config", "/work/seccomp.yaml", "--",
            ] + spec.cmd[:]
        else:
            inside_argv = spec.cmd[:]

        # Quote an toàn để nhét vào bash -lc '...'
        cmd_inside = " ".join(shlex.quote(x) for x in inside_argv)

        remount_flags = "noexec,nosuid,nodev" if self.noexec_work else "defaults"

        shell = (
            "set -e;"
            f"mkdir -p '{mnt_work}' '{mnt_proc}';"
            f"mount --bind '{spec.workdir}' '{mnt_work}';"
            f"mount -t proc proc '{mnt_proc}';"
            f"mount -o remount,bind,{remount_flags} '{mnt_work}';"
            f"chroot '{self.rootfs}' bash -lc 'cd /work && {cmd_inside}';"
            "rc=$?;"
            f"umount '{mnt_proc}' || true;"
            f"umount '{mnt_work}' || true;"
            "exit $rc"
        )
        net_args = ["--net"]
        return [
            "unshare","--mount","--uts","--ipc","--pid",*net_args,
            "--user","--map-root-user",
            "bash","-lc", shell
        ]

    def run(self, job_id: str, spec: ExecSpec) -> int:
        cmd = self._build_chroot_cmd(spec) if self._rootfs_ready() else self._build_host_cmd(spec)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        attach(self.leaf, p.pid)
        try:
            out, err = p.communicate(timeout=spec.timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            (spec.workdir/"stderr.log").write_text("TIMEOUT\n")
            return 124
        (spec.workdir/"stdout.log").write_text(out or "")
        (spec.workdir/"stderr.log").write_text(err or "")
        return p.returncode

    def cleanup(self, job_id: str):
        if self.leaf:
            teardown(self.leaf)
            self.leaf = None
