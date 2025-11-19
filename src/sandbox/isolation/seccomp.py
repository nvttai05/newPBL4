from __future__ import annotations
from typing import Callable
from pathlib import Path
import json

def _load_syscall_list(policy_path: Path) -> list:
    """
    Đọc danh sách syscall từ YAML hoặc JSON.
    Dùng như DENY-LIST (danh sách bị cấm).
    """
    if not policy_path or not policy_path.exists():
        return []

    txt = policy_path.read_text(encoding="utf-8").strip()
    if not txt:
        return []

    # JSON
    if txt.startswith("{") or txt.startswith("["):
        try:
            data = json.loads(txt)
            if isinstance(data, dict):
                return list(dict.fromkeys(data.get("syscalls", [])))
            if isinstance(data, list):
                return list(dict.fromkeys(data))
        except Exception:
            pass

    # YAML
    try:
        import yaml
        data = yaml.safe_load(txt)
        if isinstance(data, dict):
            return list(dict.fromkeys(data.get("syscalls", [])))
        if isinstance(data, list):
            return list(dict.fromkeys(data))
    except Exception:
        pass

    # Fallback: dạng "- fork"
    items = []
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
    return list(dict.fromkeys(items))


def make_seccomp_preexec(policy_path: Path, mode: str = "enforcing") -> Callable[[], None]:
    """
    Trả về hàm preexec() sẽ apply seccomp dạng BLACKLIST:
    - Mặc định: ALLOW mọi syscall
    - Những syscall trong policy: KILL khi gọi đến
    """
    try:
        import seccomp  # python3-seccomp
    except Exception:
        # Nếu không có lib seccomp thì bỏ qua
        return lambda: None

    deny_syscalls = _load_syscall_list(policy_path)

    def _preexec() -> None:
        # Cho qua tất cả syscall, trừ những cái bị deny
        default_action = seccomp.ALLOW
        f = seccomp.SyscallFilter(default_action)

        for name in deny_syscalls:
            try:
                f.add_rule(seccomp.KILL, name)
            except Exception:
                # Nếu syscall không tồn tại trên kiến trúc hiện tại thì bỏ qua
                pass

        f.load()  # kích hoạt seccomp filter trong child process

    return _preexec
