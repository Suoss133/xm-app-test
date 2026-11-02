import allure
from apps.base.base_add_device_page import BaseAddDevicePage
from core.yaml_utils import YamlUtils
from utils.logger import logger
from appium.webdriver.common.appiumby import AppiumBy


class AddDevicePage(BaseAddDevicePage):

    # 首页弹窗选择设备
    POPUP_DEVICE = (AppiumBy.XPATH, "//android.widget.TextView[@resource-id='com.xm.support.android:id/tv_name']")
    POPUP_DEVICES_ADD_BUTTON = (AppiumBy.XPATH, "//android.widget.TextView[@resource-id='com.xm.support.android:id/tv_add']")


    def __init__(self):
        super().__init__(
            page_name="添加设备页",
            config_path="apps/Koocam/config.yaml",
            page_config_name="add_device"
        )

    # 点击找不到二维码按钮
    def click_no_find_qrcode_btn(self):
        """
        点击找不到二维码按钮
        :return:
        """
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 点击找不到二维码按钮"):
                self.click(self.elements["no_find_qrcode_btn"])
                logger.info("成功点击找不到二维码按钮")
        except Exception as e:
            with allure.step(f"执行时间：{current_time} ---- 点击找不到二维码按钮失败"):
                self._handle_error(f"点击找不到二维码按钮失败: {e}", "点击找不到二维码按钮失败")

    # 选择设备类型
    def select_device_type(self, device_type):
        """
        选择设备类型
        :param device_type: 设备类型
        :return:
        """
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["device_type"],
            device_type
        )
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 选择设备类型：【{device_type}】"):
                self.click(locator)
                logger.info(f"成功点击设备类型: {device_type}")
        except Exception as e:
            error_msg = f"找不到设备类型：【{device_type}】: {str(e)}"
            with allure.step(f"执行时间：{current_time} ---- 找不到设备类型：【{device_type}】"):
                self._handle_error(error_msg, f"找不到设备类型_{device_type}_{current_time}")
    # 选择设备
    def select_device_name(self, device_name):
        """
        点击选择设备
        :param device_name: 设备名称
        :return:
        """
        # 指定目标设备元素
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["device_name"],
            device_name
        )
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击选择设备按钮"):
                self.click(locator)
        except Exception as e:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击选择设备按钮失败"):
                self._handle_error(f"点击选择设备按钮失败：{e}", "点击选择设备按钮失败")

    def get_popup_devices(self):
        """
        获取弹窗中的所有设备列表
        Returns:
            list: 包含设备信息的字典列表，每个字典包含 'element'、'id' 和 'index' 键
        """
        try:
            device_elements = self.find_elements(self.POPUP_DEVICE)
            devices = []

            for i, element in enumerate(device_elements):
                device_id = element.text
                devices.append({
                    "element": element,
                    "id": device_id,
                    "index": i + 1,  # index从1开始
                })

            logger.info(f"弹窗中找到 {len(devices)} 个设备: {[d['id'] for d in devices]}")
            return devices
        except Exception as e:
            self._handle_error(f"获取弹窗中的设备列表失败: {str(e)}", "获取弹窗设备列表失败")

    def get_popup_device_add_buttons(self):
        """
        获取弹窗中的添加设备按钮
        Returns:
            list: 设备添加按钮元素列表
        """
        try:
            add_buttons = self.find_elements(self.POPUP_DEVICES_ADD_BUTTON)
            logger.info(f"弹窗中找到 {len(add_buttons)} 个添加按钮")
            return add_buttons
        except Exception as e:
            self._handle_error(f"获取弹窗设备添加按钮列表失败: {str(e)}", "获取弹窗添加按钮失败")

    def click_popup_device_add_button_by_index(self, index):
        """
        根据索引点击弹窗中的添加设备按钮
        Args:
            index (int): 设备索引（从1开始）
        """
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 选择弹窗中指定设备添加按钮"):
                add_buttons = self.get_popup_device_add_buttons()
                if 1 <= index <= len(add_buttons):
                    add_buttons[index - 1].click()  # 转换为0基索引
                    logger.info(f"成功点击弹窗第 {index} 个添加按钮")
                else:
                    error_msg = f"弹窗中不存在第 {index} 个添加按钮，总共有 {len(add_buttons)} 个按钮"
                    self._handle_error(error_msg, f"点击弹窗添加设备按钮失败_{current_time}")
        except Exception as e:
            self._handle_error(f"点击弹窗第 {index} 个添加按钮失败: {str(e)}", f"点击弹窗添加设备按钮失败_{current_time}")

    def select_device_from_popup(self, target_device_id):
        """
        从弹窗中选择指定设备并点击添加按钮
        Args:
            target_device_id (str): 目标设备的ID
        Returns:
            bool: 成功选择设备并点击添加按钮返回True，否则返回False
        """
        try:
            # 获取弹窗中的所有设备列表
            devices = self.get_popup_devices()
            if not devices:
                logger.warning("弹窗中无设备")
                return False

            # 查找目标设备
            target_device_index = -1
            for device in devices:
                if device["id"] == target_device_id:
                    target_device_index = device["index"]
                    break

            if target_device_index == -1:
                logger.warning(f"弹窗中未找到目标设备: {target_device_id}")
                available_devices = [d['id'] for d in devices]
                logger.info(f"弹窗中可用设备: {available_devices}")
                return False

            # 点击对应设备的添加按钮
            self.click_popup_device_add_button_by_index(target_device_index)
            logger.info(f"成功选择设备 {target_device_id} 并点击添加按钮")
            return True
        except Exception as e:
            self._handle_error(f"选择设备并点击添加按钮失败: {str(e)}", "选择设备添加按钮失败")
            return False
