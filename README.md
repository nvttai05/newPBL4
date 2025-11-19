# sandboxpy (sườn FULL)
- API giữ đúng RuleFE: /jobs endpoints
- Tầng bảo mật: rlimits → ns/chroot → cgroups → seccomp
- DB nhúng: SQLite
- Đa ngôn ngữ: Python (Node runner để sẵn)

## Dev quickstart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn sandbox.api:app --reload --port 8000 --app-dir src

## Test
# Tạo job
JOB=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'content-type: application/json' \
  -d '{"entry":"main.py","code":"x=bytearray(100*1024*1024); print(\"allocated 100MB\")"}' \
  | jq -r '.job_id')
echo "JOB=$JOB"
# 1) Run job
curl -s -X POST "http://127.0.0.1:8000/jobs/$JOB/run" >/dev/null

# 2) Poll trạng thái cho tới khi xong
while true; do
  S=$(curl -s "http://127.0.0.1:8000/jobs/$JOB" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status=$S"
  [[ "$S" = "FINISHED" || "$S" = "FAILED" ]] && break
  sleep 0.4
done

# 3) In logs (định dạng đẹp)
curl -s "http://127.0.0.1:8000/jobs/$JOB/logs" | python3 -m json.tool



# 1) Tạo job
JOB=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'content-type: application/json' \
  -d '{"entry":"main.py","code":"print(\"hello sandbox\")"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
echo "JOB=$JOB"

# 2) Chạy job
curl -s -X POST http://127.0.0.1:8000/jobs/$JOB/run >/dev/null

# 3) Poll (zsh an toàn, không dùng =~)
while true; do
  S=$(curl -s http://127.0.0.1:8000/jobs/$JOB \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status=$S"
  [[ "$S" = "FINISHED" || "$S" = "FAILED" ]] && break
  sleep 0.3
done

# 4) Lấy logs
curl -s http://127.0.0.1:8000/jobs/$JOB/logs
