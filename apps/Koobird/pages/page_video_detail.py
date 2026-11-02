import time

import allure

from apps.base.base_video_detail import BaseVideoPlayDetailPage
from core.yaml_utils import YamlUtils
from utils.logger import logger


class VideoDetailPage(BaseVideoPlayDetailPage):

    def __init__(self):
        super().__init__(
            page_name="视频播放页面",
            config_path="apps/koobird/config.yaml",
            page_config_name="video_detail"
        )

        # 关闭错误弹窗
        self.close_error_tips = YamlUtils.parse_locator(self.elements["close_error_tips"])

    def check_error_tips(self, start_time=None, live_stream_play=10):
        """
        校验是否出现错误
        Args:
            start_time: 开始计时时间戳
        """
        if start_time is None:
            start_time = time.time()

        return super().check_error_tips(start_time)

    # 处理出图失败错误，关闭错误弹窗
    def _handle_video_error(self):
        """
        处理出失败错误，关闭错误弹窗
        :return:
        """
        try:
           with allure.step(f"执行时间：{self.get_current_time()} ---- 关闭错误弹窗"):
               self.click(self.close_error_tips)
           logger.info("关闭错误弹窗")
        except Exception as e:
            logger.error("关闭错误弹窗失败")
            with allure.step(f"执行时间：{self.get_current_time()} ---- 关闭错误弹窗失败"):
                self._handle_error(f"关闭错误弹窗失败: {str(e)}", "关闭错误弹窗失败")
