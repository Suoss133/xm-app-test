# api/routers/jobs.py
from fastapi import APIRouter, HTTPException
from api.schemas.job import (
    JobCreateRequest,
    JobInfo,
    PipelineRunRequest,
)
from scheduler.queue import job_manager

router = APIRouter()


@router.post("", response_model=JobInfo)
@router.post("/", response_model=JobInfo)
def create_job(body: JobCreateRequest):
    job = job_manager.submit_job(
        suite=body.suite,
        device_udid=body.device_udid,
        params=body.params,
        current_app=body.current_app,
    )
    return JobInfo(**job.to_dict())


@router.post("/pipeline")
def run_pipeline(body: PipelineRunRequest):
    job_ids = []
    for step in body.steps:
        job = job_manager.submit_job(
            suite=step.suite,
            device_udid=step.device_udid,
            params=step.params,
            current_app=step.current_app,
            pipeline_name=body.name,
        )
        job_ids.append(job.id)
    return {"pipeline": body.name, "job_ids": job_ids}


@router.get("", response_model=list[JobInfo])
@router.get("/", response_model=list[JobInfo])
def list_jobs(limit: int = 50):
    jobs = job_manager.list_jobs(limit=limit)
    return [JobInfo(**j.to_dict()) for j in jobs]


@router.get("/{job_id}/logs")
def get_job_logs(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    lines = job_manager.get_logs(job_id)
    return {
        "job_id": job_id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "lines": lines,
        "count": len(lines),
    }


@router.get("/{job_id}", response_model=JobInfo)
def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return JobInfo(**job.to_dict())


@router.post("/{job_id}/stop")
def stop_job(job_id: str):
    ok = job_manager.stop_job(job_id)
    if not ok:
        raise HTTPException(400, "无法停止该任务（不存在或已结束）")
    return {"ok": True, "job_id": job_id}