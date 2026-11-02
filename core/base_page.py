import os
import subprocess
from datetime import datetime
import traceback
import time
import logging

from appium.webdriver.common.appiumby import AppiumBy

from core.driver import DriverManager
from utils.logger import logger
from utils.popup_handler import PopupHandler
from core.result import StepResult, FailureType
from core.exceptions import BusinessFailure, RestartRequired

import allure
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException, InvalidSessionIdException
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput


class ElementFindTimeoutError(Exception):
    pass

class ElementNotFoundException(Exception):
    pass

class ElementOperationError(Exception):
    pass


class BasePage:
    def __init__(self, page_name):
        self.page_name = page_name
        self.driver = DriverManager.get_driver()
        self.popup_handler = PopupHandler(self.driver)
        self.wait_timeout = 20
        self.poll_frequency = 0.5
        self.coordinate_map = {
            "删除设备": (351, 1553)
        }

    def _adb_base_args(self):
        """
        构造 ADB 命令前缀，尽量与当前 Appium 会话设备一致（多设备时避免误操作）。
        """
        serial = os.environ.get("ANDROID_SERIAL")
        if not serial and getattr(self, "driver", None):
            caps = self.driver.capabilities or {}
            serial = (
                caps.get("deviceUDID")
                or caps.get("udid")
                or caps.get("appium:udid")
                or caps.get("appium:deviceName")
            )
        if serial:
            return ["adb", "-s", str(serial)]
        return ["adb"]

    def _find_element(self, locator, handle_popup=False, max_retries=3):
        by, value = locator
        retry_count = 0

        while retry_count < max_retries:
            try:
                DriverManager.heartbeat()
                logger.info(f"[{self.page_name}] 查找元素: {locator}")

                element = DriverManager.safe_find_element(
                    by=by,
                    value=value,
                    timeout=self.wait_timeout,
                    poll_frequency=self.poll_frequency
                )

                if not element.is_displayed():
                    raise ElementNotFoundException(f"元素存在但不可见: {by}={value}")

                return element

            # 先捕获 TimeoutException 和 NoSuchElementException（业务找不到元素）
            except (TimeoutException, NoSuchElementException) as e:
                if handle_popup:
                    logger.warning(f"[{self.page_name}] 首次查找失败，尝试处理弹窗...")
                    if self.popup_handler.handle_popups():
                        DriverManager.heartbeat()
                        try:
                            return DriverManager.safe_find_element(by, value, timeout=8)
                        except Exception as e2:
                            raise ElementFindTimeoutError(f"处理弹窗后仍未找到元素: {by}={value}") from e2

                raise ElementFindTimeoutError(f"元素查找失败: {by}={value}") from e

            # 再捕获其他需要重试的异常（Stale、session 问题等）
            except (StaleElementReferenceException, WebDriverException, InvalidSessionIdException) as e:
                # 排除已经处理过的 TimeoutException
                if isinstance(e, TimeoutException):
                    # 如果意外进到这里，记录并抛出
                    logger.error(f"TimeoutException 意外进入 Stale/WebDriver 分支: {str(e)}")
                    raise ElementFindTimeoutError(f"TimeoutException 未被正确捕获: {by}={value}") from e

                # UiAutomator2 崩溃：优先走恢复逻辑，不计入普通重试
                if self._is_uiautomator2_crashed(e):
                    try:
                        self._recover_uiautomator2()
                        logger.info(f"[{self.page_name}] UiAutomator2 已恢复，重新查找元素: {by}={value}")
                        time.sleep(1.0)
                        continue  # 不计入 retry_count，继续下一次正常查找
                    except RuntimeError:
                        raise ElementFindTimeoutError(f"UiAutomator2 崩溃且恢复失败: {by}={value}") from e

                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"[{self.page_name}] Stale/WebDriver/InvalidSession 异常，重试第 {retry_count} 次")
                    time.sleep(0.5)
                else:
                    raise ElementFindTimeoutError(f"查找元素失败（已重试{max_retries}次）: {by}={value}") from e

    def find_elements(self, locator):
        """查找多个元素"""
        try:
            DriverManager.heartbeat()
            if not isinstance(locator, tuple) or len(locator) != 2:
                raise ValueError("定位器必须是 (by, value) 格式的元组")

            by, value = locator
            elements = self.driver.find_elements(*locator)
            logging.info(f"找到{len(elements)}个元素: {by}={value}")
            return elements
        except Exception as e:
            by, value = locator if isinstance(locator, tuple) and len(locator) == 2 else ("Unknown", "Unknown")
            logging.error(f"查找元素失败: {by}={value}, 错误: {str(e)}")
            raise

    def click(self, locator, max_retries=3, handle_popup=False):
        """点击元素（自动心跳 + 自动重连）"""
        by, value = locator
        retry_count = 0

        while retry_count < max_retries:
            try:
                element = self._find_element(locator, handle_popup=handle_popup)

                DriverManager.heartbeat()  # 点击前再发一次心跳
                DriverManager.safe_click(element)  # 使用 DriverManager 的安全点击

                logger.info(f"[{self.page_name}] 点击成功: {by}={value}")
                return element

            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"[{self.page_name}] 点击失败，重试第 {retry_count} 次: {e}")
                    time.sleep(0.6)
                else:
                    raise ElementOperationError(f"点击元素失败（已重试{max_retries}次）: {by}={value}") from e

    def send_keys(self, locator, text, handle_popup=False):
        element = self._find_element(locator, handle_popup=handle_popup)
        DriverManager.heartbeat()
        element.clear()
        element.send_keys(text)

    def get_text(self, locator, handle_popup=False):
        element = self._find_element(locator, handle_popup=handle_popup)
        DriverManager.heartbeat()
        text = element.text
        logger.info(f"[{self.page_name}] 获取文本: {text}")
        return text

    def only_find_element(self, locator, handle_popup=False):
        """仅查找元素，不处理弹窗"""

    def scroll_down(self, distance_ratio=0.4):
        """
        向下滑动屏幕（基于W3C规范的ActionChains实现）

        Args:
            distance_ratio (float): 滑动距离比例，相对于屏幕高度，默认0.4

        Examples:
            # 默认滑动（滑动距离为屏幕高度的40%）
            page.scroll_down()

            # 自定义滑动距离（滑动距离为屏幕高度的60%）
            page.scroll_down(distance_ratio=0.6)
        """
        try:
            # 获取屏幕尺寸
            size = self.driver.get_window_size()
            start_x = size['width'] / 2
            start_y = size['height'] * 0.7
            end_y = size['height'] * (0.7 - distance_ratio)  # 根据比例计算结束位置

            # 确保结束位置不超出屏幕边界
            end_y = max(end_y, 0)

            # 创建触摸输入设备
            touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
            actions = ActionChains(self.driver)
            actions.w3c_actions = ActionBuilder(self.driver, mouse=touch_input)

            # 构建滑动动作链：按下 -> 移动 -> 抬起
            actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
            actions.w3c_actions.pointer_action.pointer_down()  # 按下屏幕
            actions.w3c_actions.pointer_action.pause(0.1)  # 短暂停顿增强稳定性
            actions.w3c_actions.pointer_action.move_to_location(start_x, end_y)  # 滑动到目标位置
            actions.w3c_actions.pointer_action.pause(0.1)
            actions.w3c_actions.pointer_action.pointer_up()  # 抬起手指
            actions.perform()  # 执行动作链

            logger.info(f"向下滑动屏幕成功，滑动距离比例: {distance_ratio}")

        except Exception as e:
            logging.error(f"滑动屏幕失败: {str(e)}")
            raise

    def scroll_down_adb(self, distance_ratio=0.4, size=None, duration_ms=350, min_swipe_px=120):
        """
        使用 ADB 命令向下滑动屏幕

        Args:
            distance_ratio (float): 滑动距离比例，相对于屏幕高度，默认0.4
            size (dict, optional): 屏幕尺寸 {"width": int, "height": int}，如不传则通过ADB获取
            duration_ms (int): 滑动持续时间（毫秒）。部分机型省略该参数时 input swipe 会返回非零退出码。
            min_swipe_px (int): 最小滑动像素距离，避免距离过短被系统拒绝。

        Examples:
            # 默认滑动（滑动距离为屏幕高度的40%）
            page.scroll_down_adb()

            # 自定义滑动距离（滑动距离为屏幕高度的60%）
            page.scroll_down_adb(distance_ratio=0.6)

            # 复用屏幕尺寸以提升性能
            size = page.get_screen_size_adb()
            page.scroll_down_adb(size=size)
        """
        try:
            # 获取屏幕尺寸（优先使用传入的尺寸，否则通过ADB获取）
            if size is None:
                size = self.get_screen_size_adb()

            start_x = int(size['width'] / 2)
            start_y = int(size['height'] * 0.7)
            end_y = int(size['height'] * (0.7 - distance_ratio))

            # 确保结束位置不超出屏幕边界
            end_y = max(end_y, 0)

            # 保证垂直滑动距离不低于最小值（小屏 + 小比例时易触发 swipe 失败）
            swipe_dist = start_y - end_y
            if swipe_dist < min_swipe_px:
                end_y = max(0, start_y - min_swipe_px)

            adb = self._adb_base_args()
            swipe_args = [str(start_x), str(start_y), str(start_x), str(end_y)]
            cmd = adb + ["shell", "input", "swipe"] + swipe_args + [str(int(duration_ms))]
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if r.returncode != 0:
                # 极少数旧固件不支持带 duration 的 swipe，再试四参数形式
                cmd4 = adb + ["shell", "input", "swipe"] + swipe_args
                r = subprocess.run(cmd4, capture_output=True, text=True, check=False)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "").strip()
                logging.error(f"ADB滑动屏幕失败: exit={r.returncode} cmd={' '.join(cmd)} err={err}")
                raise subprocess.CalledProcessError(r.returncode, cmd, r.stdout, r.stderr)

            logger.info(
                f"ADB向下滑动屏幕成功，distance_ratio={distance_ratio}, "
                f"duration_ms={duration_ms}, dy={start_y - end_y}"
            )

        except Exception as e:
            logging.error(f"ADB滑动屏幕失败: {str(e)}")
            raise

    def tap_adb(self, x, y):
        """
        使用 ADB 命令在指定坐标点击

        Args:
            x (int): X坐标
            y (int): Y坐标

        Examples:
            # 在指定坐标点击
            page.tap_adb(540, 960)

            # 支持相对坐标（0-1之间视为百分比）
            page.tap_adb(0.5, 0.8)
        """
        try:
            # 处理相对坐标
            if isinstance(x, float) and 0 < x <= 1:
                size = self.get_screen_size_adb()
                x = int(size['width'] * x)
            if isinstance(y, float) and 0 < y <= 1:
                if 'size' not in dir():
                    size = self.get_screen_size_adb()
                y = int(size['height'] * y)

            # 执行 ADB 点击命令
            subprocess.run(
                ["adb", "shell", "input", "tap", str(int(x)), str(int(y))],
                check=True
            )

            logger.info(f"ADB点击坐标 ({x}, {y}) 成功")

        except Exception as e:
            logging.error(f"ADB点击坐标 ({x}, {y}) 失败: {str(e)}")
            raise

    def get_screen_size_adb(self):
        """
        通过 ADB 命令获取屏幕尺寸

        Returns:
            dict: {"width": int, "height": int}

        Examples:
            size = page.get_screen_size_adb()
            print(f"屏幕尺寸: {size['width']}x{size['height']}")
        """
        try:
            result = subprocess.run(
                self._adb_base_args() + ["shell", "wm", "size"],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout.strip()
            # 解析输出，格式如 "Physical size: 1080x2400"
            if "x" in output:
                size_str = output.split(":")[-1].strip()
                width, height = map(int, size_str.split("x"))
                return {"width": width, "height": height}
            else:
                raise ValueError(f"无法解析屏幕尺寸: {output}")

        except Exception as e:
            logging.error(f"通过ADB获取屏幕尺寸失败: {str(e)}")
            raise

    def scroll_up(self, distance_ratio=0.4):
        """
        向上滑动屏幕

        Args:
            distance_ratio (float): 滑动距离比例，相对于屏幕高度，默认0.4

        Examples:
            # 默认向上滑动
            page.scroll_up()

            # 自定义滑动距离
            page.scroll_up(distance_ratio=0.6)
        """
        try:
            # 获取屏幕尺寸
            size = self.driver.get_window_size()
            start_x = size['width'] / 2
            start_y = size['height'] * 0.3
            end_y = size['height'] * (0.3 + distance_ratio)  # 根据比例计算结束位置

            # 确保结束位置不超出屏幕边界
            end_y = min(end_y, size['height'])

            # 创建触摸输入设备
            touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
            actions = ActionChains(self.driver)
            actions.w3c_actions = ActionBuilder(self.driver, mouse=touch_input)

            # 构建滑动动作链：按下 -> 移动 -> 抬起
            actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
            actions.w3c_actions.pointer_action.pointer_down()  # 按下屏幕
            actions.w3c_actions.pointer_action.pause(0.1)  # 短暂停顿增强稳定性
            actions.w3c_actions.pointer_action.move_to_location(start_x, end_y)  # 滑动到目标位置
            actions.w3c_actions.pointer_action.pause(0.1)
            actions.w3c_actions.pointer_action.pointer_up()  # 抬起手指
            actions.perform()  # 执行动作链

            logger.info(f"向上滑动屏幕成功，滑动距离比例: {distance_ratio}")
            time.sleep(1)  # 等待滑动完成后的界面稳定

        except Exception as e:
            logging.error(f"向上滑动屏幕失败: {str(e)}")
            raise

    def scroll_to_bottom(self, max_swipes=10):
        """
        滑动到页面底部

        Args:
            max_swipes (int): 最大滑动次数，防止无限循环，默认10次

        Returns:
            bool: 成功滑动到页面底部返回True，否则返回False
        """
        try:
            logger.info("开始滑动到页面底部")

            for i in range(max_swipes):
                # 获取滑动前的页面源码或元素状态
                before_source = self.driver.page_source

                # 向下滑动
                self.scroll_down()

                # 获取滑动后的页面源码
                after_source = self.driver.page_source

                # 如果页面内容没有变化，说明已经到达底部
                if before_source == after_source:
                    logger.info(f"已滑动到页面底部，共滑动 {i + 1} 次")
                    return True

            logger.warning(f"达到最大滑动次数 {max_swipes}，可能未完全滑动到页面底部")
            return False

        except Exception as e:
            logger.error(f"滑动到页面底部时发生错误: {str(e)}")
            return False

    def scroll_to_element(self, locator, max_swipes=10, scroll_up=False):
        """
        滑动直到找到指定元素

        Args:
            locator (tuple): 要查找的元素定位信息
            max_swipes (int): 最大滑动次数，默认10次
            scroll_up (bool): 是否向上滑动查找，默认False（向下滑动）

        Returns:
            bool: 找到元素返回True，否则返回False
        """
        try:

            for i in range(max_swipes):
                try:
                    # 尝试查找元素
                    by, value = locator
                    element = self.driver.find_element(*locator)
                    if element.is_displayed():
                        logger.info(f"找到元素 {value}，共滑动 {i} 次")
                        return True

                except:
                    pass

                # 根据参数决定滑动方向
                if scroll_up:
                    self.scroll_up()
                else:
                    self.scroll_down()

            logger.warning(f"达到最大滑动次数 {max_swipes}，未找到元素 {locator}")
            return False

        except Exception as e:
            logger.error(f"滑动查找元素 {locator} 时发生错误: {str(e)}")
            return False

    def scroll_webview_to_element(self, locator, max_attempts=10, delay=0.8):
        """
        在 WebView 中滚动到指定元素可见（纯 JS，避免 get_window_size / CDP）
        """
        by, value = locator
        try:
            # ---- 确保在可用 WebView ----
            try:
                ctx = self.driver.context or ""
                if not str(ctx).upper().startswith("WEBVIEW"):
                    ok = self.switch_to_webview()
                    if not ok:
                        ok = self.ensure_webview_ready()
                    if not ok:
                        logger.error("无法切换到 WebView 上下文")
                        return False
                else:
                    self.driver.execute_script("return 1;")
            except Exception:
                if not self.ensure_webview_ready():
                    logger.error("无法切换到 WebView 上下文")
                    return False

            logger.info(f"开始在 WebView 中滚动到元素可见: {value}")

            for attempt in range(max_attempts):
                try:
                    element = self.driver.find_element(by, value)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', inline:'nearest', behavior:'instant'});",
                        element,
                    )
                    time.sleep(0.3)

                    in_viewport = self.driver.execute_script(
                        """
                        var el = arguments[0];
                        var rect = el.getBoundingClientRect();
                        var vh = window.innerHeight || document.documentElement.clientHeight;
                        var vw = window.innerWidth || document.documentElement.clientWidth;
                        return rect.top >= 0 && rect.left >= 0
                            && rect.bottom <= vh && rect.right <= vw
                            && rect.width > 0 && rect.height > 0;
                        """,
                        element,
                    )
                    if element.is_displayed() or in_viewport:
                        logger.info(f"元素 {value} 已可见，共尝试 {attempt + 1} 次")
                        return True
                except Exception as e:
                    logger.debug(f"第 {attempt + 1} 次查找/滚动未成功: {e}")

                scroll_info = self.driver.execute_script(
                    """
                    return {
                        y: window.pageYOffset || document.documentElement.scrollTop || 0,
                        total: Math.max(
                            document.body.scrollHeight || 0,
                            document.documentElement.scrollHeight || 0
                        ),
                        vh: window.innerHeight || document.documentElement.clientHeight || 0
                    };
                    """
                )
                scroll_y = scroll_info.get("y", 0)
                total_h = scroll_info.get("total", 0)
                vh = scroll_info.get("vh", 0)
                logger.info(f"当前滚动位置: {scroll_y}, 视口高: {vh}, 页面总高度: {total_h}")

                if scroll_y + vh >= total_h - 5:
                    logger.warning(f"已滚动到页面底部，仍未找到可见元素: {value}")
                    try:
                        element = self.driver.find_element(by, value)
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", element
                        )
                        time.sleep(0.3)
                        if element.is_displayed():
                            return True
                    except Exception:
                        pass
                    return False

                self.driver.execute_script(
                    "window.scrollBy(0, Math.floor(window.innerHeight * 0.8));"
                )
                time.sleep(delay)

            logger.warning(f"达到最大尝试次数 {max_attempts}，未能使元素可见: {value}")
            return False

        except Exception as e:
            error_msg = f"在 WebView 中滑动到元素 {value} 可见时发生错误: {str(e)}"
            logger.error(error_msg)
            try:
                allure.attach(
                    error_msg,
                    name="WebView滑动到元素失败",
                    attachment_type=allure.attachment_type.TEXT,
                )
            except Exception:
                pass
            return False

    def back(self, levels=1, wait_time=1):
        """返回上一页"""
        try:
            if levels <= 0:
                logger.warning("返回层级数应大于0，已调整为1")
                levels = 1

            # 执行多级返回
            for i in range(levels):
                with allure.step(f"执行时间：{self.get_current_time()} ----返回第 {i + 1} 级"):
                    self.driver.back()

                # 等待页面加载稳定
                if wait_time > 0:
                    time.sleep(wait_time)

            logger.info(f"返回操作完成，共返回 {levels} 级")
            return True

        except Exception as e:
            error_msg = f"返回操作失败，强制重启App: {str(e)}"
            logger.error(error_msg)
            self._back_to_home()

    def _back_to_home(self):
        """返回到首页"""
        try:
            current_package = self.driver.current_package
            logger.info(f"用例失败，重启App: {current_package}")
            self.driver.terminate_app(current_package)
            time.sleep(5)
            self.driver.activate_app(current_package)
            logger.info("App 重启成功")
        except Exception as e:
            # 冷启动并启动到首页
            app_package = DriverManager.get_current_package()
            app_activity = DriverManager.get_current_activity()
            full_activity = f"{app_package}/{app_activity}"
            subprocess.run(["adb", "shell", "am", "start", "force-stop", full_activity])
            time.sleep(2)
            subprocess.run(["adb", "shell", "am", "start", "-n", full_activity])



    def back_until_element_visible(self, element_name, max_levels=10, wait_time=1):
        """
        返回直到指定元素可见

        Args:
            element_name (str): 要等待出现的元素名称
            max_levels (int): 最大返回层级数，默认10级
            wait_time (float): 每次返回后的等待时间（秒），默认1秒

        Returns:
            bool: 成功找到元素返回True，否则返回False
        """
        try:
            logger.info(f"开始返回直到元素 {element_name} 可见，最大返回层级: {max_levels}")

            for i in range(max_levels):
                try:
                    # 尝试查找元素
                    element = self._find_element(element_name)
                    if element.is_displayed():
                        logger.info(f"已找到目标元素 {element_name}，返回操作完成")
                        return True
                except (ElementFindTimeoutError, ElementNotFoundException):
                    # 元素未找到，继续返回
                    pass

                # 执行返回操作
                self.driver.back()
                logger.info(f"已完成第 {i + 1} 级返回")

                # 等待页面加载稳定
                if wait_time > 0:
                    time.sleep(wait_time)

            logger.warning(f"达到最大返回层级 {max_levels}，仍未找到元素 {element_name}")
            return False

        except Exception as e:
            error_msg = f"返回直到元素可见失败: {str(e)}"
            logger.error(error_msg)
            return False

    def get_element_center(self, locator):
        """
        获取元素的中心点坐标
        :param locator: WebElement对象
        :return: (center_x, center_y) 中心点坐标元组
        """
        try:
            # 获取元素的位置和大小
            element = self._find_element(locator)
            location = element.location
            size = element.size

            # 计算中心点坐标
            center_x = location['x'] + size['width'] / 2
            center_y = location['y'] + size['height'] / 2

            logger.info(f"元素中心点坐标: ({center_x}, {center_y}), 位置: {location}, 大小: {size}")
            return center_x, center_y

        except Exception as e:
            logger.error(f"获取元素中心点坐标失败: {str(e)}")
            raise ElementOperationError(f"获取元素中心点坐标失败: {str(e)}")

    def back_home_with_tap(self):
        """根据坐标点击返回上一页"""
        with allure.step(f"执行时间：{self.get_current_time()} ---- 点击返回上一页"):
            self.tap_at_coordinates(61, 82)


    def tap_at_coordinates(self, x, y):
        """在指定坐标位置点击"""
        try:
            # 获取屏幕尺寸
            window_size = self.driver.get_window_size()
            screen_width = window_size['width']
            screen_height = window_size['height']

            # 处理相对坐标（百分比形式）
            if isinstance(x, float) and 0 < x <= 1:
                x = int(screen_width * x)
            if isinstance(y, float) and 0 < y <= 1:
                y = int(screen_height * y)

            # 创建触摸输入设备
            touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
            action_builder = ActionBuilder(self.driver, mouse=touch_input)

            # 执行点击操作
            action_builder.pointer_action.move_to_location(x, y)
            action_builder.pointer_action.pointer_down()
            action_builder.pointer_action.pause(0.1)
            action_builder.pointer_action.pointer_up()
            action_builder.perform()

            logger.info(f"在坐标 ({x}, {y}) 点击成功")
            return True

        except Exception as e:
            error_msg = f"在坐标 ({x}, {y}) 点击失败: {str(e)}"
            logger.error(error_msg)
            raise ElementOperationError(error_msg) from e

    def wait_for_element_indefinitely(self, locator, timeout=5):
        """
        持续等待元素出现，可设置超时时间
        """
        # 获取元素定位器
        by, value = locator
        logger.info(f"开始等待元素出现: {self.page_name}.{value}")
        logger.info(f"设置超时时间: {timeout}秒")
        logger.info(f"元素定位方式: {locator}")

        # 记录开始时间
        start_time = time.time()

        try:
            # 持续轮询检查元素是否存在
            while True:
                # 检查是否超时（在循环开始时检查）
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    error_msg = f"等待元素超时 ({timeout}秒): {self.page_name}.{value}"
                    logger.error(error_msg)
                    raise ElementFindTimeoutError(error_msg)

                try:
                    # 直接查找元素
                    element = self.driver.find_element(*locator)
                    if element.is_displayed():
                        logger.info(f"元素已出现: {self.page_name}.{value}")
                        return element
                    else:
                        logger.debug(f"元素存在但不可见: {self.page_name}.{value}")

                except ElementFindTimeoutError:
                    # 直接传播超时异常
                    raise
                except Exception:
                    # 其他异常（如元素不存在）继续等待
                    logger.debug(f"元素 {self.page_name}.{value} 尚未出现，继续等待...")
                    pass

                # 短暂休眠后继续检查
                time.sleep(self.poll_frequency)

        except ElementFindTimeoutError:
            # 直接重新抛出超时异常
            raise
        except Exception as e:
            error_msg = f"等待元素时发生意外错误: {self.page_name}.{value}, 错误: {str(e)}"
            logger.error(error_msg)
            raise ElementOperationError(error_msg) from e

    def switch_to_webview(self, timeout=10):
        """
        切换到WebView上下文

        Args:
            timeout (int): 等待WebView上下文出现的超时时间（秒）

        Returns:
            bool: 切换成功返回True，失败返回False

        Examples:
            # 切换到WebView
            page.switch_to_webview()

            # 指定超时时间
            page.switch_to_webview(timeout=15)
        """
        try:
            # 获取当前上下文
            current_context = self.driver.current_context
            logger.info(f"当前上下文: {current_context}")

            # 如果当前上下文已经是WebView，直接返回True
            if current_context and "WEBVIEW" in current_context.upper():
                logger.info(f"当前已在WebView上下文: {current_context}")
                return True

            start_time = time.time()
            while time.time() - start_time < timeout:
                # 获取所有可用的上下文
                contexts = self.driver.contexts
                logger.info(f"当前可用上下文: {contexts}")

                # 查找包含WEBVIEW的上下文
                webview_context = None
                for context in contexts:
                    if "WEBVIEW" in context.upper():
                        webview_context = context
                        break

                if webview_context:
                    # 切换到WebView上下文
                    self.driver.switch_to.context(webview_context)
                    current_context = self.driver.current_context
                    logger.info(f"成功切换到WebView上下文: {current_context}")
                    return True

                # 等待一段时间后重试
                time.sleep(1)

            logger.warning(f"在{timeout}秒内未找到WebView上下文")
            return False

        except Exception as e:
            error_msg = f"切换到WebView时发生错误: {str(e)}"
            logger.error(error_msg)
            allure.attach(error_msg, name="WebView切换错误", attachment_type=allure.attachment_type.TEXT)
            return False

    def switch_to_native(self):
        """
        切换回Native上下文

        Returns:
            bool: 切换成功返回True，失败返回False
        """
        try:
            # 切换到NATIVE_APP上下文
            self.driver.switch_to.context("NATIVE_APP")
            current_context = self.driver.current_context
            logger.info(f"成功切换到Native上下文: {current_context}")
            return True

        except Exception as e:
            error_msg = f"切换到Native时发生错误: {str(e)}"
            logger.error(error_msg)
            allure.attach(error_msg, name="Native切换错误", attachment_type=allure.attachment_type.TEXT)
            return False

    def get_current_context(self):
        """
        获取当前上下文

        Returns:
            str: 当前上下文名称
        """
        try:
            current_context = self.driver.current_context
            logger.info(f"当前上下文: {current_context}")
            return current_context
        except Exception as e:
            error_msg = f"获取当前上下文时发生错误: {str(e)}"
            logger.error(error_msg)
            return None

    def get_available_contexts(self):
        """
        获取所有可用的上下文

        Returns:
            list: 所有可用上下文列表
        """
        try:
            contexts = self.driver.contexts
            logger.info(f"可用上下文: {contexts}")
            return contexts
        except Exception as e:
            error_msg = f"获取可用上下文时发生错误: {str(e)}"
            logger.error(error_msg)
            return []

    def wait_and_switch_to_webview(self, timeout=10):
        """
        等待并切换到WebView上下文
        """
        try:
            logger.info("开始等待并切换到WebView上下文")

            # 先获取当前上下文
            current_context = self.get_current_context()
            if current_context and "WEBVIEW" in current_context.upper():
                logger.info(f"已经在WebView上下文: {current_context}")
                return True

            # 等待WebView上下文出现并切换
            if self.switch_to_webview(timeout=timeout):
                return True
            else:
                # 如果第一次切换失败，尝试处理可能的弹窗后再试
                logger.warning("首次切换WebView失败，尝试处理弹窗后重试")
                popup_handled = self.popup_handler.check_and_handle_popup()
                if popup_handled:
                    logger.info("处理弹窗后重新尝试切换到WebView")
                    return self.switch_to_webview(timeout=timeout)
                else:
                    logger.error("未检测到可处理的弹窗，切换WebView仍然失败")
                    return False

        except Exception as e:
            error_msg = f"等待并切换到WebView时发生错误: {str(e)}"
            logger.error(error_msg)
            allure.attach(error_msg, name="WebView切换错误", attachment_type=allure.attachment_type.TEXT)
            return False

    def click_webview_element_by_locator(self, by, locator, timeout=10, element_name="元素"):
        """
        通过定位器点击元素的通用方法
        """
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            logger.info(f"尝试点击{element_name}: by={by}, locator={locator}")

            # 等待元素可点击并点击
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, locator))
            )
            element.click()
            logger.info(f"点击{element_name}成功: by={by}, locator={locator}")
            return True
        except Exception as e:
            error_msg = f"点击{element_name}失败: by={by}, locator={locator}, 错误: {str(e)}"
            logger.error(error_msg)
            # 将错误信息添加到Allure报告
            try:
                import allure
                allure.attach(error_msg, name=f"{element_name}点击失败", attachment_type=allure.attachment_type.TEXT)
                # 附加当前页面截图
                try:
                    screenshot = self.driver.get_screenshot_as_png()
                    allure.attach(screenshot, name=f"{element_name}点击失败截图",
                                  attachment_type=allure.attachment_type.PNG)
                except:
                    pass
            except:
                pass
            return False

    def _take_screenshot(self, name: str) -> bool:
        """ADB 优先截图，失败再走 Appium（原有逻辑保留）"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                result = subprocess.run(
                    ["adb", "exec-out", "screencap", "-p"],
                    capture_output=True, timeout=5, check=False,
                )
                if result.returncode == 0 and len(result.stdout) > 0:
                    allure.attach(result.stdout, name=name, attachment_type=allure.attachment_type.PNG)
                    logger.info(f"已截取屏幕截图(ADB exec-out): {name}")
                    return True

                # 兜底 Appium
                screenshot = self.driver.get_screenshot_as_png()
                allure.attach(screenshot, name=name, attachment_type=allure.attachment_type.PNG)
                logger.info(f"已截取屏幕截图(Appium): {name}")
                return True
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.warning(f"截图失败: {name}, {e}")
                    return False
                time.sleep(0.5)
        return False

    def get_current_time(self, format_str="%Y-%m-%d %H:%M:%S"):
        """获取当前系统时间"""
        return time.strftime(format_str, time.localtime())

    def click_webview_element_by_locator(self, by, locator, timeout=10, element_name="元素"):
        """webview点击元素的方式"""
        try:

            logger.info(f"尝试点击{element_name}: by={by}, locator={locator}")

            # 等待元素可点击并点击
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, locator))
            )
            element.click()
            logger.info(f"点击{element_name}成功: by={by}, locator={locator}")
            return True
        except Exception as e:
            error_msg = f"点击{element_name}失败: by={by}, locator={locator}, 错误: {str(e)}"
            logger.error(error_msg)
            # 将错误信息添加到Allure报告
            try:
                import allure
                allure.attach(error_msg, name=f"{element_name}点击失败", attachment_type=allure.attachment_type.TEXT)
                # 附加当前页面截图
                try:
                    screenshot = self.driver.get_screenshot_as_png()
                    allure.attach(screenshot, name=f"{element_name}点击失败截图",
                                  attachment_type=allure.attachment_type.PNG)
                except:
                    pass
            except:
                pass
            return False

    def _handle_error(
            self,
            error_msg: str,
            screenshot_name: str = None,
            raise_exception: bool = True,
            failure_type: FailureType = FailureType.UNKNOWN,
    ) -> StepResult:
        """
        统一错误处理。
        - 默认抛 BusinessFailure（兼容旧代码）
        - 也可只返回 StepResult（新结构化用法）
        """
        if screenshot_name is None:
            screenshot_name = f"错误截图_{int(time.time())}"

        self._take_screenshot(screenshot_name)
        logger.error(f"[{self.page_name}] {error_msg}")

        result = StepResult.fail(failure_type, error_msg, screenshot_taken=True)

        if raise_exception:
            raise BusinessFailure(error_msg)

        return result

    def get_timeline_center_y(self) -> int:
        """
        获取时间轴元素中心 Y 坐标
        元素 id: com.xm.support.android:id/layout_timeline
        """
        try:
            # 优先用 Appium 定位
            locator = (AppiumBy.ID, "com.xm.support.android:id/layout_timeline")
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(locator)
            )

            location = element.location  # {'x': ..., 'y': ...}
            size = element.size  # {'width': ..., 'height': ...}

            center_y = int(location["y"] + size["height"] / 2)
            logger.info(
                f"时间轴位置: x={location['x']}, y={location['y']}, "
                f"w={size['width']}, h={size['height']} → center_y={center_y}"
            )
            return center_y

        except Exception as e:
            logger.warning(f"获取时间轴坐标失败: {e}，尝试 ADB dumpsys 兜底")
            return self._get_timeline_center_y_by_adb()

    def _get_timeline_center_y_by_adb(self) -> int:
        """ADB 兜底获取时间轴中心 Y（当 Appium 定位失败时）"""
        try:
            adb = self._adb_base_args()
            # 导出当前界面 XML
            subprocess.run(adb + ["shell", "uiautomator", "dump", "/sdcard/ui.xml"],
                           timeout=8, check=False)
            result = subprocess.run(
                adb + ["shell", "cat", "/sdcard/ui.xml"],
                capture_output=True, text=True, timeout=8
            )
            xml = result.stdout

            import re
            # 匹配 resource-id 包含 layout_timeline 的节点 bounds
            pattern = r'resource-id="[^"]*layout_timeline[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            match = re.search(pattern, xml)
            if not match:
                # 宽松一点再试一次
                pattern = r'layout_timeline[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                match = re.search(pattern, xml)

            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                center_y = (y1 + y2) // 2
                logger.info(f"ADB 解析时间轴 bounds=[{x1},{y1}][{x2},{y2}] → center_y={center_y}")
                return center_y

        except Exception as e:
            logger.error(f"ADB 获取时间轴坐标失败: {e}")

        # 最终兜底（你实测可用的 Y）
        logger.warning("使用兜底 Y=812")
        return 812

    def swipe_horizontal(self, start_x, start_y, end_x, end_y, duration=1000):
        """
        水平滑动（左右滑动）
        Args:
            start_x (int): 起始点X坐标
            start_y (int): 起始点Y坐标
            end_x (int): 结束点X坐标
            end_y (int): 结束点Y坐标
            duration (int): 滑动持续时间（毫秒），默认1000ms

        Examples:
            # 从左向右滑动
            page.swipe_horizontal(235, 656, 532, 656)
            # 从右向左滑动
            page.swipe_horizontal(532, 656, 235, 656)
        """
        try:
            # 创建触摸输入设备
            touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
            actions = ActionChains(self.driver)
            actions.w3c_actions = ActionBuilder(self.driver, mouse=touch_input)

            # 构建滑动动作链
            actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
            actions.w3c_actions.pointer_action.pointer_down()
            actions.w3c_actions.pointer_action.move_to_location(end_x, end_y)
            actions.w3c_actions.pointer_action.release()
            actions.perform()

            logger.info(f"水平滑动成功: 从({start_x}, {start_y})到({end_x}, {end_y})")
            time.sleep(5)
            return True

        except Exception as e:
            error_msg = f"水平滑动失败: 从({start_x}, {start_y})到({end_x}, {end_y}), 错误: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def is_element_present(self, locator, timeout=2):
        """
        判断元素是否存在
        Args:
            locator (tuple): 元素定位器
            timeout (int): 超时时间（秒），默认2秒

        Returns:
            bool: 元素存在返回True，超时返回False
        """
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                elements = self.driver.find_elements(*locator)
                if len(elements) > 0:
                    return True
                time.sleep(self.poll_frequency)
            return False
        except Exception:
            return False

    def verify_page_jump(self, identifier, timeout=10, page_name="目标页面") -> StepResult:
        time.sleep(1)
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(identifier),
                message=f"未找到{page_name}的唯一标识"
            )
            logger.info(f"{page_name}页面跳转成功")
            self._take_screenshot(f"{page_name}页面跳转状态截图")
            return StepResult.ok()
        except Exception as e:
            return self._handle_error(
                f"{page_name}页面跳转失败: {str(e)}",
                "页面跳转失败",
                raise_exception=False,
                failure_type=FailureType.ELEMENT_NOT_FOUND,
            )


    def is_element_visible(self, locator, timeout=2):
        try:
            WebDriverWait(self.driver, timeout, self.poll_frequency).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except Exception:
            return False

    def pull_to_refresh(self, refresh_element=None, pull_distance_ratio=0.3, duration=1000):
        """
        下拉刷新页面
        Args:
            refresh_element (tuple, optional): 刷新指示器元素定位器，用于确认刷新完成
            pull_distance_ratio (float): 下拉距离比例，相对于屏幕高度，默认0.3
            duration (int): 滑动持续时间（毫秒），默认1000ms

        Returns:
            bool: 刷新成功返回True，失败返回False

        Examples:
            # 基本下拉刷新
            page.pull_to_refresh()

            # 指定刷新完成标识元素
            page.pull_to_refresh((AppiumBy.ID, "com.example.app:id/refresh_complete_indicator"))

            # 自定义下拉距离
            page.pull_to_refresh(pull_distance_ratio=0.5)
        """
        try:
            logger.info("开始执行下拉刷新操作")

            # 获取屏幕尺寸
            size = self.driver.get_window_size()
            screen_width = size['width']
            screen_height = size['height']

            # 计算下拉坐标
            start_x = screen_width / 2
            start_y = screen_height * 0.25  # 从屏幕上方1/4处开始
            pull_distance = screen_height * pull_distance_ratio
            end_y = start_y + pull_distance  # 下拉到目标位置

            # 确保结束位置不超出屏幕边界
            end_y = min(end_y, screen_height * 0.9)

            logger.info(f"下拉刷新坐标: 从({start_x}, {start_y})到({start_x}, {end_y})")

            # 创建触摸输入设备
            touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
            actions = ActionChains(self.driver)
            actions.w3c_actions = ActionBuilder(self.driver, mouse=touch_input)

            # 构建下拉刷新动作链
            # 1. 按下屏幕
            actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
            actions.w3c_actions.pointer_action.pointer_down()
            actions.w3c_actions.pointer_action.pause(0.1)

            # 2. 向下滑动（下拉）
            actions.w3c_actions.pointer_action.move_to_location(start_x, end_y)
            actions.w3c_actions.pointer_action.pause(duration / 1000.0)  # 持续时间

            # 3. 释放手指
            actions.w3c_actions.pointer_action.pointer_up()
            actions.perform()

            logger.info("下拉刷新手势执行完成")

            # 等待刷新完成
            if refresh_element:
                try:
                    logger.info(f"等待刷新完成，检查元素: {refresh_element}")
                    # 等待刷新指示器消失或者出现，表明刷新完成
                    WebDriverWait(self.driver, 10).until(
                        EC.invisibility_of_element_located(refresh_element) or
                        EC.visibility_of_element_located(refresh_element)
                    )
                    logger.info("检测到刷新完成标识")
                except TimeoutException:
                    logger.warning("等待刷新完成超时，可能刷新未完成或标识元素设置不正确")
            else:
                # 如果没有指定刷新元素，则等待一段时间
                time.sleep(3)
                logger.info("页面刷新成功，等待3秒后继续")

            logger.info("下拉刷新操作完成")
            return True

        except Exception as e:
            error_msg = f"下拉刷新操作失败: {str(e)}"
            logger.error(error_msg)
            # 添加截图到报告
            self._take_screenshot("下拉刷新失败")
            return False

    def refresh_h5_page(self):
        try:
            # 已在 WebView 且 JS 可用则直接 reload
            need_full = True
            try:
                ctx = self.driver.context or ""
                if str(ctx).upper().startswith("WEBVIEW"):
                    self.driver.execute_script("return 1;")
                    need_full = False
            except Exception:
                need_full = True

            if need_full and not self.ensure_webview_ready():
                logger.error("无法切换到可用 WebView，刷新取消")
                return False

            self.driver.execute_script(
                "try{location.reload();}catch(e){window.location.href=window.location.href;}"
            )
            time.sleep(1.2)  # 原 2s 可略减

            # reload 后会话常失效，必须再连一次
            if not self.ensure_webview_ready():
                logger.error("H5 刷新后 WebView 会话丢失")
                self._take_screenshot("H5 页面刷新失败")
                return False

            logger.info("H5 页面刷新成功")
            return True
        except Exception as e:
            logger.error(f"H5 页面刷新失败: {e}")
            self._take_screenshot("H5 页面刷新失败")
            return False

    def click_with_coordinate_fallback(self, locator, max_retries=3, element_name=None):
        """
        点击元素，如果找不到元素则使用坐标点击作为兜底方案

        Args:
            locator (tuple): 元素定位器
            max_retries (int): 最大重试次数，默认3次
            element_name (str): 元素名称，用于在坐标映射中查找，默认使用locator信息

        Returns:
            bool: 点击成功返回True
        """
        # 确定元素名称用于坐标映射查找
        if element_name is None:
            # 从locator中提取元素名称
            by, value = locator
            element_name = value.split("=")[-1] if "=" in str(value) else str(value)

        # 首先尝试正常点击元素
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.info(f"尝试点击元素: {locator} (第{retry_count + 1}次尝试)")
                element = self.driver.find_element(locator)
                element.click()
                logging.info(f"成功点击元素: {locator}")
                return True
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"第{retry_count}次点击元素失败，准备重试: {str(e)}")
                    time.sleep(0.5)  # 短暂等待后重试
                else:
                    logger.error(f"经过{max_retries}次重试后仍无法点击元素: {locator}, 错误: {str(e)}")

        # 如果重试后仍然失败，尝试使用坐标点击
        if element_name in self.coordinate_map:
            x, y = self.coordinate_map[element_name]
            logger.info(f"元素点击失败，使用坐标兜底方案: {element_name} -> ({x}, {y})")
            try:
                self.tap_at_coordinates(x, y)
                logger.info(f"成功通过坐标点击元素: {element_name}")
                return True
            except Exception as e:
                error_msg = f"坐标点击也失败: {element_name} ({x}, {y}), 错误: {str(e)}"
                logger.error(error_msg)
                raise ElementOperationError(error_msg) from e
        else:
            error_msg = f"元素点击失败且未找到坐标映射: {element_name}"
            logger.error(error_msg)
            raise ElementOperationError(error_msg)


    def adb_screenshot(step_name=""):
        """用 ADB 截图并附加到 Allure 报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        local_path = f"./screenshots/{filename}"

        os.makedirs("./screenshots", exist_ok=True)

        # 1. 在手机上截图
        subprocess.run(["adb", "shell", "screencap", "-p", f"/sdcard/{filename}"], check=True)

        # 2. 拉取到电脑
        subprocess.run(["adb", "pull", f"/sdcard/{filename}", local_path], check=True)

        # 3. 删除手机上的文件（可选，保持干净）
        subprocess.run(["adb", "shell", "rm", f"/sdcard/{filename}"], check=True)

        # 4. 附加到 Allure
        with open(local_path, "rb") as f:
            allure.attach(
                f.read(),
                name=f"{step_name} - {timestamp}" if step_name else timestamp,
                attachment_type=allure.attachment_type.PNG
            )

        logger.info(f"adb截图已附加截图到 Allure: {filename}")
        return local_path

    # ==================== UiAutomator2 崩溃自动恢复 ====================

    def _is_uiautomator2_crashed(self, exc: Exception) -> bool:
        """
        根据异常信息判断是否为 UiAutomator2 服务崩溃。

        崩溃特征（两种模式均支持）：
        - "cannot be proxied to UiAutomator2 server because the instrumentation process is not running"
        - "instrumentation process is not running (probably crashed)"
        """
        msg = str(exc)
        return (
            "UiAutomator2" in msg
            and "cannot be proxied" in msg
            and "instrumentation process is not running" in msg
        ) or (
            "instrumentation process is not running (probably crashed)" in msg
        )

    # def _recover_uiautomator2(self) -> bool:
    #     """
    #     尝试自动恢复 UiAutomator2 服务。
    #
    #     恢复策略（由轻到重）：
    #     1. activate_app — 仅激活前台，最轻量
    #     2. terminate_app + activate_app — 强制重启 App
    #     3. raise — 恢复失败，抛给上层处理
    #
    #     Returns:
    #         bool: 恢复成功返回 True
    #     """
    #     logger.warning("[UIA2恢复] 检测到 UiAutomator2 服务崩溃，开始恢复...")
    #
    #     current_pkg = None
    #     try:
    #         current_pkg = self.driver.current_package
    #     except Exception:
    #         pass
    #
    #     if not current_pkg:
    #         logger.error("[UIA2恢复] 无法获取当前 App 包名，恢复失败")
    #         raise RuntimeError("UiAutomator2 崩溃且无法获取包名，无法自动恢复")
    #
    #     # 策略1：仅激活 App
    #     try:
    #         self.driver.activate_app(current_pkg)
    #         logger.info(f"[UIA2恢复] activate_app({current_pkg}) 成功")
    #         time.sleep(1.5)
    #         return True
    #     except Exception as e1:
    #         logger.warning(f"[UIA2恢复] activate_app 失败: {e1}")
    #
    #     # 策略2：强制终止后重新激活
    #     try:
    #         self.driver.terminate_app(current_pkg)
    #         time.sleep(1.0)
    #         self.driver.activate_app(current_pkg)
    #         time.sleep(2.0)
    #         logger.info(f"[UIA2恢复] terminate_app + activate_app({current_pkg}) 成功")
    #         return True
    #     except Exception as e2:
    #         logger.warning(f"[UIA2恢复] terminate_app + activate_app 失败: {e2}")
    #
    #     logger.error("[UIA2恢复] 两种策略均失败，无法自动恢复 UiAutomator2")
    #     raise RuntimeError(
    #         "UiAutomator2 崩溃，自动恢复失败（已尝试 activate_app 和 terminate_app+activate_app）"
    #     )

    def _recover_uiautomator2(self) -> bool:
        """
        真正解决 UiAutomator2 崩溃的终极方法
        作用：
        1. 关闭崩溃的旧驱动
        2. 重新初始化驱动（调用你自己的单例driver重建）
        3. 恢复后可以直接继续执行
        """
        logger.critical("【致命异常】UiAutomator2 已崩溃，开始执行【驱动重启恢复】...")

        try:
            # 1. 强制销毁旧 driver（不管是否有效）
            if hasattr(self, 'driver') and self.driver is not None:
                try:
                    logger.warning("[驱动重启] 关闭旧驱动 driver.quit()...")
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"[驱动重启] 关闭旧驱动失败（可忽略）: {str(e)}")
                self.driver = None
                time.sleep(3)

            # 2. 重新创建驱动（调用你自己的单例driver）
            logger.info("[驱动重启] 开始重新初始化新驱动...")
            from core.driver import Driver  # 你的单例driver类
            self.driver = Driver().get_driver()  # 重建新驱动
            logger.info("[驱动重启] ✅ 新驱动创建成功！")

            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"[驱动重启] ❌ 驱动重启失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise RuntimeError("自动化恢复失败：无法重建驱动")


    def get_webview_contexts(self):
        try:
            contexts = self.driver.contexts or []
            return [c for c in contexts if c and str(c).upper().startswith("WEBVIEW")]
        except Exception as e:
            logger.warning(f"获取 contexts 失败: {e}")
            return []

    def ensure_webview_ready(self, preferred_keyword="", retries=2, wait_sec=0.5):
        """
        优先快路径：当前已在可用 WebView 则立刻返回，避免每次都 NATIVE 重连。
        """
        # ---------- 快路径 ----------
        try:
            ctx = (self.driver.context or "")
            if str(ctx).upper().startswith("WEBVIEW"):
                # 排除明显错误的 chrome 系统页（可选）
                if "chrome" not in ctx.lower() or (preferred_keyword and preferred_keyword in ctx):
                    self.driver.execute_script("return 1;")
                    logger.info(f"WebView 已就绪(快路径): {ctx}")
                    return True
        except Exception:
            pass

        last_err = None
        for i in range(retries):
            try:
                try:
                    self.driver.switch_to.context("NATIVE_APP")
                except Exception:
                    pass
                time.sleep(0.2)

                webviews = []
                for _ in range(6):  # 最多约 3s，原 12 次太慢
                    webviews = self.get_webview_contexts()
                    if webviews:
                        break
                    time.sleep(0.4)

                if not webviews:
                    last_err = "未发现 WEBVIEW 上下文"
                    logger.warning(f"ensure_webview 第{i + 1}次: {last_err}")
                    time.sleep(wait_sec)
                    continue

                target = None
                if preferred_keyword:
                    for c in webviews:
                        if preferred_keyword in c:
                            target = c
                            break
                if not target:
                    for c in webviews:
                        if "chrome" not in c.lower():
                            target = c
                            break
                if not target:
                    target = webviews[-1]

                self.driver.switch_to.context(target)
                self.driver.execute_script("return 1;")
                logger.info(f"WebView 就绪: {target}")
                return True
            except Exception as e:
                last_err = str(e)
                logger.warning(f"ensure_webview 第{i + 1}次失败: {e}")
                time.sleep(wait_sec)

        logger.error(f"无法恢复 WebView: {last_err}")
        return False