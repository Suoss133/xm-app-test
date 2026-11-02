import time
import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from core.base_page import BasePage
from core.yaml_utils import YamlUtils
from core.result import StepResult, FailureType
from utils.logger import logger


class BaseAddDevicePage(BasePage):
    """添加设备基类"""

    def __init__(self, page_name, config_path, page_config_name):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)

        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        self.BLUETOOTH_DEVICE = YamlUtils.parse_locator(self.elements["select_bluetooth_device"])
        self.SELECT_MY_NETWORK_BUTTON = YamlUtils.parse_locator(self.elements["select_my_network"])
        self.ENTER_WIFI_PASSWORD = YamlUtils.parse_locator(self.elements["input_wifi_password"])
        self.JOIN_WIFI_BUTTON = YamlUtils.parse_locator(self.elements["join_wifi_button"])
        self.BLUETOOTH_PAGE_IDENTIFIER = YamlUtils.parse_locator(self.elements["bluetooth_page_identifier"])
        self.WIFI_PAGE_IDENTIFIER = YamlUtils.parse_locator(self.elements["wifi_page_identifier"])
        self.CONNECT_PAGE_IDENTIFIER = YamlUtils.parse_locator(self.elements["connect_page_identifier"])
        self.CONNECT_SUCCESS_TEXT = YamlUtils.parse_locator(self.elements["connect_success"])
        self.CONNECT_SUCCESS_INFO2 = YamlUtils.parse_locator(self.elements["connect_success_info2"])
        self.CONNECT_FAILED_TEXT = YamlUtils.parse_locator(self.elements["connect_failed"])
        self.WIFI_PASSWORD_INPUT = YamlUtils.parse_locator(self.elements["input_wifi_password"])
        self.MANUAL_WIFI_BUTTON = YamlUtils.parse_locator(self.elements["manual_input_wifi_button"])
        self.WIFI_NAME_INPUT = YamlUtils.parse_locator(self.elements["input_wifi_name"])
        self.confirm_join_wifi_button = YamlUtils.parse_locator(self.elements["confirm_join_wifi"])
        self.LOADING = YamlUtils.parse_locator(self.elements["loading"])
        self.input_device_name = YamlUtils.parse_locator(self.elements["input_device_name"])
        self.confirm_device_name_button = YamlUtils.parse_locator(self.elements["confirm_device_name_button"])
        self.guide_install = YamlUtils.parse_locator(self.elements["install_guide"])
        self.close_install_guide = YamlUtils.parse_locator(self.elements["close_install_guide"])

    def wait_for_loading_to_disappear(self, timeout=60, poll_interval=2) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_element_visible(self.LOADING):
                logger.info("加载完成")
                return True
            time.sleep(poll_interval)
        return False

    # 选择蓝牙设备
    def select_bluetooth_device(self, bluetooth_device_id, timeout=60):
        """选择指定的蓝牙设备"""
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time}---- 选择蓝牙设备:【{bluetooth_device_id}】"):
                # 等待目标蓝牙设备出现
                target_device_element = self._wait_for_bluetooth_device(bluetooth_device_id, timeout)
                # 点击选择该设备
                target_device_element.click()
                logger.info(f"成功选择蓝牙设备: '{bluetooth_device_id}'")
                return True
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 找不到定蓝牙设备，请确认是否已开启"):
                self._handle_error(f"选择蓝牙设备失败: {str(e)}", f"选择蓝牙设备失败_{self.get_current_time()}")
    # 选择我的网络
    def click_select_my_network_button(self):
        """点击选择我的Wi-Fi设备按钮"""
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 选择我的网络"):
                element = self.wait_for_element_indefinitely(self.SELECT_MY_NETWORK_BUTTON)
                element.click()
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 找不到我的网络"):
                self._handle_error(f"选择我的网络失败: {str(e)}", f"选择我的网络失败_{self.get_current_time()}")
    # 输入Wi-Fi密码
    def enter_wifi_password(self, password="12345678"):
        """输入Wi-Fi密码"""
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 输入Wi-Fi密码"):
                self.send_keys(self.ENTER_WIFI_PASSWORD, password)
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 未连接正确的Wi-Fi名称或密码错误"):
                self._handle_error(f"输入Wi-Fi密码失败: {str(e)}", f"输入Wi-Fi密码失败_{self.get_current_time()}")

    def check_network_config_status(self, device_name: str, timeout: int = 300, poll_interval: int = 1) -> StepResult:
        start_time = time.time()
        logger.info(f"开始监控配网页面，超时 {timeout}s")

        while time.time() - start_time < timeout:
            if not self.is_element_visible(self.CONNECT_PAGE_IDENTIFIER):
                logger.info("配网流程结束，等待结果页渲染...")
                self._take_screenshot("配网结束截图")
                return self._check_config_result(device_name)
            time.sleep(poll_interval)

        msg = f"配网超时（{timeout}秒），页面未关闭"
        self._take_screenshot("配网超时")
        return StepResult.fail(FailureType.NETWORK_CONFIG_FAILED, msg)

    def select_network(self, wifi_ssid: str, wifi_password: str) -> StepResult:
        self.wait_for_loading_to_disappear()
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 手动输入WiFi"):
                self._input_wifi(wifi_ssid, wifi_password)
                self._join_wifi()
                self.confirm_join_wifi()
                logger.info(f"成功输入WiFi并尝试连接: {wifi_ssid}")
                return StepResult.ok()
        except Exception as e:
            msg = f"手动输入WiFi失败: {wifi_ssid}，错误: {str(e)}"
            self._take_screenshot(f"手动输入WiFi失败_{wifi_ssid}")
            return StepResult.fail(FailureType.NETWORK_CONFIG_FAILED, msg)

    def _join_wifi(self):
        self.click(self.JOIN_WIFI_BUTTON)

    def confirm_join_wifi(self):
        self.click(self.confirm_join_wifi_button)

    def _check_config_result(self, device_name: str) -> StepResult:
        if (self.is_element_visible(self.CONNECT_SUCCESS_TEXT) or
                self.is_element_visible(self.CONNECT_SUCCESS_INFO2)):
            logger.info("设备配网成功")
            with allure.step(f"执行时间：{self.get_current_time()} ---- 设备配网成功【{device_name}】"):
                pass
            return StepResult.ok(data={"text": "连接成功"})

        # 失败分支
        try:
            error_text = self.get_text(self.CONNECT_FAILED_TEXT).strip()
        except Exception:
            error_text = "未知配网错误"

        msg = f"设备配网失败: {error_text}"
        self._take_screenshot(f"设备配网失败_{device_name}")
        logger.error(msg)

        return StepResult.fail(
            FailureType.NETWORK_CONFIG_FAILED,
            msg,
            data={"text": error_text}
        )

    def _input_wifi(self, wifi_ssid: str, wifi_password: str):
        self.click(self.MANUAL_WIFI_BUTTON)
        self.send_keys(self.WIFI_NAME_INPUT, wifi_ssid)
        self.send_keys(self.WIFI_PASSWORD_INPUT, wifi_password)

    def _wait_for_bluetooth_device(self, device_id, timeout=60):
        """
        等待指定蓝牙设备出现

        Args:
            device_id (str): 目标蓝牙设备ID
            timeout (int, optional): 超时时间（秒），默认60秒

        Returns:
            WebElement: 找到的目标蓝牙设备元素对象
        """

        try:
            logger.info(f"开始等待蓝牙设备出现: '{device_id}'")
            logger.info(f"设置超时时间: {timeout}秒")

            # 记录开始时间
            start_time = time.time()

            # 持续轮询检查目标蓝牙设备是否存在
            while True:
                # 检查是否超时
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    error_msg = f"等待蓝牙设备超时 ({timeout}秒): '{device_id}'"
                    logger.error(error_msg)
                    raise AssertionError(error_msg)

                try:
                    # 查找所有蓝牙设备元素
                    device_elements = self.find_elements(self.BLUETOOTH_DEVICE)
                    logger.debug(f"找到 {len(device_elements)} 个蓝牙设备元素")

                    # 遍历所有设备元素，查找目标设备
                    for element in device_elements:
                        try:
                            # 获取设备元素的文本
                            element_text = element.text.strip()
                            logger.debug(f"检查设备: '{element_text}'")

                            # 精确匹配或包含匹配设备名称
                            if element_text and (element_text == device_id or device_id in element_text):
                                logger.info(f"找到目标蓝牙设备: '{device_id}'")
                                return element

                        except Exception as e:
                            logger.debug(f"获取设备元素文本时出错: {str(e)}")
                            continue

                except Exception as e:
                    logger.debug(f"查找蓝牙设备元素时出错: {str(e)}")

                # 短暂休眠后继续检查
                time.sleep(self.poll_frequency)

        except Exception as e:
            error_msg = f"等待蓝牙设备失败: '{device_id}', 错误: {str(e)}"
            logger.error(error_msg)

    def select_device_by_sn(self, device_sn: str, timeout: int = 120) -> StepResult:
        """根据 SN 选择蓝牙设备"""
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["select_bluetooth_device_sn"], device_sn
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 选择设备SN: {device_sn}"):
                element = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(locator)
                )
                element.click()
                logger.info(f"已成功选择设备 SN: {device_sn}")
                return StepResult.ok()
        except TimeoutException:
            msg = f"根据SN选择设备超时({timeout}秒): {device_sn}，请检查设备是否在配网状态"
            self._take_screenshot(f"选择蓝牙设备超时_{device_sn}")
            return StepResult.fail(FailureType.DEVICE_NOT_FOUND, msg)
        except Exception as e:
            msg = f"根据SN选择设备失败: {device_sn}，错误: {str(e)}"
            self._take_screenshot(f"选择蓝牙设备失败_{device_sn}")
            return StepResult.fail(FailureType.DEVICE_NOT_FOUND, msg)

    # 断言蓝牙设备是否重新开启
    def assert_device_auto_open_bluetooth(self, device_sn):
        """
        断言设备蓝牙未自动开启（即指定SN的设备不应在列表中可见）
        如果 is_element_visible 返回 True，说明设备意外出现，断言失败
        
        Args:
            device_sn (str): 设备SN
        """
        current_time = self.get_current_time()
        try:
            # 指定目标设备SN
            locator = YamlUtils.parse_dynamic_locator(
                self.elements["select_bluetooth_device_sn"],
                device_sn
            )
            is_visible = self.is_element_visible(locator)

            if is_visible:
                # 如果元素可见，说明设备意外出现在列表中，断言失败
                error_msg = f"设备 {device_sn} 意外出现在蓝牙列表中"
                logger.error(error_msg)
                raise AssertionError(error_msg)
            else:
                # 元素不可见，符合预期，断言成功
                logger.info(f"断言成功: 设备 {device_sn} 未在蓝牙列表中出现")
                    
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 断言设备蓝牙状态异常"):
                self._handle_error(f"断言设备蓝牙状态异常: {str(e)}", f"断言设备蓝牙状态异常")

    # 选择蓝牙设备 坐标点击实现
    def select_device_by_coordinate(self, sn):
        """根据坐标选择设备"""
        sn_locator = (AppiumBy.XPATH,	"//android.widget.TextView[@resource-id='com.koobird.android:id/tv_dev_name']")
        time.sleep(2)
        self.tap_at_coordinates(188, 671)
        self.wait_for_loading_to_disappear()
        time.sleep(2)
        self.tap_at_coordinates(358, 1500)
        time.sleep(1)
        self.tap_at_coordinates(358, 1500)
        time.sleep(1)
        self.tap_at_coordinates(358, 1500)

        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 选择蓝牙"):
                old_sn = self.get_text(sn_locator)
                if sn in old_sn:
                    self.click(sn_locator)
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 根据坐标选择设备失败"):
                self._handle_error(f"根据坐标选择设备失败: {str(e)}", f"根据坐标选择设备失败_{self.get_current_time()}")

    # 根据设备型号选择蓝牙设备
    def select_device_by_model(self, model):
        """根据设备型号选择蓝牙设备"""
        pass

    def set_device_name(self, device_name: str) -> StepResult:
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 设置设备名称 {device_name}"):
                self.send_keys(self.input_device_name, device_name)
                self.click(self.confirm_device_name_button)
                logger.info(f"已设置设备名称: {device_name}")
                return StepResult.ok()
        except Exception as e:
            msg = f"设置设备名称失败: {device_name}，错误: {str(e)}"
            self._take_screenshot(f"设置设备名称失败_{device_name}")
            return StepResult.fail(FailureType.ELEMENT_NOT_FOUND, msg)

    def auto_close_install_guide(self, should_handle: bool = True) -> StepResult:
        if not should_handle:
            return StepResult.ok()
        try:
            page_title = self.get_text(self.guide_install)
            if page_title == "安装向导":
                self.click(self.close_install_guide)
                logger.info("成功关闭安装向导")
            return StepResult.ok()
        except Exception as e:
            logger.warning(f"处理安装向导异常（可忽略）: {e}")
            return StepResult.ok(message="安装向导处理异常但继续")

