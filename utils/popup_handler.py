import time
import yaml
import os
from appium.webdriver.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from utils.logger import logger
from appium.webdriver.common.appiumby import AppiumBy
from core.driver import DriverManager


class PopupHandler:
    """支持多 App 差异化定位的异常弹窗处理类"""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.check_timeout = 1  # 检查弹窗的超时时间（秒）
        self.handled_popups = {}  # 记录已处理弹窗：{弹窗名称: 处理时间戳}
        self.cooldown_seconds = 3  # 冷却时间

        # 获取当前执行的 App 名称 (需确保 driver.py 中有 get_current_app 方法)
        self.current_app = DriverManager.get_current_app()

        # 动态加载当前 App 对应的弹窗配置
        self.popup_config = self._load_current_app_config()

        # 定义权限类弹窗名称列表
        self.permission_popup_names = ["camera_permission", "location_permission", "bluetooth_permission"]

    def _load_current_app_config(self):
        """从 YAML 加载当前 App 专属的弹窗配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "popups.yaml"
        )
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)

            # 路径：apps -> [App名称] -> popups
            app_popups = full_config.get("apps", {}).get(self.current_app, {}).get("popups", {})

            if not app_popups:
                logger.warning(f"⚠️ 在 popups.yaml 中未找到 App '{self.current_app}' 的配置，请检查配置项")
            else:
                logger.info(f"✅ 成功加载 App '{self.current_app}' 的专属弹窗配置")

            return app_popups
        except Exception as e:
            logger.error(f"❌ 加载弹窗配置文件出错: {str(e)}")
            return {}

    def handle_popups(self):
        """遍历当前 App 的配置并处理出现的弹窗"""
        if not self.popup_config:
            return False

        current_time = time.time()

        for popup_name, popup_info in self.popup_config.items():
            # 冷却时间检查：避免同一个弹窗在短时间内反复处理导致死循环
            if popup_name in self.handled_popups:
                if current_time - self.handled_popups[popup_name] < self.cooldown_seconds:
                    continue

            try:
                # 1. 探测弹窗主体是否存在
                loc = popup_info['locator']
                locator = (getattr(AppiumBy, loc['by'].upper()), loc['value'])

                # 使用隐式等待或短时间的显示等待
                WebDriverWait(self.driver, self.check_timeout).until(
                    EC.presence_of_element_located(locator)
                )

                logger.info(f"🔔 检测到弹窗: {popup_name} (当前 App: {self.current_app})")

                # 2. 点击处理按钮（关闭或允许）
                btn_info = popup_info['handle_button']
                handle_locator = (getattr(AppiumBy, btn_info['by'].upper()), btn_info['value'])

                handle_button = WebDriverWait(self.driver, self.check_timeout).until(
                    EC.element_to_be_clickable(handle_locator)
                )
                handle_button.click()
                logger.info(f"✨ 动作执行: {popup_info.get('action', '点击关闭')}")

                # 3. 记录处理时间并验证消失
                self.handled_popups[popup_name] = current_time

                # 等待弹窗消失
                try:
                    WebDriverWait(self.driver, 2).until(EC.invisibility_of_element_located(locator))
                except:
                    pass

                # 如果是系统权限申请，通常处理一个后会弹下一个，直接返回 True 触发下一轮检查
                return True

            except TimeoutException:
                continue  # 当前配置的弹窗未出现，继续检查下一个
            except Exception as e:
                logger.warning(f"⚠️ 处理弹窗 {popup_name} 时发生意外: {str(e)}")
                continue

        return False

    def handle_popups_continuously(self, max_attempts=3):
        """
        连续处理多个弹窗（处理完一个后，可能立马弹出另一个）
        """
        attempts = 0
        any_handled = False
        while attempts < max_attempts:
            if self.handle_popups():
                any_handled = True
                attempts += 1
                time.sleep(0.5)  # 处理完一个后微调，等待下一个可能出现的弹窗
            else:
                break
        return any_handled