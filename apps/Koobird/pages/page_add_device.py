import time

import allure
from apps.base.base_add_device_page import BaseAddDevicePage
from core.yaml_utils import YamlUtils
from utils.logger import logger
from appium.webdriver.common.appiumby import AppiumBy


class AddDevicePage(BaseAddDevicePage):


    def __init__(self):
        super().__init__(
            page_name="添加设备页",
            config_path="apps/koobird/config.yaml",
            page_config_name="add_device"
        )

        self.device_list = YamlUtils.parse_locator(self.elements["device_list"])

        self.BLUETOOTH_DEVICE = None

    # 选择指定设备
    def select_device(self, device_name):
        """选择指定设备"""
        try:
            device_list = self.find_elements(self.device_list)
            for device in device_list:
                if device.text == device_name:
                    with allure.step(f"执行时间：{self.get_current_time()} ---- 选择设备{device_name}"):
                        self._take_screenshot("选择设备")
                        device.click()
                    logger.info(f"选择设备：{device_name}")
                    return
        except Exception as e:
            logger.error(f"选择设备失败：{e}")
            with allure.step(f"执行时间：{self.get_current_time()} ---- 找不到定蓝牙设备，请确认是否已开启配网状态"):
                self._handle_error(f"选择蓝牙设备失败: {str(e)}", f"选择蓝牙设备失败_{self.get_current_time()}")

    def select_network(self, wifi_ssid, wifi_password):
        """直接手动输入WiFi名称和密码"""
        self.wait_for_loading_to_disappear()
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 输入wifi名称{wifi_ssid}:wifi密码{wifi_password}"):
                logger.info(f"开始手动输入WiFi: {wifi_ssid}")
                self._input_wifi(wifi_ssid, wifi_password)
                self._join_wifi()
                logger.info(f"成功输入WiFi信息并尝试连接: {wifi_ssid}")
                return True
        except Exception as e:
            logger.error(f"手动输入WiFi失败: {str(e)}")
            with allure.step(f"执行时间：{self.get_current_time()} ---- 手动输入WiFi失败"):
                self._handle_error(f"手动输入WiFi失败: {str(e)}", f"手动输入WiFi失败_{self.get_current_time()}")
            return False

    # 加入Wi-Fi
    def _join_wifi(self):
        """点击加入Wi-Fi按钮"""
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 加入Wi-Fi"):
                self.click(self.JOIN_WIFI_BUTTON)
                logger.info("点击加入")
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 加入Wi-Fi失败"):
                self._handle_error(f"加入Wi-Fi失败: {str(e)}", f"加入Wi-Fi失败_{self.get_current_time()}")


    def select_device_by_sn(self, device_sn):
        """根据SN选择设备"""
        """根据坐标选择设备"""
        self.BLUETOOTH_DEVICE = (AppiumBy.XPATH, f'//android.widget.TextView[@resource-id="com.koobird.android:id/tv_dev_name" and @text="{device_sn}"]')
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
                old_sn = self.get_text(self.BLUETOOTH_DEVICE)
                if device_sn in old_sn:
                    self.select_bluetooth_device(device_sn)
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 根据坐标选择设备失败"):
                self._handle_error(f"根据坐标选择设备失败: {str(e)}", f"根据坐标选择设备失败_{self.get_current_time()}")


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