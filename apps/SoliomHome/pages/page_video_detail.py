import time

import allure

from apps.base.base_video_detail import BaseVideoPlayDetailPage
from core.yaml_utils import YamlUtils
from utils.logger import logger


class VideoDetailPage(BaseVideoPlayDetailPage):

    def __init__(self):
        super().__init__(
            page_name="视频播放页面",
            config_path="apps/SoliomHome/config.yaml",
            page_config_name="video_detail"
        )

        # 静音
        self.MUTE_BUTTON = YamlUtils.parse_locator(self.elements["mute_button"])

        # 截屏
        """com.xm.support.android:id/tv_screenshot"""
        self.SCREENSHOT_BUTTON = YamlUtils.parse_locator(self.elements["screenshot_button"])

    # 点击静音操作按钮
    def click_mute_button(self):
        """点击静音按钮"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击静音按钮"):
                self.click(self.MUTE_BUTTON)
        except Exception as e:
            self._handle_error(f"点击静音按钮失败: {str(e)}", "点击静音按钮失败")

    # 获取静音提示信息
    def get_mute_text(self):
        """获取静音提示信息"""
        try:
            mute_message = self.get_text(self.MUTE_BUTTON)
            logger.info(f"静音提示信息：{mute_message}")
            return mute_message
        except Exception as e:
            self._handle_error(f"获取静音提示信息失败: {str(e)}", "获取静音提示信息失败")

    def click_screenshot_button(self):
        """点击截图按钮"""
        try:
            with allure.step(f"执行时间：{self.get_current_time()} ---- 点击截图按钮"):
                self.click(self.SCREENSHOT_BUTTON)
        except Exception as e:
            self._handle_error(f"点击截图按钮失败: {str(e)}", "点击截图")

    def check_error_tips(self, start_time=None, live_stream_play=10):
        """
        校验是否出现错误
        返回: (load_duration, error_message)
        """
        if start_time is None:
            start_time = time.time()

        return super().check_error_tips(start_time, live_stream_play)