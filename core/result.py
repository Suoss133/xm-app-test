# core/result.py
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class FailureType(Enum):
    NONE = auto()
    DEVICE_NOT_FOUND = auto()          # 蓝牙设备未找到
    NETWORK_CONFIG_FAILED = auto()     # 配网失败
    LIVE_VIEW_FAILED = auto()          # 出图失败
    DELETE_FAILED = auto()             # 删除设备失败
    ELEMENT_NOT_FOUND = auto()         # 通用元素未找到
    UNKNOWN = auto()                   # 未知异常


class RecoveryAction(Enum):
    CONTINUE = auto()      # 只记录结果，继续下一轮（不重启）
    RESTART_APP = auto()   # 重启 App
    STOP_SUITE = auto()    # 终止整个压测（pytest.skip）
    SKIP = auto()          # 跳过当前用例


@dataclass
class StepResult:
    success: bool
    failure_type: FailureType = FailureType.NONE
    message: str = ""
    data: Any = None
    screenshot_taken: bool = False

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "StepResult":
        return cls(success=True, failure_type=FailureType.NONE, message=message, data=data)

    @classmethod
    def fail(
        cls,
        failure_type: FailureType,
        message: str,
        data: Any = None,
        screenshot_taken: bool = True,
    ) -> "StepResult":
        return cls(
            success=False,
            failure_type=failure_type,
            message=message,
            data=data,
            screenshot_taken=screenshot_taken,
        )