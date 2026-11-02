import allure

from apps.base.base_setting_device_page import BaseSettingDevicePage
from core.yaml_utils import YamlUtils
from utils.logger import logger


class SettingsDevicePage(BaseSettingDevicePage):

    def __init__(self):
        super().__init__(
            page_name="设备设置页",
            config_path="apps/Koocam/config.yaml",
            page_config_name="setting_device"
        )

        self.setting_page_title = YamlUtils.parse_dynamic_locator(self.elements["setting_page_title"])
