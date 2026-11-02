# test_binding.py
import os
import time
import allure
import pytest

from core.base_test_suite import BaseTestSuite
from core.page_factory import create_pages
from utils.test_config import test_config, TestConfigManager
from utils.logger import logger
from utils.excel_reporter import excel_reporter
from core.result import StepResult, FailureType
from core.recovery_policy import get_recovery_action, RecoveryAction
from core.exceptions import RestartRequired, BusinessTestFailure
from core.allure_helper import get_friendly_title

task_name = test_config.get_suite_parameter("task_name")
TASK_FILE = excel_reporter.start_new_task("binding", task_name or None)
logger.info(f"📊 绑定压测报告文件: {TASK_FILE}")


@allure.epic("蓝牙绑定压测模块")
@allure.feature("蓝牙绑定压测模块")
class Testbinding(BaseTestSuite):
    test_counter = 0
    _delete_failed = False
    SUITE_NAME = "binding"
    _task_started = False

    @pytest.fixture(autouse=True)
    def setup(self, keep_app_state):
        if self._delete_failed:
            pytest.skip("删除设备失败，跳过后续测试")

        self.initialize_suite("binding")
        self.driver = keep_app_state

        app = os.environ.get("CURRENT_APP") or TestConfigManager.get_current_app()
        logger.info(f"[蓝牙绑定压测] 当前 App = {app}")
        pager = create_pages(app)


        self.home_page = pager["HomePage"]()
        self.add_device_page = pager["AddDevicePage"]()
        self.setting_page = pager["SettingsDevicePage"]()
        self.video_detail_page = pager["VideoDetailPage"]()
        self.result = None

        self.device_sn = self.suite_config.get("parameter", {}).get("device_sn")
        self.wifi_ssid = self.suite_config.get("parameter", {}).get("wifi_ssid")
        self.wifi_password = self.suite_config.get("parameter", {}).get("wifi_password")
        raw_sleep = self.suite_config.get("parameter", {}).get("sleep_control")
        try:
            self.sleep_control = int(raw_sleep) if raw_sleep not in (None, "") else 0
        except (ValueError, TypeError):
            self.sleep_control = 0

        Testbinding.test_counter += 1
        self.device_default_name = "auto_test"

    repeat_count = test_config.get_repeat_count("binding", 1)

    @pytest.mark.parametrize('iteration', range(repeat_count))
    def test_add_device_main(self, iteration):
        start_time = time.time()
        start_time_str = self.home_page.get_current_time()
        step_results = []
        final_result = StepResult.ok()

        try:
            # ========== 1. 点击添加设备 ==========
            r = self.home_page.click_add_device_button()
            step_results.append(("点击添加设备", r))
            if not r.success:
                final_result = r
                self._finish_and_recover(final_result, start_time_str, start_time, step_results)
                return

            # ========== 2. 选择蓝牙设备 ==========
            r = self.add_device_page.select_device_by_sn(self.device_sn)
            step_results.append(("选择蓝牙设备", r))
            if not r.success:
                final_result = r
                self._finish_and_recover(final_result, start_time_str, start_time, step_results)
                return

            # ========== 3. WiFi & 配网 ==========
            self.add_device_page.wait_for_loading_to_disappear()
            r = self.add_device_page.verify_page_jump(
                self.add_device_page.WIFI_PAGE_IDENTIFIER, page_name="Wi-Fi搜索页面"
            )
            step_results.append(("进入WiFi页面", r))
            if not r.success:
                final_result = r
                self._finish_and_recover(final_result, start_time_str, start_time, step_results)
                return

            r = self.add_device_page.select_network(self.wifi_ssid, self.wifi_password)
            step_results.append(("输入WiFi", r))
            if not r.success:
                final_result = r
                self._finish_and_recover(final_result, start_time_str, start_time, step_results)
                return

            r = self.add_device_page.verify_page_jump(
                self.add_device_page.CONNECT_PAGE_IDENTIFIER, page_name="等待配网状态中页面"
            )
            step_results.append(("进入配网页", r))

            r = self.add_device_page.check_network_config_status(self.device_sn)
            step_results.append(("配网结果", r))

            if r.success:
                self.result = r.data  # {"text": "连接成功"}
            else:
                self.result = r.data or {"text": r.message}
                final_result = r
                self._finish_and_recover(final_result, start_time_str, start_time, step_results)
                return

            # ========== 4. 设置名称 & 关闭引导 ==========
            r = self.add_device_page.set_device_name(self.device_default_name)
            step_results.append(("设置设备名称", r))
            self.home_page.close_popup()
            self.add_device_page.auto_close_install_guide()
            
            self.home_page.pull_to_refresh()

            # ========== 5. 校验出图（失败只记录，不中断） ==========
            r = self._check_live_view()
            step_results.append(("出图校验", r))
            if not r.success:
                final_result = r   # 记录失败，但继续执行删除

            # ========== 6. 删除设备 ==========
            r = self.home_page.click_setting_button(self.device_default_name)
            step_results.append(("进入设置", r))
            if not r.success:
                final_result = r
            else:
                jump = self.setting_page.verify_page_jump(
                    self.setting_page.setting_page_title,
                    page_name="设备设置页面",
                )
                step_results.append(("设置页跳转", jump))
                time.sleep(self.sleep_control)

                del_result = self.setting_page.delete_device_by_result(
                    self.result,
                    self.device_default_name,
                    home_page=self.home_page,
                )
                step_results.append(("删除设备", del_result))
                if not del_result.success:
                    final_result = del_result
                    # 删除失败禁止继续绑定（蓝牙不会再开）
                    Testbinding._delete_failed = True

            time.sleep(3)

        except Exception as e:
            final_result = StepResult.fail(FailureType.UNKNOWN, str(e))
            step_results.append(("未知异常", final_result))

        self._finish_and_recover(final_result, start_time_str, start_time, step_results)

    def _check_live_view(self) -> StepResult:
        """出图检查封装"""
        start = time.time()

        r = self.home_page.click_live_button(self.device_default_name)
        if not r.success:
            return r

        result = self.video_detail_page.check_error_tips(start, 10)

        self.home_page.back()

        if self.sleep_control > 0:
            time.sleep(self.sleep_control)
        return result

    def _finish_and_recover(self, final_result: StepResult, start_time_str: str,
                            start_time: float, step_results: list):
        end_time = time.time()
        end_time_str = self.home_page.get_current_time()
        duration = end_time - start_time

        test_result = "PASS" if final_result.success else "FAIL"
        error_msg = final_result.message if not final_result.success else ""

        # 友好标题
        allure.dynamic.title(get_friendly_title(self.test_counter, final_result))
        allure.dynamic.description(
            f"开始: {start_time_str}<br>结束: {end_time_str}<br>"
            f"耗时: {duration:.2f}s<br>结果: {test_result}<br>错误: {error_msg}"
        )

        self._save_to_excel({
            "测试次数": self.test_counter,
            "测试开始时间": start_time_str,
            "测试结束时间": end_time_str,
            "执行中耗时": f"{duration:.2f}",
            "执行结果": test_result,
            "错误信息": error_msg,
        })

        if not final_result.success:
            action = get_recovery_action(self.SUITE_NAME, final_result.failure_type)
            logger.info(f"失败类型: {final_result.failure_type.name} → 动作: {action.name}")

            if action == RecoveryAction.STOP_SUITE:
                Testbinding._delete_failed = True
                pytest.skip(final_result.message)

            elif action == RecoveryAction.RESTART_APP:
                # 需要重启：先让用例失败，再抛重启信号
                raise RestartRequired(final_result.message, final_result.failure_type)

            else:
                # CONTINUE（出图失败等）：只让用例失败，不重启
                raise BusinessTestFailure(
                    final_result.message,
                    failure_type=final_result.failure_type
                )

    def _save_to_excel(self, test_data):
        try:
            # 直接使用模块级变量
            excel_reporter.append_to_report(test_data, TASK_FILE)
        except Exception as e:
            logger.error(f"保存Excel失败: {e}")