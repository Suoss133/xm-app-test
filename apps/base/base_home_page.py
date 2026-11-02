import time
import allure
from selenium.webdriver.support.wait import WebDriverWait

from core.base_page import BasePage
from core.yaml_utils import YamlUtils
from core.result import StepResult, FailureType
from utils.logger import logger
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class BaseHomePage(BasePage):
    """首页基类"""
    def __init__(self, page_name, config_path, page_config_name, handle_popup=False):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)
        self.handle_popup = handle_popup

        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        self.ADD_DEVICE_BUTTON = YamlUtils.parse_locator(self.elements["add_device_button"])
        self.HOME_PAGE_IDENTIFIER = YamlUtils.parse_locator(self.elements["home_page_identifier"])


    def click_play_video_button(self, device_name):
        """
        选择指定设备播放视频按钮
        :param device_name: 设备名称
        """

        locator = YamlUtils.parse_dynamic_locator(
            self.elements["live_button"],
            device_name
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击视频播放"):
                self.click(locator, handle_popup=self.handle_popup)
                logger.info("首页点击视频播放")
        except Exception as e:
            self._handle_error(f"点击视频播放按钮失败: {str(e)}", "点击视频播放按钮失败")

    def click_event_button(self, device_name):
        """选择指定设备事件按钮"""
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["event_button"],
            device_name
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击设备事件按钮"):
                self.click(locator, handle_popup=True)
        except Exception as e:
            self._handle_error(f"点击设备事件按钮失败: {str(e)}", "点击设备事件按钮失败")


    def click_add_device_button(self) -> StepResult:
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击添加设备按钮"):
                self.click(self.ADD_DEVICE_BUTTON, handle_popup=self.handle_popup)
                logger.info("点击添加设备按钮成功")
                return StepResult.ok()
        except Exception as e:
            return self._handle_error(
                f"点击添加设备按钮失败: {str(e)}",
                "点击添加设备按钮失败",
                raise_exception=False,
                failure_type=FailureType.ELEMENT_NOT_FOUND,
            )

    def click_live_button(self, device_name: str) -> StepResult:
        locator = YamlUtils.parse_dynamic_locator(self.elements["live_button"], device_name)
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击视频播放"):
                self.click(locator, handle_popup=self.handle_popup)
                logger.info(f"点击设备 {device_name} 直播按钮成功")
                return StepResult.ok()
        except Exception as e:
            return self._handle_error(
                f"点击视频播放按钮失败: {str(e)}",
                "点击视频播放按钮失败",
                raise_exception=False,
                failure_type=FailureType.ELEMENT_NOT_FOUND,
            )

    def click_setting_button(self, device_name: str) -> StepResult:
        locator = YamlUtils.parse_dynamic_locator(self.elements["setting_device_button"], device_name)
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击设备设置按钮"):
                self.click(locator, handle_popup=self.handle_popup)
                logger.info(f"点击设备 {device_name} 设置按钮成功")
                return StepResult.ok()
        except Exception as e:
            return self._handle_error(
                f"点击设备设置按钮失败: {str(e)}",
                "点击设备设置按钮失败",
                raise_exception=False,
                failure_type=FailureType.ELEMENT_NOT_FOUND,
            )

    # 关闭提示弹窗
    def close_popup(self) -> StepResult:
        close_popup = YamlUtils.parse_locator(self.elements["close_popup"])

        if not self.is_element_visible(close_popup):
            logger.info("没有提示弹窗")
            return StepResult.ok()

        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 关闭提示弹窗"):
                # 等待元素可点击（用显式等待）
                element = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(close_popup)
                )
                element.click()  # 直接用等待返回的元素点击，更可靠
                logger.info("关闭提示弹窗成功")
                return StepResult.ok()
        except TimeoutException:
            logger.warning("弹窗元素不可点击，跳过")
            return StepResult.ok(message="弹窗不可点击但继续")
        except Exception as e:
            logger.warning(f"关闭弹窗失败（可忽略）: {e}")
            return StepResult.ok(message="弹窗关闭失败但继续")

    def back_to_home(self) -> StepResult:
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 返回首页"):
                self._back_to_home()
                return StepResult.ok()
        except Exception as e:
            return self._handle_error(
                f"返回首页失败: {str(e)}",
                "返回首页失败",
                raise_exception=False,
                failure_type=FailureType.UNKNOWN,
            )