# api/routers/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from scheduler.queue import job_manager

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_logs_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    # 先推历史日志
    history = job_manager.get_logs(job_id)
    await websocket.send_json({"type": "history", "lines": history})

    # 再订阅增量
    q = job_manager.subscribe_logs(job_id)
    try:
        while True:
            line = await q.get()
            if line is None:
                await websocket.send_json({"type": "done"})
                break
            await websocket.send_json({"type": "log", "line": line})
    except WebSocketDisconnect:
        job_manager.unsubscribe_logs(job_id, q)