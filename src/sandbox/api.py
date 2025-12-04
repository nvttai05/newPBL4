from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from .core.utils import infer_lang_from_entry
from .services.job_service import JobService


app = FastAPI(title="Sandbox API")

# Serve static (nếu có UI/debug page)
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
    # FE có thể gửi lang: "python", "go", ...
    # Nếu FE không gửi, BE sẽ tự đoán từ entry (infer_lang_from_entry)
    lang: Optional[str] = None


class CreateJobRes(BaseModel):
    job_id: str


class RunJobRes(BaseModel):
    ok: bool
    reason: Optional[str] = None  # Thêm lý do nếu có lỗi


class JobStatusRes(BaseModel):
    id: str
    status: str
    # Sử dụng Optional để tương thích với các phiên bản Python cũ hơn
    exit_code: Optional[int] = 0
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
    # Ưu tiên dùng lang FE gửi, nếu không có thì tự infer từ entry
    lang = (req.lang or "").lower() or infer_lang_from_entry(req.entry)

    # Hỗ trợ "python", "go" (và các lang khác nếu đã cấu hình)
    # Nếu bạn chưa implement node/bash, có thể bỏ chúng khỏi list này.
    if lang not in ("python", "go", "node", "bash"):
        raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")

    try:
        # Truyền lang xuống JobService
        job_id = svc.create_job(entry=req.entry, code=req.code, lang=lang)
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
        # Thêm reason nếu có lỗi
        return RunJobRes(ok=False, reason=str(e))
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
