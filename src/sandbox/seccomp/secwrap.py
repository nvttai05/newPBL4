# src/sandbox/seccomp/secwrap.py
import sys, argparse, runpy
from pathlib import Path
from .seccomp_helper import create_seccomp_from_config

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--", dest="cmd", nargs=argparse.REMAINDER, default=[])
    args = ap.parse_args()

    # Áp profile
    f = Path(args.config)
    filt = create_seccomp_from_config(f.read_text(encoding="utf-8"))
    filt.load()  # bật filter

    if args.cmd:
        # exec chương trình user
        import os
        os.execvp(args.cmd[0], args.cmd)

if __name__ == "__main__":
    main()
