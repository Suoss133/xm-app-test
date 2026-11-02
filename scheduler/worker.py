# scheduler/worker.py
import threading
from datetime import datetime
from typing import Optional

from scheduler.models import JobStatus
from scheduler.runner import run_pytest_job
from utils.logger import logger   # ← 必须在模块顶层


class DeviceWorker(threading.Thread):
    """每个 device_udid 一个 Worker，串行消费该设备队列"""

    def __init__(self, device_udid: str, job_manager):
        super().__init__(daemon=True, name=f"worker-{device_udid}")
        self.device_udid = device_udid
        self.job_manager = job_manager
        self._stop_job_ids: set = set()
        self._current_job_id: Optional[str] = None

    def request_stop(self, job_id: str):
        self._stop_job_ids.add(job_id)

    def run(self):
        logger.info(f"[Worker:{self.device_udid}] 启动")
        while True:
            job = self.job_manager.pop_next(self.device_udid)
            if job is None:
                # 队列空，退出；有新任务时 JobManager 会再拉起 Worker
                logger.info(f"[Worker:{self.device_udid}] 队列空，退出")
                break

            self._current_job_id = job.id
            self.job_manager.update_job(
                job.id,
                status=JobStatus.RUNNING,
                started_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.job_manager.publish_log(job.id, f"[系统] 任务开始 suite={job.suite}")

            def log_cb(line: str):
                self.job_manager.publish_log(job.id, line)

            def stop_flag() -> bool:
                return job.id in self._stop_job_ids

            try:
                code = run_pytest_job(
                    suite=job.suite,
                    device_udid=job.device_udid,
                    params=job.params,
                    current_app=job.current_app,
                    log_callback=log_cb,
                    stop_flag=stop_flag,
                    job_id=job.id,
                )
                if job.id in self._stop_job_ids:
                    status = JobStatus.STOPPED
                    msg = "用户停止"
                elif code == 0:
                    status = JobStatus.SUCCESS
                    msg = "执行成功"
                else:
                    status = JobStatus.FAILED
                    msg = f"pytest 退出码: {code}"

                self.job_manager.update_job(
                    job.id,
                    status=status,
                    message=msg,
                    return_code=code,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                )
                self.job_manager.publish_log(job.id, f"[系统] 任务结束: {msg}")
            except Exception as e:
                logger.exception(f"[Worker] 任务异常 {job.id}")
                self.job_manager.update_job(
                    job.id,
                    status=JobStatus.FAILED,
                    message=str(e),
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                )
                self.job_manager.publish_log(job.id, f"[系统] 异常: {e}")
            finally:
                self.job_manager.publish_log(job.id, None)  # WS 结束
                self._current_job_id = None
                self._stop_job_ids.discard(job.id)

        def log_cb(line: str):
            # 终端也能看到 pytest 输出，方便排查
            logger.info(f"[job:{job.id}] {line}")
            self.job_manager.publish_log(job.id, line)