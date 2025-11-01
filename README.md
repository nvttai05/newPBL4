# Sandbox Pro-Lite

## Run API
```bash
uvicorn sandbox.api.app:app --reload

# Run 

Đặt biến và tạo thư mục:
CG=/sys/fs/cgroup/system.slice/sandbox.service
sudo mkdir -p "$CG/payload" "$CG/sbx"

Hút mọi PID ở root → payload
for i in $(seq 1 100); do
  procs=$(sudo cat "$CG/cgroup.procs" 2>/dev/null || true)
  [ -z "$procs" ] && break
  while read -r p; do
    [ -n "$p" ] && echo "$p" | sudo tee "$CG/payload/cgroup.procs" >/dev/null || true
  done <<< "$procs"
  sleep 0.03
done

Bật controller cho service và sbx
echo "+memory" | sudo tee "$CG/cgroup.subtree_control" >/dev/null || true
echo "+pids"   | sudo tee "$CG/cgroup.subtree_control" >/dev/null || true
echo "+cpu"    | sudo tee "$CG/cgroup.subtree_control" >/dev/null || true

echo "+memory" | sudo tee "$CG/sbx/cgroup.subtree_control" >/dev/null || true
echo "+pids"   | sudo tee "$CG/sbx/cgroup.subtree_control" >/dev/null || true
echo "+cpu"    | sudo tee "$CG/sbx/cgroup.subtree_control" >/dev/null || true


Check lại
echo "service subtree: $(sudo cat $CG/cgroup.subtree_control)"
echo "sbx subtree:     $(sudo cat $CG/sbx/cgroup.subtree_control)"
echo "root PIDs:";     sudo cat $CG/cgroup.procs || true
echo "payload PIDs:";  sudo cat $CG/payload/cgroup.procs || true

Kỳ vọng
service subtree: memory pids cpu
sbx subtree:     memory pids cpu
root PIDs:       (trống)
payload PIDs:    848


# Tạo job
resp=$(curl -sS -X POST 127.0.0.1:8000/jobs \
  -H 'content-type: application/json' \
  -d '{"code":"print(\"hello sandbox\")","entry":"main.py"}')
echo "RAW: $resp"
jid=$(python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["job_id"])' <<<"$resp")
echo "jid=$jid"


# Chạy job
curl -sS -i -X POST "127.0.0.1:8000/jobs/$jid/run"


curl -sS "127.0.0.1:8000/jobs/$jid" | jq .jid" | jq .
curl -sS "127.0.0.1:8000/jobs/$jid/logs" | jq .