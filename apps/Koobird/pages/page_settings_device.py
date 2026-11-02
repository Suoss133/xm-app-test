from apps.base.base_setting_device_page import BaseSettingDevicePage


class SettingsDevicePage(BaseSettingDevicePage):

    def __init__(self):
        super().__init__(
            page_name="设备设置页",
            config_path="apps/koobird/config.yaml",
            page_config_name="setting_device"
        )