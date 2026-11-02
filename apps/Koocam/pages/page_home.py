import allure

from apps.base.base_home_page import BaseHomePage
from core.result import StepResult,FailureType
from core.yaml_utils import YamlUtils
from utils.logger import logger
from appium.webdriver.common.appiumby import AppiumBy


class HomePage(BaseHomePage):

    def __init__(self):
        super().__init__(
            page_name="首页",
            config_path="apps/Koocam/config.yaml",
            page_config_name="home",
            handle_popup=True # 启用弹窗处理
        )

        # 发现新设备弹窗
        self.FIND_NEW_DEVICE_POPUP = YamlUtils.parse_locator(self.elements["find_new_device_popup"])
        self.POPUP_DEVICE_LIST = YamlUtils.parse_locator(self.elements["popup_device_list"])

        # 用户按钮
        self.USER_BUTTON = YamlUtils.parse_locator(self.elements["user_button"])
        # 用户名称
        self.USER_NAME = YamlUtils.parse_dynamic_locator(self.elements["user_name"])

        # 首页设备离线状态
        self.device_staus = (AppiumBy.ID,'com.xm.support.android:id/tv_alarm_tips')

    # 设备是否离线
    def is_device_offline(self, device_name):
        # 重新加载
        reload = (AppiumBy.ID,"com.xm.support.android:id/iv_refresh")
        if self.is_element_visible(self.device_staus):
            logger.error("设备已离线")
            result = self.driver.get_text(self.device_staus)
            return result
        return True

    # 重新加载
    def click_reload(self):
        pass

    # 跳转进入到个人信息页
    def click_user_info_page(self):
        """点击用户信息按钮"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 跳转到个人信息页"):
                self.click(self.USER_NAME)
                logger.info("成功跳转到个人信息页")
        except Exception as e:
            error_msg = f"点击用户名称失败：{e}"
            self._handle_error(error_msg)
    # 点击用户按钮
    def click_user_button(self):
        """点击用户按钮"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击用户按钮"):
                self.click(self.USER_BUTTON)
                logger.info("成功点击用户按钮")
        except Exception as e:
            error_msg = f"点击用户按钮失败：{e}"
            self._handle_error(error_msg)
    # 获取页面唯一标识
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
    # 检查是否出现发现新设备弹窗
    def check_find_new_device_popup(self):
        """检查是否弹出发现新设备弹窗"""
        try:
            result = self.is_element_visible(self.FIND_NEW_DEVICE_POPUP)
            if result:
                logger.info("已弹出发现新设备弹窗")
                return True
            else:
                logger.warning(f"未弹出发现新设备弹窗")
                return False
        except Exception as e:
            self._handle_error(f"检查是否弹出发现新设备弹窗失败: {str(e)}", "检查是否弹出发现新设备弹窗失败")
    # 获取弹窗设备列表
    def _get_popup_device_list(self):
        """获取弹窗设备列表"""
        try:
            device_elements = self.find_elements(self.POPUP_DEVICE_LIST)
            devices = []

            for i, element in enumerate(device_elements):
                device_id = element.text
                devices.append({
                    "element": element,
                    "id": device_id,
                    "index": i + 1
                })

            logger.info(f"弹窗中找到 {len(devices)} 个设备: {[d['id'] for d in devices]}")
            return devices
        except Exception as e:
            self._handle_error(f"获取弹窗设备列表失败: {str(e)}", "获取弹窗设备列表失败")
    def _click_popup_add_device(self, index):
        """
        点击弹窗中的设备添加按钮
        :param index: 设备索引
        :return:
        """
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击弹窗中的设备添加按钮"):
                add_buttons = self.find_elements(self.ADD_DEVICE_BUTTON)
                logger.info(f"弹窗中找到 {len(add_buttons)} 个设备添加按钮")
                return add_buttons
        except Exception as e:
            self._handle_error(f"弹窗中的设备添加按钮失败: {str(e)}", "点击弹窗中的设备添加按钮失败")
    def select_device_from_popup(self, device_id):
        """
        选择弹窗中的设备
        :param device_id: 目标设备ID
        :return:
        """
        try:
            # 获取弹窗中的所有设备列表
            devices = self._get_popup_device_list()
            if not devices:
                logger.warning("首页没有新设备弹窗")
                return False

            # 查找目标设备
            target_device_index = -1
            for device in devices:
                if device["id"] == device_id:
                    target_device_index = device["index"]
                    break

            if target_device_index == -1:
                logger.warning(f"弹窗中未找到目标设备 {device_id}")
                available_devices = [d["id"] for d in devices]
                logger.info(f"弹窗中可用设备列表: {available_devices}")
                return False

            # 点击对应设备的添加按钮
            self._click_popup_add_device(target_device_index)
            logger.info(f"成功已选择设备 {device_id}")
            return True

        except Exception as e:
            self._handle_error(f"选择弹窗中的设备失败: {str(e)}", "选择弹窗中的设备失败")
            return False

    def click_live_button(self,device_name):
        """选择指定设备直播按钮"""
        locator = YamlUtils.parse_dynamic_locator(
            self.elements["live_button"],
            device_name
        )
        try:
            self.click(locator, handle_popup=self.handle_popup)
            logger.info("点击直播播放按钮成功")
            return StepResult.ok()
        except Exception as e:
            self._handle_error(f"点击设备直播按钮失败: {str(e)}",
                               "点击设备直播按钮失败",
                               raise_exception=False,
                               failure_type=FailureType.ELEMENT_NOT_FOUND)






