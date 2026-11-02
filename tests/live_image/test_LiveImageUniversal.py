# tests/live_image/test_LiveImageUniversal.py
import os
import subprocess
import time
import allure
import pytest

from core.allure_helper import get_friendly_title
from core.base_test_suite import BaseTestSuite
from utils.logger import logger
from utils.test_config import test_config, TestConfigManager
from utils.excel_reporter import excel_reporter
from core.result import StepResult, FailureType
from core.recovery_policy import get_recovery_action, RecoveryAction
from core.exceptions import RestartRequired, BusinessTestFailure
from core.page_factory import create_pages


task_name = test_config.get_suite_parameter("task_name")
TASK_FILE = excel_reporter.start_new_task("LiveImageUniversal", task_name or None)
logger.info(f"📊 开流压测报告文件: {TASK_FILE}")


def get_current_time(format_str="%Y-%m-%d %H:%M:%S"):
    """获取当前系统时间"""
    return time.strftime(format_str, time.localtime())


@allure.epic("通用出图压测模块")
@allure.feature("出图稳定性压测")
class TestLiveImageUniversal(BaseTestSuite):
    test_counter = 0
    SUITE_NAME = "LiveImageUniversal"

    @pytest.fixture(autouse=True)
    def setup(self, keep_app_state):
        self.initialize_suite("LiveImageUniversal")
        self.driver = keep_app_state

        app = os.environ.get("CURRENT_APP") or TestConfigManager.get_current_app()
        logger.info(f"[出图压测] 当前 App = {app}")
        pager = create_pages(app)

        self.home_page = pager["HomePage"]()
        self.video_detail_page = pager['VideoDetailPage']()
        self.login_page = pager['LoginPage']()

        self.device_title = self.get_parameter("device_title")
        self.sleep_control = self.get_parameter("sleep_control") or 0
        self.live_stream_play = self.get_parameter("live_stream_play") or 10

        self.load_duration = None
        self.start_time = None
        self.end_time = None

    repeat_count = test_config.get_repeat_count("LiveImageUniversal", 1)

    @pytest.mark.parametrize('iteration', range(repeat_count))
    def test_live_image_universal(self, iteration):
        """出图压测 """
        TestLiveImageUniversal.test_counter += 1
        iteration_num = iteration + 1

        start_time_str = "N/A"
        end_time_str = "N/A"
        duration = 0.0
        final_result = StepResult.ok()

        try:
            # 登录页兜底
            if self.login_page.get_login_identifier_element():
                logger.warning("当前处于登录页面，尝试重新登录")
                self.login_page.click_login_button()
                time.sleep(2)

            # 执行主逻辑（返回 StepResult）
            final_result = self._main_test_logic()

            # 时间统计
            start_time_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))
                if self.start_time else "N/A"
            )
            end_time_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time))
                if self.end_time else "N/A"
            )

            load_duration = 0.0
            if final_result.data and isinstance(final_result.data, dict):
                load_duration = final_result.data.get("total_duration", 0.0)
            self.load_duration = load_duration

            error_str = final_result.message if not final_result.success else ""
            load_duration_str = f"{load_duration:.2f}" if load_duration else "N/A"
            test_result = "PASS" if final_result.success else "FAIL"

            # Allure
            allure.dynamic.title(
                f"第 {iteration_num} 次出图压测 - {'成功' if final_result.success else '失败'}"
            )
            allure.dynamic.description(
                f"执行设备：{self.device_title}<br>"
                f"执行开始时间：{start_time_str}<br>"
                f"执行结束时间：{end_time_str}<br>"
                f"出图耗时：{load_duration_str} 秒<br>"
                f"错误信息：{error_str}"
            )

            # Excel（只在这里写一次）
            self._save_to_excel({
                "测试次数": TestLiveImageUniversal.test_counter,
                "测试开始时间": start_time_str,
                "测试结束时间": end_time_str,
                "出图耗时(秒)": load_duration_str,
                "错误信息": error_str,
                "执行结果": test_result,
            })

            if not final_result.success:
                action = get_recovery_action(self.SUITE_NAME, final_result.failure_type)
                if action == RecoveryAction.RESTART_APP:
                    raise RestartRequired(final_result.message, final_result.failure_type)
                else:
                    # 让 Allure 显示 Failed，但不重启
                    raise BusinessTestFailure(final_result.message, final_result.failure_type)

        except RestartRequired:
            # 需要重启的信号继续向上抛，让 conftest 处理
            raise
        except BusinessTestFailure:
            # 业务失败已经在上面保存过 Excel，直接重新抛出即可
            raise
        except Exception as e:
            # 只有真正的未知异常才在这里补救保存
            if not self.end_time:
                self.end_time = time.time()

            start_time_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))
                if self.start_time else "N/A"
            )
            end_time_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time))
                if self.end_time else "N/A"
            )
            error_str = str(e)

            allure.dynamic.title(get_friendly_title(self.test_counter, final_result))
            allure.dynamic.description(
                f"执行设备：{self.device_title}<br>"
                f"执行开始时间：{start_time_str}<br>"
                f"执行结束时间：{end_time_str}<br>"
                f"错误信息：{error_str}"
            )

            self._save_to_excel({
                "测试次数": TestLiveImageUniversal.test_counter,
                "测试开始时间": start_time_str,
                "测试结束时间": end_time_str,
                "出图耗时(秒)": '',
                "错误信息": error_str,
                "执行结果": "FAIL",
            })
            raise

    def _main_test_logic(self) -> StepResult:
        """主测试逻辑，统一返回 StepResult"""


        with allure.step(f"1. 执行时间{get_current_time()}，点击直播按钮"):
            r = self.home_page.click_live_button(self.device_title)
            if not r.success:
                return r
        self.start_time = time.time()  # 记录点击时刻作为计时起点

        with allure.step(f"2. 执行时间{get_current_time()}，出图检测"):
            result = self.video_detail_page.check_error_tips(
                self.start_time, self.live_stream_play
            )

        with allure.step(f"3. 执行时间{get_current_time()}，返回首页"):
            self.home_page.back()

        with allure.step(f"4. 等待设备休眠 {self.sleep_control} 秒"):
            if self.sleep_control > 0:
                logger.info(f"等待设备休眠 {self.sleep_control} 秒")
                time.sleep(self.sleep_control)


        self.end_time = time.time()
        return result

    def _save_to_excel(self, test_data):
        try:
            # 直接使用模块级变量
            excel_reporter.append_to_report(test_data, TASK_FILE)
        except Exception as e:
            logger.error(f"保存Excel失败: {e}")