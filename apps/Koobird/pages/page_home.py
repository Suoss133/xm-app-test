import time

import allure
from appium.webdriver.common.appiumby import AppiumBy

from apps.base.base_home_page import BaseHomePage
from core.result import StepResult, FailureType
from core.yaml_utils import YamlUtils
from utils.logger import logger


class HomePage(BaseHomePage):

    def __init__(self):
        super().__init__(
            page_name="首页",
            config_path="apps/Koobird/config.yaml",
            page_config_name="home",
            handle_popup = True  # 启用弹窗处理
        )

        self.live_button = YamlUtils.parse_locator(self.elements["live_button"])

    def click_live_button(self,device_title):
        """默认选择页面第一个设备直播按钮"""
        try:
            self.click(self.live_button, handle_popup=self.handle_popup)
            logger.info(f"点击设备直播按钮成功")
            return StepResult.ok()
        except Exception as e:
            self._handle_error(f"点击设备直播按钮失败: {str(e)}",
                               "点击设备直播按钮失败",
                               raise_exception=False,
                               failure_type=FailureType.ELEMENT_NOT_FOUND)


    def get_home_identifier_element(self):
        """获取首页唯一标识"""
        try:
            result = self.get_text(self.HOME_PAGE_IDENTIFIER, handle_popup=self.handle_popup)
            if result == '全部设备':
                return True
            else:
                return False
        except Exception as e:
            self._handle_error(f"获取首页唯一标识失败: {str(e)}", "获取首页唯一标识失败")
            return False


    # 校验设备是否成功删除
    def check_device_delete(self, device_name):
        """校验设备是否成功删除"""
        locator = (AppiumBy.ID,'com.koobird.android:id/tv_dev_name')
        try:
            result = self.get_text(locator, handle_popup=self.handle_popup)
            if result in device_name:
                return False
            else:
                return True
        except Exception as e:
            return True