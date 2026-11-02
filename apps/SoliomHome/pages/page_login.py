from appium.webdriver.common.appiumby import AppiumBy
from apps.base.base_login_page import BaseLoginPage


class LoginPage(BaseLoginPage):

    def __init__(self):
        super().__init__(
            page_name="登录页",
            config_path="apps/SoliomHome/config.yaml",
            page_config_name="login",
            handle_popup=False  # 启用弹窗处理
        )

        self.LOGIN_IDENTIFIER = (AppiumBy.XPATH, '//android.widget.TextView[@text="欢迎回来"]')

    def get_login_identifier_element(self):
        """获取登录唯一标识"""
        try:
            result = self.is_element_visible(self.LOGIN_IDENTIFIER)
            if result:
                return True
            else:
                return False
        except Exception as e:
            self._handle_error(f"获取登录唯一标识失败: {str(e)}", "获取登录唯一标识失败")
            return False