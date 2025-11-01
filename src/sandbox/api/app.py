from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ..services.job_store import JobStore
from ..services.orchestrator import Orchestrator

app = FastAPI(title="Sandbox Pro-Lite")
store = JobStore()
orc = Orchestrator(store)

class JobReq(BaseModel):
    code: str
    entry: str = "main.py"

@app.post("/jobs")
def submit(req: JobReq):
    jid = orc.submit_python(req.code, req.entry)
    return {"job_id": jid}

@app.post("/jobs/{job_id}/run")
def run_job(job_id: str):
    # kiểm tra xem job có tồn tại không
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        orc.run(job_id)
        return {"ok": True}
    except Exception as e:
        # log lỗi để debug nếu cần
        print(f"Error while running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}")
def status(job_id: str):
    j = store.get(job_id)
    return j.dict() if j else {"error": "not found"}

@app.get("/jobs/{job_id}/logs")
def logs(job_id: str):
    return orc.logs(job_id)
