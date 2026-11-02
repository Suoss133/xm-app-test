# core/allure_helper.py

from core.result import FailureType, StepResult
import re


def get_friendly_title(counter: int, result: StepResult) -> str:
    """
    根据 StepResult 生成 Allure友好标题
    :param counter:
    :param result:
    :return:
    """

    if result.success:
        return f"第 {counter} 次 执行成功"

    msg = result.message or ""

    if result.failure_type == FailureType.LIVE_VIEW_FAILED:
        return f"第 {counter} 次 出图失败:{msg}"

    if result.failure_type == FailureType.NETWORK_CONFIG_FAILED:
        return f"第 {counter} 次 {result.message}"

    # 配网失败 / UNKNOWN 里带设备SN的情况
    if result.failure_type in (FailureType.NETWORK_CONFIG_FAILED, FailureType.UNKNOWN):
        # 尝试提取 “设备配网失败: xxxx” 或直接使用原消息
        if "配网失败" in msg or "添加失败" in msg:
            return f"第 {counter} 次 {msg}"
        return f"第 {counter} 次 设备配网失败：{msg}"

    # 蓝牙设备未找到
    if result.failure_type == FailureType.DEVICE_NOT_FOUND:
        return f"第 {counter} 次 蓝牙设备未找到：{msg}"

    # 删除失败
    if result.failure_type == FailureType.DELETE_FAILED:
        return f"第 {counter} 次 删除设备失败：{msg}"

    # 其他未知
    return f"第 {counter} 次 执行失败：{msg}"
