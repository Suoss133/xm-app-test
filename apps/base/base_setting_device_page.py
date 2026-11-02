# base_setting_device_page.py
import time

from selenium.webdriver.support.wait import WebDriverWait

from core.base_page import BasePage
from core.result import StepResult, FailureType
from core.yaml_utils import YamlUtils
from utils.logger import logger
from selenium.webdriver.support import expected_conditions as EC



class BaseSettingDevicePage(BasePage):
    """设备设置基类"""

    def __init__(self, page_name, config_path, page_config_name):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)
        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name,
        )
        self.DELETE_DEVICE = YamlUtils.parse_locator(self.elements["delect_device"])
        self.SETTING_DEVICE_PAGE_IDENTIFIER = YamlUtils.parse_locator(
            self.elements["setting_device_page_identifier"]
        )
        self.confirm_delect_device = YamlUtils.parse_locator(
            self.elements["confirm_delect_device"]
        )
        self.device_status = YamlUtils.parse_locator(self.elements["device_status"])
        self.setting_page_title = self.SETTING_DEVICE_PAGE_IDENTIFIER

    # ------------------------------------------------------------------
    # WebView：动态包名，不写死
    # ------------------------------------------------------------------
    def _app_webview_keyword(self) -> str:
        try:
            pkg = (self.driver.capabilities or {}).get("appPackage") or ""
            if pkg:
                return pkg
        except Exception:
            pass
        try:
            from core.driver import DriverManager
            pkg = DriverManager.get_current_package()
            if pkg:
                return pkg
        except Exception:
            pass
        return ""

    def _ensure_wv(self) -> bool:
        return self.ensure_webview_ready(preferred_keyword=self._app_webview_keyword())

    # ------------------------------------------------------------------
    # 等待上线
    # ------------------------------------------------------------------
    def wait_for_device_online(self, max_rounds: int = 6, interval: int = 4) -> bool:
        """
        上线检测：先看状态，离线再刷新；缩短轮次与间隔。
        """
        for i in range(max_rounds):
            try:
                if not self._ensure_wv():
                    time.sleep(interval)
                    continue

                # 已在线则不再无意义刷新
                offline = self.is_element_visible(self.device_status, timeout=1.5)
                if not offline:
                    logger.info("设备已上线，可以删除设备")
                    return True

                logger.info(f"第{i + 1}轮：设备离线，刷新 H5...")
                self.refresh_h5_page()
                time.sleep(interval)

                offline = self.is_element_visible(self.device_status, timeout=1.5)
                if not offline:
                    logger.info("设备已上线，可以删除设备")
                    return True
            except Exception as e:
                logger.error(f"检查设备状态异常: {e}")
                time.sleep(interval)

        logger.error(f"等待设备上线超时（{max_rounds} 轮）")
        return False

    # ------------------------------------------------------------------
    # 单次删除点击（当前页）
    # ------------------------------------------------------------------
    def _click_delete_once(self) -> None:
        """滚动 → 点删除 → 确认（全程尽量留在 WebView）"""
        if not self._ensure_wv():
            raise RuntimeError("WebView 不可用")

        if not self.scroll_webview_to_element(self.DELETE_DEVICE, max_attempts=5, delay=0.4):
            self.refresh_h5_page()
            if not self.scroll_webview_to_element(self.DELETE_DEVICE, max_attempts=5, delay=0.4):
                raise RuntimeError("未找到「删除设备」按钮")

        # 已在 WebView，不要再整轮 ensure
        try:
            el = self.driver.find_element(*self.DELETE_DEVICE)
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            el = self.driver.find_element(*self.DELETE_DEVICE)
            el.click()

        time.sleep(0.8)

        # 确认框：短超时，避免 20s×3
        confirm_ok = False
        try:
            confirm = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(self.confirm_delect_device)
            )
            try:
                self.driver.execute_script("arguments[0].click();", confirm)
            except Exception:
                confirm.click()
            confirm_ok = True
        except Exception:
            # 可能是 Native 弹窗
            try:
                self.switch_to_native()
                # Native 用短超时找确认（若 yaml 是 H5 xpath，这里会失败，快速跳过）
                old_timeout = self.wait_timeout
                self.wait_timeout = 5
                try:
                    self.click(self.confirm_delect_device, max_retries=1)
                    confirm_ok = True
                finally:
                    self.wait_timeout = old_timeout
            except Exception as e:
                logger.warning(f"确认删除按钮未点到: {e}")

        if not confirm_ok:
            raise RuntimeError("未成功点击「确认删除」")

        time.sleep(1.5)
        try:
            self.switch_to_native()
        except Exception:
            pass
        logger.info("删除点击流程完成")

    def delete_device_by_context(self) -> None:
        if not self._ensure_wv():
            raise RuntimeError("无法进入 WebView")
        if not self.wait_for_device_online(max_rounds=6, interval=4):
            raise RuntimeError("等待设备上线超时")
        self._click_delete_once()
        logger.info("成功删除设备（当前页）")

    # ------------------------------------------------------------------
    # 当前页重试 3 次（不重启 App）
    # ------------------------------------------------------------------
    def delete_device_on_page_retry(self, max_retries: int = 3) -> None:
        last_err = None
        for i in range(1, max_retries + 1):
            try:
                logger.info(f"[删除-当前页] 第 {i}/{max_retries} 次尝试")
                if i > 1:
                    # 轻量恢复：只 ensure + 一次 refresh，不要反复 NATIVE 空转
                    if not self._ensure_wv():
                        raise RuntimeError("重试前 WebView 不可用")
                    self.refresh_h5_page()
                    time.sleep(0.5)

                self.delete_device_by_context()
                return
            except Exception as e:
                last_err = e
                logger.error(f"[删除-当前页] 第 {i} 次失败: {e}")
                self._take_screenshot(f"删除失败_当前页第{i}次")
                time.sleep(1.0)

        raise RuntimeError(f"当前页删除重试{max_retries}次仍失败: {last_err}")

    # ------------------------------------------------------------------
    # 重启 App（仅作最后兜底）
    # ------------------------------------------------------------------
    def _restart_app(self):
        pkg = ""
        try:
            pkg = (self.driver.capabilities or {}).get("appPackage") or ""
        except Exception:
            pass
        if not pkg:
            try:
                from core.driver import DriverManager
                pkg = DriverManager.get_current_package()
            except Exception:
                pass
        if not pkg:
            raise RuntimeError("无法获取 appPackage，无法重启 App")

        self.driver.terminate_app(pkg)
        time.sleep(2)
        self.driver.activate_app(pkg)
        time.sleep(3)
        logger.info(f"[删除兜底] App 已重启: {pkg}")

    def _device_still_on_home(self, home_page, device_name: str) -> bool:
        return home_page.is_element_visible(
            (
                "xpath",
                f'//android.widget.TextView[contains(@resource-id,"title") '
                f'and @text="{device_name}"]',
            ),
            timeout=4,
        )

    # ------------------------------------------------------------------
    # 保障删除：当前页 3 次 → 重启兜底
    # ------------------------------------------------------------------
    def delete_device_with_guarantee(
        self,
        device_name: str,
        home_page,
        page_retries: int = 3,
        restart_retries: int = 2,
    ) -> StepResult:
        """
        1) 当前设置页重试 page_retries 次（不重启）
        2) 仍失败 → 重启 App → 再进设置再删（restart_retries 次）
        3) 成功条件：删除流程完成 + 首页无该设备
        """
        last_err = ""

        # ---------- 阶段 A：当前页重试 ----------
        try:
            logger.info(f"[删除保障] 阶段A：当前页最多重试 {page_retries} 次")
            self.delete_device_on_page_retry(max_retries=page_retries)

            time.sleep(2)
            try:
                if hasattr(home_page, "pull_to_refresh"):
                    home_page.pull_to_refresh()
            except Exception:
                pass

            if self._device_still_on_home(home_page, device_name):
                raise RuntimeError(f"当前页删除后首页仍存在设备: {device_name}")

            logger.info(f"[删除保障] 阶段A成功: {device_name}")
            return StepResult.ok(message="删除成功(当前页重试)")
        except Exception as e:
            last_err = str(e)
            logger.error(f"[删除保障] 阶段A失败: {last_err}")

        # ---------- 阶段 B：重启 App 兜底 ----------
        for round_i in range(1, restart_retries + 1):
            logger.warning(
                f"[删除保障] 阶段B兜底 第 {round_i}/{restart_retries} 次：重启 App 再删"
            )
            try:
                try:
                    self.switch_to_native()
                except Exception:
                    pass

                self._restart_app()
                time.sleep(2)

                enter = home_page.click_setting_button(device_name)
                if hasattr(enter, "success") and not enter.success:
                    raise RuntimeError(f"重启后进入设置失败: {getattr(enter, 'message', enter)}")

                self.verify_page_jump(
                    self.SETTING_DEVICE_PAGE_IDENTIFIER,
                    page_name="设备设置页面",
                )
                time.sleep(2)

                # 进入设置后仍先走当前页删除（含等上线）
                self.delete_device_on_page_retry(max_retries=2)

                time.sleep(2)
                try:
                    if hasattr(home_page, "pull_to_refresh"):
                        home_page.pull_to_refresh()
                except Exception:
                    pass

                if self._device_still_on_home(home_page, device_name):
                    raise RuntimeError(f"兜底删除后首页仍存在设备: {device_name}")

                logger.info(f"[删除保障] 阶段B第{round_i}次成功: {device_name}")
                return StepResult.ok(message=f"删除成功(重启兜底第{round_i}次)")

            except Exception as e:
                last_err = str(e)
                logger.error(f"[删除保障] 阶段B第{round_i}次失败: {last_err}")
                self._take_screenshot(f"删除失败_重启兜底第{round_i}次")

        return StepResult.fail(
            FailureType.DELETE_FAILED,
            f"删除设备最终失败(当前页{page_retries}次+重启兜底{restart_retries}次): {last_err}",
        )

    def delete_device_by_result(
        self,
        result: dict | StepResult,
        device_name: str,
        home_page=None,
    ) -> StepResult:
        if isinstance(result, StepResult):
            text = result.data.get("text") if result.data else None
            success = result.success
        else:
            text = result.get("text") if result else None
            success = text == "连接成功"

        if not (success or text == "连接成功"):
            logger.warning(f"配网未成功，跳过删除。原因: {text}")
            return StepResult.ok(message="配网失败，跳过删除")

        if home_page is None:
            # 无 home_page 时仅当前页重试，不走重启兜底
            try:
                self.delete_device_on_page_retry(max_retries=3)
                return StepResult.ok()
            except Exception as e:
                return StepResult.fail(FailureType.DELETE_FAILED, f"删除设备失败: {e}")

        return self.delete_device_with_guarantee(device_name, home_page)