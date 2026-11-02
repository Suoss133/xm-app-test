# base_video_detail.py
import threading
import time
import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.base_page import BasePage
from core.yaml_utils import YamlUtils
from core.result import StepResult, FailureType
from utils.logger import logger


class BaseVideoPlayDetailPage(BasePage):
    """视频播放详情页基类"""

    def __init__(self, page_name, config_path, page_config_name, handle_popup=False):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 10, 0.5)
        self.handle_popup = handle_popup

        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        self.LOADING = YamlUtils.parse_locator(self.elements["loading"])
        self.ERROR_TIPS = YamlUtils.parse_locator(self.elements["error_tips"])

        # 守护线程控制变量
        self._popup_daemon_thread = None
        self._daemon_running = False

        self.popup_text_loc = (AppiumBy.XPATH,
                          '//android.widget.TextView[@text="长时间观看实时画面将加速设备的电量消耗，你想继续吗?"]')
        self.cancel_btn_loc = (AppiumBy.ID, 'com.xm.support.android:id/tv_cancel')


    def _popup_daemon_loop(self):
        """后台线程循环：每5s检测弹窗，出现点击继续观看"""
        logger.info("直播弹窗守护线程已启动")
        while self._daemon_running:
            try:
                # 短等待1秒判断弹窗是否可见
                WebDriverWait(self.driver, timeout=1).until(
                    EC.visibility_of_element_located(self.popup_text_loc)
                )
                logger.warning("检测到【长时间观看电量消耗】弹窗，点击继续观看按钮")
                self.click(self.cancel_btn_loc)
            except (TimeoutException, NoSuchElementException):
                # 弹窗不存在，直接跳过
                pass
            except Exception as e:
                # driver失效、app闪退等异常，直接退出守护线程
                logger.debug(f"弹窗守护线程异常(大概率app闪退): {str(e)}")
                break
            time.sleep(5)
        logger.info("直播弹窗守护线程已退出")


    def start_popup_daemon(self):
        """启动弹窗后台守护线程，daemon=True主程序退出线程自动销毁"""
        if self._popup_daemon_thread and self._popup_daemon_thread.is_alive():
            logger.info("弹窗守护线程已经在运行，无需重复启动")
            return
        self._daemon_running = True
        self._popup_daemon_thread = threading.Thread(target=self._popup_daemon_loop, daemon=True)
        self._popup_daemon_thread.start()


    def stop_popup_daemon(self):
        """停止弹窗守护线程，用例结束调用"""
        self._daemon_running = False
        if self._popup_daemon_thread:
            self._popup_daemon_thread.join(timeout=8)

    # 处理出图失败
    def _handle_video_error(self):
        """
        处理直播出图失败错误信息，由子类实现
        """
        pass

    def check_error_tips(self, start_time=None, live_stream_play: int = 10) -> StepResult:
        """
        校验出图结果，返回 StepResult
        start_time: 点击直播按钮的时间
        """
        if start_time is None:
            start_time = time.time()

        try:
            # ===== 第一步：等待 Loading 出现 =====
            logger.info("等待 Loading 元素出现...")
            try:
                WebDriverWait(self.driver, timeout=5).until(
                    EC.visibility_of_element_located(self.LOADING)
                )
                logger.info("Loading 元素已出现")
            except TimeoutException:
                self._take_screenshot(f"loading_never_appear_{self.get_current_time()}")
                total_duration = time.time() - start_time
                return StepResult.fail(
                    FailureType.LIVE_VIEW_FAILED,
                    "Loading 元素从未出现，可能点击直播失败",
                    data={"total_duration": total_duration}
                )

            # ===== 第二步：等待 Loading 消失 =====
            try:
                WebDriverWait(self.driver, timeout=300, poll_frequency=0.5).until_not(
                    EC.visibility_of_element_located(self.LOADING)
                )
                logger.info("Loading 已消失，直播画面已显示")
            except TimeoutException:
                total_duration = time.time() - start_time
                self._take_screenshot(f"loading_timeout_{self.get_current_time()}")
                return StepResult.fail(
                    FailureType.LIVE_VIEW_FAILED,
                    f"开流超时（Loading 超过300秒未消失）",
                    data={"total_duration": total_duration}
                )

            # ===== 计算完整的开流耗时 =====
            total_duration = time.time() - start_time
            logger.info(f"完整开流耗时: {total_duration:.2f}秒")

            # ===== 第三步：检测错误提示（页面上的错误文本） =====
            try:
                logger.info("检测出图是否失败...")
                error_tips_element = WebDriverWait(self.driver, live_stream_play, 2).until(
                    EC.visibility_of_element_located(self.ERROR_TIPS)
                )
                if error_tips_element.is_displayed():
                    error_text = error_tips_element.text.strip()
                    self._take_screenshot(f"出图失败_{self.get_current_time()}")

                    # ===== 新增：调用子类的失败处理方法 =====
                    self._handle_failure_on_page(error_text)

                    return StepResult.fail(
                        FailureType.LIVE_VIEW_FAILED,
                        f"{error_text}",
                        data={"total_duration": total_duration}
                    )
            except TimeoutException:
                pass  # 无错误提示

            # ===== 第五步：开流成功 =====
            with allure.step(f"执行时间：{self.get_current_time()} ---- 开流成功，耗时: {total_duration:.2f}秒"):
                pass
            self._take_screenshot(f"开流成功_耗时{total_duration:.2f}秒")
            allure.dynamic.parameter("开流耗时(秒)", f"{total_duration:.2f}")
            return StepResult.ok(data={"total_duration": total_duration})

        except Exception as e:
            total_duration = time.time() - start_time
            self._take_screenshot(f"开流检测异常_{self.get_current_time()}")
            return StepResult.fail(
                FailureType.LIVE_VIEW_FAILED,
                f"开流检测异常: {str(e)}",
                data={"total_duration": total_duration},
            )

    # ===== 以下方法由子类实现 =====
    def _is_failure_dialog_present(self) -> bool:
        """
        检测失败弹窗是否存在，由子类实现
        默认返回 False
        """
        return False

    def _get_failure_dialog_message(self) -> str:
        """
        获取失败弹窗的错误信息，由子类实现
        默认返回空字符串
        """
        return ""

    def _handle_failure_dialog(self):
        """
        处理失败弹窗（点击关闭/返回按钮），由子类实现
        默认不做任何操作
        """
        pass

    def _handle_failure_on_page(self, error_text: str):
        """
        处理页面上的失败提示（点击返回首页等），由子类实现
        默认不做任何操作
        """
        pass