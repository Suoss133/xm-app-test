# api/routers/reports.py
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS = PROJECT_ROOT / "reports"


@router.get("")
def list_reports():
    excel_list = []
    for p in PROJECT_ROOT.rglob("*.xlsx"):
        if any(x in str(p) for x in (".venv", "venv", "site-packages")):
            continue
        st = p.stat()
        excel_list.append({
            "name": p.name,
            "path": str(p),
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    excel_list.sort(key=lambda x: x["mtime"], reverse=True)

    allure_dir = REPORTS / "allure-results"
    allure_info = None
    if allure_dir.exists():
        files = list(allure_dir.glob("*"))
        allure_info = {
            "path": str(allure_dir),
            "file_count": len(files),
            "hint": "allure serve reports/allure-results",
        }

    shots = []
    shot_root = PROJECT_ROOT / "screenshots"
    if shot_root.exists():
        for f in sorted(shot_root.rglob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
            shots.append({
                "name": f.name,
                "path": str(f),
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
            })

    return {
        "allure_results": allure_info,
        "excel": excel_list[:50],
        "screenshots": shots,
    }


@router.get("/download")
def download_report(path: str = Query(..., description="文件绝对路径")):
    p = Path(path).resolve()
    root = PROJECT_ROOT.resolve()
    if not str(p).startswith(str(root)):
        raise HTTPException(403, "非法路径")
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path=str(p), filename=p.name)