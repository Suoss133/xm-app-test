import time
from .common import get_page_instance, take_screenshot, handle_error, log_step


# 等待出图
def wait_for_stream_play(app_name, live_stream_play = 60):
    """
    等待出图
    :param app_name:
    :param live_stream_play: 直播播放时长
    :return:
    """
    try:
        video = get_page_instance(app_name, "page_video_detail", "VideoDetailPage")
        start = time.time()
        duration = video.check_error_tips(start, live_stream_play)
        if duration is None:
            raise RuntimeError("出图失败")
        real_time = time.time() - start
        log_step(f"{app_name}出图成功，监控耗时：{real_time:.2f}秒，实际耗时：{duration:.2f}秒")
        return duration
    except Exception as e:
        handle_error(f"{app_name} 出图失败: {str(e)}")
        return None




