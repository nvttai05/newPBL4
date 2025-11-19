from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from starlette.staticfiles import StaticFiles

from .services.job_service import JobService
from .core.utils import infer_lang_from_entry

from fastapi.responses import JSONResponse
from pathlib import Path
import json

app = FastAPI(title="Sandbox API")

app.mount("/static", StaticFiles(directory="src/sandbox/static"), name="static")
# CORS: DEV mở rộng (*). PROD nên whitelist domain FE.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cập nhật lại nếu triển khai sản phẩm (whitelist domain FE)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

svc = JobService()

# --------- Schemas (theo RuleFE) ---------
class CreateJobReq(BaseModel):
    entry: str
    code: str

class CreateJobRes(BaseModel):
    job_id: str

class RunJobRes(BaseModel):
    ok: bool
    reason: Optional[str] = None  # Thêm lý do nếu có lỗi

class JobStatusRes(BaseModel):
    id: str
    status: str
    exit_code: Optional[int] = 0  # Sử dụng Optional để tương thích với các phiên bản Python cũ hơn
    reason: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    entry: str
    lang: str

class LogsRes(BaseModel):
    stdout: str
    stderr: str

# --------- Endpoints ---------

@app.get("/")
async def root():
    return {"message": "Welcome to the sandbox API"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/debug/job/{job_id}/meta")
def debug_job_meta(job_id: str):
    p = Path("jobs") / job_id / "meta.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="meta_not_found")
    try:
        return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs", response_model=CreateJobRes)
def create_job(req: CreateJobReq):
    lang = infer_lang_from_entry(req.entry)
    if lang not in ("python", "node", "bash"):  # hiện mới chạy python
        raise HTTPException(status_code=400, detail="Unsupported language")
    try:
        job_id = svc.create_job(entry=req.entry, code=req.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return CreateJobRes(job_id=job_id)

@app.post("/jobs/{job_id}/run", response_model=RunJobRes)
def run_job(job_id: str):
    try:
        svc.run_job(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job_not_found")
    except Exception as e:
        return RunJobRes(ok=False, reason=str(e))  # Thêm reason nếu có lỗi
    return RunJobRes(ok=True)

@app.get("/jobs/{job_id}", response_model=JobStatusRes)
def get_job(job_id: str):
    try:
        data = svc.get_status(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job_not_found")
    return JobStatusRes(**data)

@app.get("/jobs/{job_id}/logs", response_model=LogsRes)
def get_logs(job_id: str):
    try:
        data = svc.get_logs(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="job_not_found")
    return LogsRes(**data)
