# src/sandbox/seccomp/secwrap.py
from __future__ import annotations
import os, sys, ctypes
from pathlib import Path
from .seccomp_helper import create_seccomp_from_config, create_seccomp

PR_SET_NO_NEW_PRIVS = 38
libc = ctypes.CDLL(None, use_errno=True)

def set_no_new_privs():
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        e = ctypes.get_errno()
        raise OSError(e, "prctl(PR_SET_NO_NEW_PRIVS) failed")

def main():
    args = sys.argv[1:]
    cfg = None
    if "--config" in args:
        i = args.index("--config")
        cfg = args[i+1]
        del args[i:i+2]

    if "--" not in args:
        print("secwrap: usage: secwrap.py [--config file] -- <cmd> [args...]", file=sys.stderr)
        sys.exit(97)
    k = args.index("--")
    real_cmd = args[k+1:]

    # 1) no_new_privs
    set_no_new_privs()

    # 2) seccomp
    ok = False
    if cfg and Path(cfg).exists():
        ok = create_seccomp_from_config(cfg)
    else:
        ok = create_seccomp()
    if not ok:
        print("secwrap: WARNING: seccomp NOT enforced (fallback).", file=sys.stderr)

    # 3) exec
    os.execvp(real_cmd[0], real_cmd)

if __name__ == "__main__":
    main()
