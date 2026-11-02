# core/recovery_policy.py
from core.result import FailureType, RecoveryAction

# 执行策略
DEFAULT_POLICY = {
    FailureType.NONE:                  RecoveryAction.CONTINUE,
    FailureType.LIVE_VIEW_FAILED:      RecoveryAction.CONTINUE,       # 出图失败：只记录，不重启
    FailureType.DEVICE_NOT_FOUND:      RecoveryAction.RESTART_APP,    # 蓝牙设备未找到：重启 App
    FailureType.NETWORK_CONFIG_FAILED: RecoveryAction.RESTART_APP,
    FailureType.DELETE_FAILED:         RecoveryAction.STOP_SUITE,
    FailureType.ELEMENT_NOT_FOUND:     RecoveryAction.RESTART_APP,
    FailureType.UNKNOWN:               RecoveryAction.RESTART_APP,
}

SUITE_POLICY = {
    "binding": DEFAULT_POLICY,
    "LiveImageUniversal": {
        **DEFAULT_POLICY,
        FailureType.LIVE_VIEW_FAILED: RecoveryAction.CONTINUE,
    },
}


def get_recovery_action(suite_name: str, failure_type: FailureType) -> RecoveryAction:
    """根据套件名和失败类型返回恢复动作"""
    policy = SUITE_POLICY.get(suite_name, DEFAULT_POLICY)
    return policy.get(failure_type, RecoveryAction.RESTART_APP)