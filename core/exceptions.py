# core/exceptions.py
class BluetoothBindingError(Exception):
    pass

class DeviceNotFoundError(BluetoothBindingError):
    pass

class NetworkConfigFailedError(BluetoothBindingError):
    pass

class DeleteDeviceFailedError(BluetoothBindingError):
    pass

class LiveViewFailedError(BluetoothBindingError):
    pass

class BusinessFailure(Exception):
    """通用业务失败（兼容旧代码）"""
    pass

class BusinessTestFailure(AssertionError):
    """业务失败，用于让 Allure 显示为 Failed，同时可携带 failure_type"""
    def __init__(self, message: str, failure_type=None):
        super().__init__(message)
        self.failure_type = failure_type


class RestartRequired(Exception):
    """
    需要重启 App 的信号异常
    """
    def __init__(self, message: str, failure_type=None):
        super().__init__(message)
        self.failure_type = failure_type