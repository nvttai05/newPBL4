import requests, time

def test_lifecycle():
    # giả định API đang chạy localhost:8000 (bạn có thể chuyển sang httpx + TestClient nếu muốn)
    jid = requests.post("http://localhost:8000/jobs", json={"code":"print('ok')","entry":"main.py"}).json()["job_id"]
    requests.post(f"http://localhost:8000/jobs/{jid}/run")
    time.sleep(0.5)
    st = requests.get(f"http://localhost:8000/jobs/{jid}").json()
    assert st["status"] in ("FINISHED","FAILED","TIMEOUT")
