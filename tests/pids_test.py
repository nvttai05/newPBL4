# pid_stress.py — hit pids.max deterministically
import subprocess, sys, time

children = []
try:
    for i in range(1, 10000):
        # mỗi child chỉ ngủ, đỡ ồn stdout, dễ giữ lại để cleanup
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        children.append(p)
        if i % 50 == 0:
            print(f"spawned {i}", flush=True)
except Exception as e:
    # pids.max đụng trần -> OSError: [Errno 11] Resource temporarily unavailable
    print("SPAWN_FAILED", type(e).__name__, str(e), flush=True)
finally:
    for p in children:
        try: p.terminate()
        except Exception: pass


# # A) tạo job
# resp=$(curl -sS -X POST 127.0.0.1:8000/jobs \
#   -H 'content-type: application/json' \
#   -d @- <<'JSON'
# {"entry":"mem_stress.py","code":"# mem_stress.py — try to exceed memory.max\nimport time, sys\n\nchunks = []\nsize = 16 * 1024 * 1024  # 16 MB/chunk\ntry:\n    for i in range(1, 10000):\n        chunks.append(bytearray(size))\n        if i % 4 == 0:\n            print(f\"allocated ~{i*size/1024/1024:.0f} MB\", flush=True)\n        time.sleep(0.05)\nexcept MemoryError as e:\n    print(\"MEMORYERROR\", str(e), flush=True)\n    sys.exit(1)\n"}
# JSON
# )
# jid=$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["job_id"])' "$resp"); echo "jid=$jid"
#
# curl -sS -i -X POST "127.0.0.1:8000/jobs/$jid/run"
# curl -sS "127.0.0.1:8000/jobs/$jid" | jq .jid" | jq .
# curl -sS "127.0.0.1:8000/jobs/$jid/logs" | jq .
