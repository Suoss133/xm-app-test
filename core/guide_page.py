# 点击下一步下一步引导通用页面
import time

from appium.webdriver.common.appiumby import AppiumBy
from core.base_page import BasePage
from utils.logger import logger
import allure


class GuidePage(BasePage):
    """引导页面基类，用于校验页面文字"""

    def __init__(self, page_name="guide_page"):
        super().__init__(page_name)
        self.text_locator = None

    def set_text_locator(self, text_locator):
        """
        设置文字定位器
        :param text_locator: 定位器元组
        """
        self.text_locator = text_locator

    def verify_text(self, expected_text):
        """
        校验页面文字（核心行为）
        :param expected_text: 期望的文字内容
        :return: 校验成功返回True，失败抛出异常
        """
        try:
            if not self.text_locator:
                raise ValueError("未设置文字定位器，请先调用 set_text_locator 方法")

            actual_text = self.get_text(self.text_locator)
            assert actual_text == expected_text, f"文字校验失败：预期 '{expected_text}'，实际 '{actual_text}'"
            logger.info(f"文字校验成功: '{expected_text}'")
            return True
        except Exception as e:
            logger.error(f"文字校验失败: {str(e)}")
            raise

    def verify_text_contains(self, expected_text):
        """
        校验页面文字是否包含指定内容
        :param expected_text: 期望包含的文字内容
        :return: 校验成功返回True，失败抛出异常
        """
        try:
            if not self.text_locator:
                raise ValueError("未设置文字定位器，请先调用 set_text_locator 方法")

            actual_text = self.get_text(self.text_locator)
            assert expected_text in actual_text, f"文字校验失败：期望包含 '{expected_text}'，实际 '{actual_text}'"
            logger.info(f"文字包含校验成功: '{actual_text}' 包含 '{expected_text}'")
            return True
        except Exception as e:
            logger.error(f"文字包含校验失败: {str(e)}")
            raise


# 具体设备页面类
class DeviceGuidePage(GuidePage):
    """设备引导页面类"""

    # 设备特定的页面文字定位器和预期文字
    DEVICE_PAGE_INFO = {
        "Cam Kit": {
            "locator": (AppiumBy.XPATH,
                        "//android.widget.TextView[@text='1. 使用包装内原装12V/2A电源适配器连接基站和电源']"),
            "expected_text": "1. 使用包装内原装12V/2A电源适配器连接基站和电源"
        },
        "Pan Tilt Camera": {
            "locator": (AppiumBy.XPATH,
                        "//android.view.View[@text='长按底部“开机键”3s，直到听到开机语音播报，摄像机蓝灯亮起，设备开机']"),
            "expected_text": "长按底部“开机键”3s，直到听到开机语音播报，摄像机蓝灯亮起，设备开机"
        },
        "Video Doorbell": {
            "locator": (AppiumBy.XPATH,
                        "//android.view.View[@text='Plug in the Chime Pro. The red light will stay on at first. Wait until the top blue light starts blinking. *If the blue light doesn’t blink, double-press the top button.']"),
            "expected_text": "Plug in the Chime Pro. The red light will stay on at first. Wait until the top blue light starts blinking. *If the blue light doesn’t blink, double-press the top button."
        },
        "Battery Camera": {
            "locator": (AppiumBy.XPATH,
                        "//android.view.View[@text 'Locate the illustrated button on the body and press it for 3 seconds until the white light flashes']"),
            "expected_text": "Locate the illustrated button on the body and press it for 3 seconds until the white light flashes"
        },
        "Baby Monitor": {
            "locator": (AppiumBy.XPATH,
                        "//android.widget.TextView[@text='开机后，请耐心等待15S左右，直到摄像机红灯闪烁']"),
            "expected_text": "开机后，请耐心等待15S左右，直到摄像机红灯闪烁"
        },
        "Window Camera": {
            "locator": (AppiumBy.XPATH, "//android.view.View[@text='请将摄像机接入电源，通电后蓝灯会常亮3s']"),
            "expected_text": "请将摄像机接入电源，通电后蓝灯会常亮3s"
        }
    }

    FIRST_STEP_BUTTON = (AppiumBy.XPATH, "//android.view.View[@text='下一步']")


    def __init__(self, page_name="device_guide_page"):
        super().__init__(page_name)

    def verify_device_page_by_name(self, device_type):
        """
        根据设备名称校验设备引导页面
        :param device_type: 设备类型
        :return: 校验结果
        """
        try:
            normalized_name = device_type.strip()

            # 查找对应的设备信息
            device_info = None
            for key, info in self.DEVICE_PAGE_INFO.items():
                if key.lower() == normalized_name.lower():
                    device_info = info
                    break

            if not device_info:
                available_devices = list(self.DEVICE_PAGE_INFO.keys())
                raise ValueError(f"未找到设备类型 '{device_type}' 的页面信息。可用设备: {available_devices}")

            # 设置定位器
            self.set_text_locator(device_info["locator"])
            # 校验页面文字
            return self.verify_text(device_info["expected_text"])
        except Exception as e:
            logger.error(f"设备页面校验失败: {str(e)}")
            raise

    def verify_and_click_next(self, device_type):
        """
        点击下一步按钮
        :param device_type: 设备类型
        :return: 校验结果
        """
        current_time = self.get_current_time()
        try:
            # 校验跳转设备引导页面是否正确
            verify_result = self.verify_device_page_by_name(device_type)

            # 校验成功
            if verify_result:
                center_x, center_y = self.get_element_center(self. FIRST_STEP_BUTTON)
                self.tap_at_coordinates(center_x, center_y)
                time.sleep(1)
                self.tap_at_coordinates(center_x, center_y)
                return True
            else:
                logger.warning(f"设备页面校验失败")
                self._take_screenshot(name=f"截图时间：{current_time} ---- 跳转到下一步引导页面错误")
                return False
        except Exception as e:
            with allure.step(f"执行时间：{current_time} ---- 校验失败"):
                logger.warning(e)
                return False