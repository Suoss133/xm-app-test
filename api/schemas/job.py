from pydantic import BaseModel,Field
from typing import Any,Dict,Optional,List
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failed"
    STOPPED = "stopped"

class JobCreateRequest(BaseModel):
    suite:str
    device_udid:str
    params:Dict[str,Any] = Field(default_factory= dict)
    current_app: Optional[str] = None

class PipelineStep(BaseModel):
    suite: str
    device_udid: str
    params: Dict[str, Any] = Field(default_factory=dict)
    current_app: Optional[str] = None


class PipelineRunRequest(BaseModel):
    name: Optional[str] = "custom"
    steps: List[PipelineStep]


class JobInfo(BaseModel):
    id: str
    suite: str
    device_udid: str
    status: JobStatus
    params: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None