import allure
from apps.base.base_add_device_page import BaseAddDevicePage
from core.yaml_utils import YamlUtils

class AddDevicePage(BaseAddDevicePage):

    def __init__(self):
        super().__init__(
            page_name="首页",
            config_path="apps/Humbirdy/config.yaml",
            page_config_name="add_device"
        )

    def click_select_device(self, device_name):
        """
        点击选择设备
        :param device_name: 设备名称
        :return:
        """
        # 指定目标设备元素
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["select_device"],
            device_name
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击选择设备按钮"):
                self.click(locator)
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击选择设备按钮失败"):
                self._handle_error(f"点击选择设备按钮失败：{e}", "点击选择设备按钮失败")