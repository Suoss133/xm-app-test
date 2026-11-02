from apps.common.actions.common import get_page_instance


# 删除设备
def delete_device(app_name, device_name):
    """
    删除设备
    :param app_name:
    :param device_name:
    :return:
    """
    setting = get_page_instance(app_name, "page_settings_device", "SettingsDevicePage")
    setting.delete_device_by_result()