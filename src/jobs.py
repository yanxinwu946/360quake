from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from src.store import new_id


@dataclass
class Job:
    query: str
    size: int
    id: str = field(default_factory=new_id)
    status: str = "running"
    error: str = ""
    page: int = 0
    pages: int = 0
    count: int = 0
    data: list[dict] = field(default_factory=list)
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "query": self.query,
            "size": self.size,
            "status": self.status,
            "error": self.error,
            "page": self.page,
            "pages": self.pages,
            "count": self.count,
        }


class JobHub:
    def __init__(self, keep: int = 8):
        self.keep = keep
        self.jobs: dict[str, Job] = {}

    def add(self, job: Job) -> Job:
        self.jobs[job.id] = job
        extra = list(self.jobs)[: -self.keep]
        for key in extra:
            old = self.jobs.pop(key, None)
            if old and old.task and not old.task.done():
                old.cancel.set()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)
