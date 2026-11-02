import time

from apps.base.base_video_detail import BaseVideoPlayDetailPage

class VideoDetailPage(BaseVideoPlayDetailPage):

    def __init__(self):
        super().__init__(
            page_name="视频播放页面",
            config_path="apps/baseus/config.yaml",
            page_config_name="video_detail"
        )

    def check_error_tips(self, start_time=None, live_stream_play=10):
        """
        校验是否出现错误
        返回: (load_duration, error_message)
        """
        if start_time is None:
            start_time = time.time()

        return super().check_error_tips(start_time, live_stream_play)