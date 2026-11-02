from pydantic import BaseModel,Field
from typing import Any,Dict,Optional

class SuiteInfo(BaseModel):
    name: str
    enable: bool = False
    current_app:str
    device_udid: Optional[str] =  None
    description: Optional[str] = None
    parameter: Dict[str, Any] = Field(default_factory=dict)

class SuiteUpdateRequest(BaseModel):
    """更新测试集请求"""
    enable: bool = False
    current_app:str
    device_udid: Optional[str] =  None
    parameter: Dict[str, Any] = Field(default_factory=dict)

class SuiteListResponse(BaseModel):
    """测试集列表响应"""
    suites: list[SuiteInfo]