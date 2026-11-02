import time

import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait

from apps.base.base_video_detail import BaseVideoPlayDetailPage
from core.yaml_utils import YamlUtils
from utils.logger import logger
from selenium.webdriver.support import expected_conditions as EC


class VideoDetailPage(BaseVideoPlayDetailPage):

    def __init__(self):
        super().__init__(
            page_name="视频播放页面",
            config_path="apps/Humbirdy/config.yaml",
            page_config_name="video_detail"
        )

        # Humbirdy 开流失败弹窗定位器
        self.failure_dialog = {
            "dialog":(AppiumBy.ID,"com.birdlife.android:id/tv_title_tips"),
            "message":(AppiumBy.ID,"com.birdlife.android:id/tv_error_tips_info"),
            "cannel_button":(AppiumBy.ID,"com.birdlife.android:id/tv_cancel")
        }


    def _handle_failure_on_page(self,error_text) -> bool:
        """处理失败弹窗：读取失败原因，点击关闭按钮"""
        try:
            # 点击关闭按钮
            close_loc = self.failure_dialog.get("cannel_button")
            if close_loc:
                self.click(close_loc)
                logger.info("已点击关闭按钮")
                return True
            else:
                logger.warning("未找到关闭按钮")
                return False

        except Exception as e:
            logger.error(f"处理失败弹窗异常: {str(e)}")
            return False

    def check_error_tips(self, start_time=None, live_stream_play=10):
        """
        校验是否出现错误
        返回: (load_duration, error_message)
        """
        if start_time is None:
            start_time = time.time()

        return super().check_error_tips(start_time, live_stream_play)