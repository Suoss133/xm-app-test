# api/routers/devices.py
from fastapi import APIRouter
from api.schemas.device import DeviceListResponse, DeviceInfo
from services.device_service import list_devices

router = APIRouter()


@router.get("", response_model=DeviceListResponse)
def get_devices():
    devices = list_devices()
    return DeviceListResponse(
        devices=[DeviceInfo(**d) for d in devices]
    )