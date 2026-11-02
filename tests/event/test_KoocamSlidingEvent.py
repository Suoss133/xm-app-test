import time

import allure
import pytest

from apps.Koocam.pages.page_event import EventPage
from apps.Koocam.pages.page_home import HomePage
from core.base_test_suite import BaseTestSuite
from utils.logger import logger
from utils.test_config import test_config


@allure.epic("事件模块")
@allure.feature("时间轴滑动压测 - 复现视频加载失败")
class TestKoocamSlidingEvent(BaseTestSuite):

    @pytest.fixture(autouse=True)
    def setup_class(self, keep_app_state):
        self.initialize_suite("KoocamSlidingEvent")
        self.driver = keep_app_state
        self.device_name = self.get_parameter("device_name")
        self.home_page = HomePage()
        self.event_page = EventPage()

        self.home_page.click_event_button(self.device_name)
        self.event_page.click_card_record()
        time.sleep(5)  # 等待页面稳定

    swipe_test_count = test_config.get_repeat_count("swipe_test_count", 1000)

    @allure.story("随机水平滑动时间轴压测")
    @pytest.mark.parametrize("repeat_index", range(1))  # 可改为多次运行
    def test_random_horizontal_swipe_stress(self, repeat_index):
        try:
            with allure.step("完整滑动压测"):
                self.event_page.swipe_event_random(
                    min_distance=150,
                    max_distance=450,
                    total_cycles=self.swipe_test_count
                )
        except Exception as e:
            allure.attach(
                f"压测异常: {str(e)}",
                name="异常详情",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.fail(f"滑动压测失败: {e}")