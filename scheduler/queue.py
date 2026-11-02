# scheduler/queue.py
import asyncio
import threading
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Deque, Optional, List

from scheduler.models import Job, JobStatus
from utils.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_JOBS_DIR = PROJECT_ROOT / "logs" / "jobs"


class JobManager:
    def __init__(self):
        self._queues: Dict[str, Deque[Job]] = defaultdict(deque)
        self._jobs: Dict[str, Job] = {}
        self._workers: Dict[str, object] = {}
        self._log_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._log_buffers: Dict[str, List[str]] = defaultdict(list)
        self._max_log_lines = 8000
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        LOG_JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _log_file(self, job_id: str) -> Path:
        return LOG_JOBS_DIR / f"{job_id}.log"

    def submit_job(
        self,
        suite: str,
        device_udid: str,
        params: Optional[dict] = None,
        current_app: Optional[str] = None,
        pipeline_name: Optional[str] = None,
    ) -> Job:
        job = Job(
            suite=suite,
            device_udid=device_udid,
            params=params or {},
            current_app=current_app,
            pipeline_name=pipeline_name,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._log_buffers[job.id] = []
            # 新建空日志文件
            self._log_file(job.id).write_text("", encoding="utf-8")
            self._queues[device_udid].append(job)
            self._ensure_worker(device_udid)
        logger.info(f"[JobManager] 入队 job={job.id} suite={suite} device={device_udid}")
        return job

    def _ensure_worker(self, device_udid: str):
        w = self._workers.get(device_udid)
        if w is None or not getattr(w, "is_alive", lambda: False)():
            from scheduler.worker import DeviceWorker
            worker = DeviceWorker(device_udid, self)
            self._workers[device_udid] = worker
            worker.start()

    def pop_next(self, device_udid: str) -> Optional[Job]:
        with self._lock:
            q = self._queues.get(device_udid)
            if q:
                return q.popleft()
        return None

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def update_job(self, job_id: str, **kwargs):
        job = self._jobs.get(job_id)
        if not job:
            return
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)

    def stop_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.STOPPED):
            return False
        worker = self._workers.get(job.device_udid)
        if worker:
            worker.request_stop(job_id)
        job.status = JobStatus.STOPPED
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        job.message = "用户停止"
        self.publish_log(job_id, "[系统] 任务已停止")
        self.publish_log(job_id, None)
        return True

    def append_log_line(self, job_id: str, line: Optional[str]):
        if line is None:
            return
        # 内存
        buf = self._log_buffers[job_id]
        buf.append(line)
        if len(buf) > self._max_log_lines:
            del buf[: len(buf) - self._max_log_lines]
        # 落盘
        try:
            with open(self._log_file(job_id), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.warning(f"[JobManager] 写日志文件失败 {job_id}: {e}")

    def get_logs(self, job_id: str) -> List[str]:
        # 优先读磁盘（重启后仍可用）
        path = self._log_file(job_id)
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
                lines = text.splitlines()
                if lines:
                    return lines
            except Exception as e:
                logger.warning(f"[JobManager] 读日志文件失败 {job_id}: {e}")
        return list(self._log_buffers.get(job_id, []))

    def subscribe_logs(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._log_subscribers[job_id].append(q)
        return q

    def unsubscribe_logs(self, job_id: str, q: asyncio.Queue):
        subs = self._log_subscribers.get(job_id, [])
        if q in subs:
            subs.remove(q)

    def publish_log(self, job_id: str, line: Optional[str]):
        self.append_log_line(job_id, line)
        subs = list(self._log_subscribers.get(job_id, []))
        if not subs:
            return

        def _put(q: asyncio.Queue, item):
            try:
                q.put_nowait(item)
            except Exception:
                pass

        loop = self._loop
        for q in subs:
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(_put, q, line)
            else:
                _put(q, line)


job_manager = JobManager()