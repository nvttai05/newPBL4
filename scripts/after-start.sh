#!/usr/bin/env bash
set -euo pipefail

# Lấy đường cgroup hiện tại của chính ExecStartPost (chính là cgroup của sandbox.service)
CG="/sys/fs/cgroup$(sed -n 's/^0:://p' /proc/self/cgroup)"

# Chuẩn bị các nhánh con
mkdir -p "$CG/payload" "$CG/sbx"

# Chỉ di chuyển PID uvicorn xuống payload để root của service rỗng
# (Controller memory/pids bạn sẽ bật thủ công khi cgroup rỗng theo các bước trước)
echo "$MAINPID" > "$CG/payload/cgroup.procs" || true
