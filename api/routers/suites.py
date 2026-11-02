# api/routers/suites.py
from fastapi import APIRouter, HTTPException
from api.schemas.suite import SuiteListResponse, SuiteInfo, SuiteUpdateRequest
from services.suite_service import list_suites, get_suite, update_suite

router = APIRouter()


@router.get("", response_model=SuiteListResponse)
def api_list_suites():
    data = list_suites()
    return SuiteListResponse(suites=[SuiteInfo(**s) for s in data])


@router.get("/{name}", response_model=SuiteInfo)
def api_get_suite(name: str):
    s = get_suite(name)
    if not s:
        raise HTTPException(404, f"suite not found: {name}")
    return SuiteInfo(**s)


@router.put("/{name}", response_model=SuiteInfo)
def api_update_suite(name: str, body: SuiteUpdateRequest):
    s = update_suite(name, body.model_dump(exclude_none=True))
    if not s:
        raise HTTPException(404, f"suite not found: {name}")
    return SuiteInfo(**s)