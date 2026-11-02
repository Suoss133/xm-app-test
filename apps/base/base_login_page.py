import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.wait import WebDriverWait

from core.base_page import BasePage
from core.yaml_utils import YamlUtils
from utils.logger import logger


class BaseLoginPage(BasePage):
    """登录页基类"""
    def __init__(self, page_name, config_path, page_config_name,handle_popup=False):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)
        self.handle_popup = handle_popup

        # 加载当前App的页面元素配置
        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        # 定义基础页面元素
        self.EMAIL_INPUT = YamlUtils.parse_locator(self.elements["email_input"])
        self.PASSWORD_INPUT = YamlUtils.parse_locator(self.elements["password_input"])
        self.REMEMBER_PASSWORD = YamlUtils.parse_locator(self.elements["remember_password"])
        self.LOGIN_BUTTON = YamlUtils.parse_locator(self.elements["login_button"])
        self.REGISTER_ACCOUNT = YamlUtils.parse_locator(self.elements["register_account"])
        self.USER_AGREE = YamlUtils.parse_locator(self.elements["user_agree"])
        self.EMAIL_ERROR_MESSAGE = YamlUtils.parse_locator(self.elements["email_error_message"])
        self.SYSTEM_WINDOW_MESSAGE = YamlUtils.parse_locator(self.elements["system_window_message"])
        self.CLOSE_SYSTEM_WINDOW = YamlUtils.parse_locator(self.elements["close_system_window"])
        # 默认使用权限
        self.PERMISSION_ALLOW = YamlUtils.parse_locator(self.elements["permission_allow"])

        self.REGION_BUTTON = YamlUtils.parse_locator(self.elements["region_button"])
        self.REGION_INPUT = YamlUtils.parse_locator(self.elements["region_input"])
        self.REGION_SELECT = YamlUtils.parse_locator(self.elements["region_select"])

    # 输入邮箱
    def enter_email(self, email):
        """输入邮箱"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 输入邮箱：{email}"):
                self.send_keys(self.EMAIL_INPUT, email)
        except Exception as e:
            self._handle_error(f"输入邮箱失败: {str(e)}", "输入邮箱失败")
            raise Exception("输入邮箱失败")
    # 输入密码
    def enter_password(self, password):
        """输入密码"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 输入密码：{password}"):
                self.send_keys(self.PASSWORD_INPUT, password)
        except Exception as e:
            self._handle_error(f"输入密码失败: {str(e)}", "输入密码失败")
            raise Exception("输入密码失败")
    # 勾选记住密码
    def check_remember_password(self):
        """勾选记住密码"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 勾选记住密码"):
                self.click(self.REMEMBER_PASSWORD)
        except Exception as e:
            self._handle_error(f"勾选记住密码失败: {str(e)}", "勾选记住密码失败")
            raise Exception("勾选记住密码失败")
    # 勾选用户协议
    def check_user_agree(self):
        """勾选用户协议"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 勾选用户协议"):
                self.click(self.USER_AGREE)
        except Exception as e:
            self._handle_error(f"勾选用户协议失败: {str(e)}", "勾选用户协议失败")
            raise Exception("勾选用户协议失败")
    # 点击登录按钮
    def click_login_button(self):
        """点击登录按钮"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击登录按钮"):
                self.click(self.LOGIN_BUTTON, handle_popup=self.handle_popup)
        except Exception as e:
            self._handle_error(f"点击登录按钮失败: {str(e)}", "点击登录按钮失败")
            raise Exception("点击登录按钮失败")
    # 检测邮箱格式是否正确
    def check_email_error_msg(self,email):
        """检测邮箱格式是否正确"""
        # 触发邮箱格式校验
        try:
            locator = (AppiumBy.XPATH, f"//android.widget.EditText[@text='{email}']")
            self.click(locator)
            with allure.step(f"执行时间：{self.get_current_time()} ---- 检测邮箱格式正确"):
                error_message = self.get_text(self.EMAIL_ERROR_MESSAGE)
                self._take_screenshot("邮箱格式校验正确")
            return error_message
        except Exception as e:
            self._handle_error(f"邮箱格式校验失败: {str(e)}", "邮箱格式校验失败")
            raise Exception("邮箱格式校验失败")
     # 检测用户密码错误
    def check_password_error_msg(self):
        """检测用户密码错误"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 校验输入错误用户密码"):
                error_message = self.get_text(self.SYSTEM_WINDOW_MESSAGE)
                self._take_screenshot("输入错误用户密码截图")
            return error_message
        except Exception as e:
            self._handle_error(f"校验输入错误用户密码失败: {str(e)}", "校验输入错误用户密码失败")
            raise Exception("校验输入错误用户密码失败")
    # 关闭系统弹窗
    def close_system_window(self):
        """关闭系统弹窗"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 关闭系统弹窗"):
                self.click(self.CLOSE_SYSTEM_WINDOW)
        except Exception as e:
            self._handle_error(f"关闭系统弹窗失败: {str(e)}", "关闭系统弹窗失败")
            raise Exception("关闭系统弹窗失败")
    # 确认使用权限
    def confirm_permission(self):
        """确认使用权限"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 确认使用权限"):
                self.click(self.PERMISSION_ALLOW)
        except Exception as e:
            self._handle_error(f"确认使用权限失败: {str(e)}", "确认使用权限失败")
            raise Exception("确认使用权限失败")
    # 获取输入框邮箱信息
    def get_email_input_text(self,email_input):
        """获取输入框邮箱信息"""
        try:
            locator = (AppiumBy.XPATH, f'//android.widget.EditText[@text="{email_input}"]')
            return self.get_text(locator)
        except Exception as e:
            self._handle_error(f"记住用户名失败: {str(e)}", "记住用户名失败")
            raise Exception("记住用户邮箱失败")
    # 获取输入框密码信息
    def get_password_input_text(self,password_input):
        """获取输入框密码信息"""
        try:
            locator = (AppiumBy.XPATH, f'//android.widget.EditText[@text="{password_input}"]')
            return self.get_text(locator)
        except Exception as e:
            self._handle_error(f"记住用户名失败: {str(e)}", "记住用户名失败")
            raise Exception("记住用户邮箱失败")
        return self.get_text(self.PASSWORD_INPUT)
    # 验证邮箱格式数据
    def verify_email_format(self):
        """验证邮箱格式数据"""
        return [
            {"email": "111111.com"},
            {"email": "111111@"}
        ]
    # 地区选择
    def select_region(self,region_name):
        """
        地区选择
        :return:
        """
        # 第一步 点击地区选择按钮
        self._click_region_button()

        # 第二步 输入框输入地区名称
        self._input_region_name(region_name)

        # 第三步 选择地区
        self._select_region(region_name)

    # 点击地区选择按钮
    def _click_region_button(self):
        """
        点击地区选择按钮
        :return:
        """
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击地区选择按钮"):
                self.click(self.REGION_BUTTON)
                logger.info("点击地区选择按钮")
        except Exception as e:
            self._handle_error(f"点击地区选择按钮失败: {str(e)}", "点击地区选择按钮失败")
            raise Exception("点击地区选择按钮失败")
    # 选择输入框输入地区名称
    def _input_region_name(self,region_name):
        """
        选择输入框输入地区名称
        :return:
        """
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 输入地区名称:{region_name}"):
                self.send_keys(self.REGION_INPUT, region_name)
                logger.info("输入框输入地区名称")

        except Exception as e:
            self._handle_error(f"输入地区名称失败: {str(e)}", "输入地区名称失败")
            raise Exception("输入地区名称失败")
    # 选择地区
    def _select_region(self,region_name):
        """
        选择地区
        :param region_name:
        :return:
        """
        locator = YamlUtils.parse_dynamic_locator(
            self.REGION_SELECT,
            region_name
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 选择地区:{region_name}"):
                self.click(locator)
                logger.info("选择地区")
        except Exception as e:
            self._handle_error(f"选择地区失败: {str(e)}", "选择地区失败")
            raise Exception("选择地区失败")