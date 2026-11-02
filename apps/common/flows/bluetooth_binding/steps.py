# flows/bluetooth_binding/steps.py
from apps.common.actions.common import get_page_instance
from apps.common.actions.home import click_add_device_button, back_to_home, click_setting_button
from apps.common.actions.add_device import (
    select_bluetooth_device_by_sn,
    select_network,
    check_network_config_status,
)
from utils.logger import logger
import time


def step_click_add_button(context):
    click_add_device_button(context["app_name"])


def step_select_bluetooth_device(context):
    select_bluetooth_device_by_sn(context["app_name"], context["device_sn"])


def step_select_wifi(context):
    select_network(
        context["app_name"],
        context["wifi_ssid"],
        context["wifi_password"]
    )


def step_wait_binding_result(context) -> bool:
    """返回是否配网成功"""
    return check_network_config_status(
        context["app_name"],
        context["device_sn"],
        timeout=context.get("binding_timeout", 120)
    )


def step_back_to_home(context):
    back_to_home(context["app_name"])


def step_enter_device_setting(context):
    """
    进入设备设置页面
    :param context:
    :return:
    """
    app_name = context["app_name"]
    context["device_title"] = context["device_title"]
    click_setting_button(app_name, context["device_title"])


class FatalDeletionError(Exception):
    """删除失败 → 需要终止整个压测"""
    pass

def step_wait_and_delete_device(context):
    """等待 30s 后删除设备"""
    logger.info("等待 30 秒后删除设备...")
    time.sleep(30)

    # 执行删除
    setting_page = get_page_instance(context["app_name"], "page_settings_device", "SettingsDevicePage")
    try:
        setting_page.delete_devices()
        logger.info("设备删除成功")
    except Exception as e:
        # 这里抛出致命异常，让上层捕获并终止
        raise FatalDeletionError(f"删除设备失败: {str(e)}")