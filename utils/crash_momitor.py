# App闪退监控
import traceback
from datetime import datetime

from core.driver import DriverManager
from utils.logger import logger


class CrashMonitor:

    @staticmethod
    def is_app_crashed(e):
        """判断是否发生App闪退"""
        crash_keywords = [
            "NoSuchWindowException",
            "SessionNotCreatedException",
            "An unknown server-side error occurred",
            "Process not found",
            "Failed to establish session"
        ]
        error_msg = str(e)
        return any(keyword in error_msg for keyword in crash_keywords)


    @staticmethod
    def handle_crash(test_case_name):
        """处理App闪退"""
        try:
            # 记录闪退日志
            crash_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"====== 用例[{test_case_name}]在{crash_time}发生闪退 ======")
            logger.error(traceback.format_exc())

            try:
                driver = DriverManager.get_driver()
                screenshot_name = f"crash_{test_case_name}_{crash_time.replace(':', '-')}"
                driver.save_screenshot(f"reports/screenshots/{screenshot_name}.png")
                logger.info(f"闪退截图已保存: {screenshot_name}.png")

            except Exception as e:
                logger.error(f"保存闪退截图时出错: {str(e)}")

            # 重启App
            logger.info("开始重启App，恢复测试环境")
            DriverManager.keep_start_driver()
        except Exception as e:
            logger.error(f"处理App闪退时出错: {str(e)}")