import time

import allure
import pytest

from apps.Koocam.pages.page_event import EventPage
from apps.Koocam.pages.page_home import HomePage
from core.base_test_suite import BaseTestSuite
from core.driver import DriverManager
from utils.logger import logger


@pytest.mark.flaky(reruns=2, reruns_delay=5,
                   reason="用例失败后等待5秒重试，最多重试2次")
class TestKoocamSlidingEvent(BaseTestSuite):

    @pytest.fixture(autouse=True)
    def setup_class(self, keep_app_state):
        self.initialize_suite("event_video_play")
        self.driver = keep_app_state

        self.device_name = self.get_parameter("device_name")
        self.home_page = HomePage()
        self.event_page = EventPage()

    @pytest.fixture(autouse=True)
    def recovery(self, keep_app_state):
        """
        pytest 层面的恢复机制：
        - 每次用例执行前（包含 rerun 重试）检查 App 是否存活
        - 若 App 崩溃/驱动断连，DriverManager 自动重连重启
        - 重启后重新初始化页面对象并导航到事件页，确保用例从正确状态继续
        """
        try:
            DriverManager.heartbeat()
        except Exception:
            logger.warning("检测到驱动失效，正在重连...")
            DriverManager.restart_start_driver()
            time.sleep(3)
            self.home_page = HomePage()
            self.event_page = EventPage()
            self.home_page.click_event_button(self.device_name)
            time.sleep(3)

        yield

        # teardown：异常截图归到 Allure 报告
        try:
            self.event_page._take_screenshot(f"teardown_{self.get_current_time()}")
        except Exception:
            pass

    @pytest.mark.parametrize("loop_times", [1])  # 可参数化
    def test_cycle_play_all_videos(self, loop_times):
        """循环播放所有录像视频压测"""

        self.home_page.click_event_button(self.device_name)

        # 加载动画消失后，向暂停播放，再去异常信息匹配
        self.event_page.play_all_videos_from_top_option(loop_times)
        # # 图片识别
        # self.event_page.play_all_videos_from_top_option_debug_pillow(loop_times)
        # # 暂停播放后判断
        # self.event_page.play_all_videos_from_top_option_debug_play_button()
