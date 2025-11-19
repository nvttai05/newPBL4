from __future__ import annotations
import os
import sys
from pathlib import Path
from ..isolation.seccomp import make_seccomp_preexec

def main():
    if len(sys.argv) < 3:
        print("Usage: python -m sandbox.runner.seccomp_entry <policy_path> <script>", file=sys.stderr)
        sys.exit(1)

    policy_path = Path(sys.argv[1])
    script_path = sys.argv[2]

    # Tạo preexec seccomp và APPLY NGAY trong process hiện tại
    seccomp_preexec = make_seccomp_preexec(policy_path)

    # Áp seccomp filter vào process này
    seccomp_preexec()

    # Exec sang python chạy script thật (vẫn trong sandbox, nhưng bị seccomp hạn chế)
    os.execv(sys.executable, [sys.executable, script_path])


if __name__ == "__main__":
    main()
