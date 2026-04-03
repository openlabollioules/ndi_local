from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class ProgressStore:
    MAX_JOBS = 100  # Plafond pour éviter la fuite mémoire

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def _cleanup_completed_jobs(self) -> None:
        """Remove oldest completed jobs if we exceed MAX_JOBS."""
        if len(self._jobs) <= self.MAX_JOBS:
            return

        # Sort jobs by creation time (uuid timestamp approximation) and done status
        completed = [(jid, job) for jid, job in self._jobs.items() if job.get("done", False)]
        if len(completed) > self.MAX_JOBS // 2:
            # Remove oldest 25% of completed jobs
            to_remove = len(completed) - self.MAX_JOBS // 2
            for jid, _ in completed[:to_remove]:
                del self._jobs[jid]

    def create_job(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._cleanup_completed_jobs()
            self._jobs[job_id] = {"events": [], "done": False, "created_at": time.time()}
        return job_id

    def add_event(self, job_id: str, step: str, message: str) -> None:
        event = {
            "step": step,
            "message": message,
            "timestamp": time.time(),
        }
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["events"].append(event)

    def complete(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["done"] = True

    def get_events(self, job_id: str, cursor: int) -> tuple[list[dict], bool]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return [], True
            events = job["events"][cursor:]
            done = job["done"]
        return events, done


progress_store = ProgressStore()
