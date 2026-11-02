import allure
from selenium.webdriver.support.wait import WebDriverWait

from core.base_page import BasePage
from core.yaml_utils import YamlUtils


class BasePersonalCenterPage(BasePage):
    """个人中心基类"""
    def __init__(self, page_name, config_path, page_config_name,handle_popup=False):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)
        self.handle_popup = handle_popup

        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        # 定义页面基础元素
        self.LOGOUT_BUTTON = YamlUtils.parse_locator(self.elements["logout_button"])
        self.LOGOUT_MESSAGE = YamlUtils.parse_locator(self.elements["logout_message"])
        self.LOGOUT_CONFIRM_BUTTON = YamlUtils.parse_locator(self.elements["confirm_logout_button"])
        self.LOGOUT_CANCEL_BUTTON = YamlUtils.parse_locator(self.elements["cancel_logout_button"])

    # 退出登录
    def _click_logout_button(self):
        """
        点击退出登录按钮
        """
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击退出登录"):
                self.click(self.LOGOUT_BUTTON)
        except Exception as e:
            self._handle_error(f"点击退出登录失败: {str(e)}", "点击退出登录失败")
            raise Exception("点击退出登录失败")

    # 获取弹窗退出信息
    def _get_logout_popup_message(self):
        """获取弹窗退出信息"""
        return self.get_text(self.LOGOUT_MESSAGE)

    # 确认退出登录
    def _click_confirm_logout(self):
        """确认退出登录"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 确认退出登录"):
                self.click(self.LOGOUT_CONFIRM_BUTTON)
        except Exception as e:
            self._handle_error(f"确认退出登录失败: {str(e)}", "确认退出登录失败")

    # 取消退出登录
    def _click_cancel_logout(self):
        """取消退出登录"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 取消退出登录"):
                self.click(self.LOGOUT_CANCEL_BUTTON)
        except Exception as e:
            self._handle_error(f"取消退出登录失败: {str(e)}", "取消退出登录失败")

    # 退出登录
    def logout(self):
        """退出登录"""
        try:
            self._click_logout_button()
            # assert self._get_logout_popup_message() in '确认要退出登录？'
            self._click_confirm_logout()
        except Exception as e:
            self._handle_error(f"退出登录失败: {str(e)}", "退出登录失败")
