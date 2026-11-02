from pydantic import BaseModel
from typing import List, Optional


class DeviceInfo(BaseModel):
    udid: str
    status: str = "device"
    model: Optional[str] = None

class DeviceListResponse(BaseModel):
    devices: List[DeviceInfo]