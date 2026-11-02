import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import devices, suites,jobs,ws
from scheduler.queue import job_manager

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routers import devices, suites, jobs, ws, reports

from collections import Counter
from scheduler.queue import job_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager.set_event_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title="App压测调度平台",
    version="1.0.0",
    description="多设备 用例调度 实时日志",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(suites.router, prefix="/api/suites", tags=["suites"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(ws.router,tags=["websocket"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/meta/jobs-summary")
def jobs_summary():
    jobs = job_manager.list_jobs(limit=100)
    return {
        "total": len(jobs),
        "by_status": dict(Counter(j.status.value for j in jobs)),
        "recent": [j.to_dict() for j in jobs[:15]],
    }

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="static")