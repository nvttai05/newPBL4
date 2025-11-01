from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field, create_engine, Session
from enum import Enum
from datetime import datetime
from typing import Optional

class JobStatus(str, Enum):
    QUEUED="QUEUED"; RUNNING="RUNNING"
    FINISHED="FINISHED"; FAILED="FAILED"; TIMEOUT="TIMEOUT"; KILLED="KILLED"

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    reason: Optional[str] = None
    lang: str = "python"
    entry: str = "main.py"

class JobStore:
    def __init__(self, url="sqlite:///./sandbox.db"):
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine)
        # tạo Session factory với expire_on_commit=False
        self.SessionLocal = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False)

    def add(self, job: Job):
        with self.SessionLocal() as s:
            s.add(job)
            s.commit()

    def get(self, job_id: str) -> Optional[Job]:
        with self.SessionLocal() as s:
            return s.get(Job, job_id)

    def update(self, job: Job) -> Job:
        with self.SessionLocal() as s:
            # gắn (attach) đối tượng trở lại session hiện tại
            db_job = s.merge(job)
            s.commit()
            return db_job