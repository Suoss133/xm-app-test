import allure

from apps.base.base_home_page import BaseHomePage
from core.result import StepResult, FailureType
from core.yaml_utils import YamlUtils
from utils.logger import logger


class HomePage(BaseHomePage):

    def __init__(self):
        super().__init__(
            page_name="首页",
            config_path="apps/baseus/config.yaml",
            page_config_name="home"
        )

        # 发现新设备弹窗
        self.live_button = YamlUtils.parse_locator(self.elements["live_button"])

    # 获取页面唯一标识
    def get_home_feature_element(self):
        """获取首页唯一标识"""
        try:
            result = self.get_text(self.HOME_PAGE_IDENTIFIER)
            if result == '我的设备':
                return True
            else:
                return False
        except Exception as e:
            self._handle_error(f"获取首页唯一标识失败: {str(e)}", "获取首页唯一标识失败")
            return False

    def click_live_button(self, name):
        """默认选择第一个设备直播按钮"""
        try:
            self.click(self.live_button, handle_popup=self.handle_popup)
            logger.info(f"点击设备直播按钮成功")
            return StepResult.ok()
        except Exception as e:
            self._handle_error(f"点击设备直播按钮失败: {str(e)}",
                               "点击设备直播按钮失败",
                               raise_exception=False,
                               failure_type=FailureType.ELEMENT_NOT_FOUND)

