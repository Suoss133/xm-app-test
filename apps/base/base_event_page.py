import random
import subprocess
import time
from datetime import datetime
import os

import allure
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from core.base_page import BasePage
from core.yaml_utils import YamlUtils
from utils.logger import logger
from utils.excel_reporter import excel_reporter


def run_adb(args, timeout=15):
    """执行 adb 命令，返回 (stdout, stderr)"""
    cmd = ["adb"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # 不抛异常，方便捕获
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "ADB 命令超时"
    except Exception as e:
        return "", str(e)


class BaseEventDevicePage(BasePage):
    """设备事件页面"""

    # 触发视频事件坐标（可配置）
    X, Y = (609, 369)

    def __init__(self, page_name, config_path, page_config_name):
        super().__init__(page_name)
        self.wait = WebDriverWait(self.driver, 15, 0.5)
        # 加载当前App的页面元素配置
        self.elements = YamlUtils.get_element_locator(
            file_path=config_path,
            page_name=page_config_name
        )

        # 事件时间
        self.EVENT_TIME = YamlUtils.parse_locator(self.elements["event_time"])
        # 下载视频按钮
        self.DOWNLOAD_VIDEO_BUTTON = YamlUtils.parse_locator(self.elements["download_button"])
        # 录像片段时段
        self.RECORD_TIME_PERIOD = YamlUtils.parse_locator(self.elements["record_time_period"])
        # 下载状态
        self.DOWNLOAD_STATUS = YamlUtils.parse_locator(self.elements["download_status"])
        # ---------下载失败弹窗----------
        # 取消下载
        self.DOWNLOAD_FAIL_CANCEL = YamlUtils.parse_locator(self.elements["download_fail_cancel"])
        # 重新下载
        self.DOWNLOAD_FAIL_RETRY = YamlUtils.parse_locator(self.elements["download_fail_retry"])
        # ---------下载成功弹窗----------
        # 确认
        self.DOWNLOAD_SUCCESS_CONFIRM = YamlUtils.parse_locator(self.elements["download_success_confirm"])
        # 分享
        self.DOWNLOAD_SUCCESS_SHARE = YamlUtils.parse_locator(self.elements["download_success_share"])
        # 加载中
        self.LOADING = YamlUtils.parse_locator(self.elements["loading"])
        # 卡录
        self.sd_record = YamlUtils.parse_locator(self.elements["sd_record"])

        # 滑动防卡死状态
        self._consecutive_left = 0
        self._force_right_count = 0
        self._initial_right_done = False
        self._last_event_time = None

        # 截图目录
        self.screenshot_dir = self._get_screenshot_dir()
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # 播放异常检测
        self.error_tips = YamlUtils.parse_locator(self.elements["error_tips"])
        self.error_tips2 = YamlUtils.parse_locator(self.elements["error_tips2"])

    def wait_for_loading_to_disappear(self, timeout=300, poll_interval=0.3, initial_wait=0.3):
        """
        等待加载动画消失（优化版：ADB XML 检查 + 渐进式轮询）

        Args:
            timeout (int): 最大等待时间（秒），默认 300 秒
            poll_interval (float): 检查间隔（秒），默认 0.3 秒
            initial_wait (float): 首次检查前的等待时间（秒），默认 0.3 秒

        Returns:
            bool: 加载元素消失返回 True，超时返回 False
        """
        start_time = time.time()

        # 首次等待：给 UI 一个初始反应时间
        time.sleep(initial_wait)

        # 渐进式轮询策略：先快后慢
        fast_polls = 5   # 前 N 次用较短间隔
        slow_interval = 0.5  # 之后用较长间隔

        poll_count = 0
        while time.time() - start_time < timeout:
            try:
                # 使用 ADB 获取当前页面 XML，检查加载元素是否可见
                if self._is_loading_visible_adb():
                    poll_count += 1
                    # 根据轮询次数选择间隔
                    interval = poll_interval if poll_count <= fast_polls else slow_interval
                    time.sleep(interval)
                    continue
                else:
                    elapsed = time.time() - start_time
                    logger.info(f"加载动画已消失（耗时 {elapsed:.1f}s）")
                    return True
            except Exception as e:
                logger.debug(f"检查加载状态时异常：{str(e)}，可能元素已不存在")
                return True

        logger.warning(f"等待加载动画消失超时（{timeout}秒）")
        return False

    def _is_loading_visible_adb(self):
        """
        通过 ADB dumpsys 检查加载动画是否可见
        比 DOM 查询更准确，反映真实 UI 状态

        Returns:
            bool: 加载动画可见返回 True，不可见返回 False
        """
        try:
            # 获取当前界面的 XML dump
            result = subprocess.run(
                ["adb", "shell", "uiautomator2", "dumpsys", "window", "windows"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )

            # 检查加载元素是否在 XML 中且可见（uiautomator2 中 visible=true）
            # loading 元素的 resource-id 通常包含 "loading" 或 "layout_loading"
            if result.returncode == 0:
                xml_content = result.stdout.lower()
                # 如果 XML 中存在 loading 相关元素，认为还在加载
                if "loading" in xml_content and "com.xm.support.android:id" in xml_content:
                    return True

            # Fallback: 检查 DOM
            return self.is_element_visible(self.LOADING, timeout=0)

        except subprocess.TimeoutExpired:
            logger.debug("ADB 检查超时，fallback 到 DOM 检查")
            return self.is_element_visible(self.LOADING, timeout=0)
        except Exception as e:
            logger.debug(f"ADB 检查异常：{str(e)}，fallback 到 DOM 检查")
            return self.is_element_visible(self.LOADING, timeout=0)

    def _get_screenshot_dir(self):
        date_str = datetime.now().strftime("%Y%m%d")
        return os.path.join("screenshots", date_str)

    def _adb_screenshot(self,step_name=""):
        """用 ADB 截图并附加到 Allure 报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        local_path = f"./screenshots/{filename}"

        os.makedirs("./screenshots", exist_ok=True)

        # 1. 在手机上截图
        subprocess.run(["adb", "shell", "screencap", "-p", f"/sdcard/{filename}"], check=True)

        # 2. 拉取到电脑
        subprocess.run(["adb", "pull", f"/sdcard/{filename}", local_path], check=True)

        # 3. 删除手机上的文件（可选，保持干净）
        subprocess.run(["adb", "shell", "rm", f"/sdcard/{filename}"], check=True)

        # 4. 附加到 Allure
        with open(local_path, "rb") as f:
            allure.attach(
                f.read(),
                name=f"{step_name} - {timestamp}" if step_name else timestamp,
                attachment_type=allure.attachment_type.PNG
            )

        print(f"已附加截图到 Allure: {filename}")
        return local_path

    def _adb_get_screen_size(self):
        try:
            adb = self._adb_base_args()
            result = subprocess.run(
                adb + ["shell", "wm", "size"],
                capture_output=True, text=True, timeout=5, check=True
            )
            output = result.stdout.strip()
            if "x" in output:
                size_str = output.split(":")[-1].strip()
                w, h = map(int, size_str.split("x"))
                return {"width": w, "height": h}
        except Exception as e:
            logger.warning(f"获取屏幕尺寸失败: {e}，使用默认 720x1600")
        return {"width": 720, "height": 1600}

    def adb_random_horizontal_swipe(self, y_center=680, y_range=80, min_distance=120, max_distance_factor=2.0):
        """
        ADB 纯水平随机滑动（只能左右，不能上下）
        - y 坐标在 y_center ± y_range 内随机（模拟手指不完全水平）
        - x 方向随机左右，距离随机
        """
        try:
            size = self._adb_get_screen_size()
            w = size["width"]

            # 随机 y 坐标（在时间轴附近小范围浮动）
            y_start = random.randint(y_center - y_range, y_center + y_range)

            # 随机起点 x（偏左或偏右）
            if random.random() < 0.5:
                start_x = random.randint(50, int(w * 0.4))          # 偏左 → 向右滑
                direction = "右"
            else:
                start_x = random.randint(int(w * 0.6), w - 50)      # 偏右 → 向左滑
                direction = "左"

            # 滑动距离
            distance = random.randint(min_distance, int(min_distance * max_distance_factor))
            if direction == "右":
                end_x = min(start_x + distance, w - 50)
            else:
                end_x = max(start_x - distance, 50)

            # y 终点小幅偏移（保持水平感）
            y_end = random.randint(y_center - y_range//2, y_center + y_range//2)

            duration = random.randint(400, 900)

            cmd = f"adb shell input swipe {start_x} {y_start} {end_x} {y_end} {duration}"
            logger.info(f"ADB 水平滑动: {cmd}  方向:{direction}")
            subprocess.run(cmd, shell=True, check=True, timeout=10)

            return start_x, y_start, end_x, y_end, direction

        except Exception as e:
            logger.error(f"ADB 水平滑动失败: {e}")
            return None, None, None, None, "失败"

    def swipe_event_random(self, min_distance=150, max_distance=450, total_cycles=50):
        """
        随机水平滑动时间轴压测
        - Y 坐标自动取时间轴中心
        - 左右滑动距离随机
        - 检测到播放异常只记录，不中断压测
        """
        # 1. 获取时间轴中心 Y（整轮复用）
        try:
            center_y = self.get_timeline_center_y()
        except Exception as e:
            logger.error(f"无法获取时间轴坐标，终止滑动: {e}")
            raise

        logger.info(f"本次压测使用时间轴 center_y = {center_y}")

        # ==================== 初始化强制右滑 ====================
        if not getattr(self, "_initial_right_done", False):
            init_cycles = random.randint(8, 15)  # 建议不要太多
            logger.info(f"初始强制向右滑动 {init_cycles} 次进入历史")

            for init_cycle in range(1, init_cycles + 1):
                init_cycle_start = datetime.now()
                logger.info(f"初始化滑动轮次 {init_cycle}/{init_cycles}")

                with allure.step(f"初始化滑动 {init_cycle}/{init_cycles}"):
                    try:
                        self.adb_swipe_right(
                            y_coordinate=center_y,
                            min_distance=min_distance,
                            max_distance=max_distance
                        )
                        self.wait_for_loading_to_disappear(timeout=30)

                        current_play_time = "未知"
                        try:
                            current_play_time = self.get_current_play_time()
                        except Exception as e:
                            logger.warning(f"初始化获取播放时间失败: {e}")

                        is_normal, error_msg = self.check_play_exception()
                        result = "PASS" if is_normal else f"FAIL - {error_msg}"

                        shot_path = self._adb_screenshot(f"init_slide_{init_cycle}")

                        row = {
                            "运行次数": f"初始化_{init_cycle}",
                            "当前播放时间": current_play_time,
                            "结果": result,
                            "截图路径": shot_path or "截图失败",
                            "滑动方向": "右（初始化）",
                            "轮次开始时间": init_cycle_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        }
                        excel_reporter.append_to_report(row, "timeline_slide_stress.xlsx")

                        if not is_normal:
                            logger.error(f"初始化滑动 {init_cycle} 检测到播放异常: {error_msg}")
                            allure.attach(
                                f"初始化异常 - 当前时间: {current_play_time}\n错误: {error_msg}",
                                name=f"初始化滑动{init_cycle}异常",
                                attachment_type=allure.attachment_type.TEXT
                            )

                    except Exception as e:
                        logger.error(f"初始化滑动 {init_cycle} 异常: {e}")
                        fail_path = self._adb_screenshot(f"init_fail_{init_cycle}")
                        fail_row = {
                            "运行次数": f"初始化_{init_cycle}",
                            "当前播放时间": "未知",
                            "结果": f"FAIL - 异常: {str(e)}",
                            "截图路径": fail_path or "失败",
                            "滑动方向": "右（初始化）",
                            "轮次开始时间": init_cycle_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        }
                        excel_reporter.append_to_report(fail_row, "timeline_slide_stress.xlsx")

            self._initial_right_done = True

        # ==================== 主滑动循环 ====================
        for cycle in range(1, total_cycles + 1):
            cycle_start = datetime.now()
            logger.info(f"=== 滑动轮次 {cycle}/{total_cycles} 开始 ===")

            with allure.step(f"滑动轮次 {cycle}/{total_cycles}"):
                try:
                    # 防连续左滑卡死
                    if getattr(self, "_consecutive_left", 0) >= 4:
                        direction = "右（防卡）"
                        self._consecutive_left = 0
                        self.adb_swipe_right(
                            y_coordinate=center_y,
                            min_distance=min_distance,
                            max_distance=max_distance
                        )
                    else:
                        if random.random() < 0.70:  # 70% 右滑
                            direction = "右"
                            self._consecutive_left = 0
                            self.adb_swipe_right(
                                y_coordinate=center_y,
                                min_distance=min_distance,
                                max_distance=max_distance
                            )
                        else:
                            direction = "左"
                            self._consecutive_left = getattr(self, "_consecutive_left", 0) + 1
                            self.adb_swipe_left(
                                y_coordinate=center_y,
                                min_distance=min_distance,
                                max_distance=max_distance
                            )

                    self.wait_for_loading_to_disappear(timeout=30)

                    current_play_time = "未知"
                    try:
                        current_play_time = self.get_current_play_time()
                    except Exception as e:
                        logger.warning(f"获取播放时间失败: {e}")

                    is_normal, error_msg = self.check_play_exception()
                    result = "PASS" if is_normal else f"FAIL - {error_msg}"

                    shot_path = self._adb_screenshot(f"cycle_{cycle}_{direction}")

                    row = {
                        "运行次数": cycle,
                        "当前播放时间": current_play_time,
                        "结果": result,
                        "截图路径": shot_path or "截图失败",
                        "滑动方向": direction,
                        "轮次开始时间": cycle_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    }
                    excel_reporter.append_to_report(row, "timeline_slide_stress.xlsx")

                    if not is_normal:
                        logger.error(f"轮次 {cycle} 检测到播放异常: {error_msg}")
                        allure.attach(
                            f"播放异常 - 当前时间: {current_play_time}\n错误: {error_msg}",
                            name=f"轮次{cycle}播放异常",
                            attachment_type=allure.attachment_type.TEXT
                        )

                except Exception as e:
                    logger.error(f"轮次 {cycle} 异常: {e}")
                    fail_path = self._adb_screenshot(f"fail_{cycle}")
                    fail_row = {
                        "运行次数": cycle,
                        "当前播放时间": "未知",
                        "结果": f"FAIL - 异常: {str(e)}",
                        "截图路径": fail_path or "失败",
                        "滑动方向": "异常",
                        "轮次开始时间": cycle_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    }
                    excel_reporter.append_to_report(fail_row, "timeline_slide_stress.xlsx")

        logger.info("滑动压测结束")
        return True

    def adb_swipe_right(self, y_coordinate=None, min_distance=150, max_distance=450):
        """
        ADB 向右滑动（基于时间轴中心 Y）
        """
        if y_coordinate is None:
            y_coordinate = self.get_timeline_center_y()

        size = self._adb_get_screen_size()
        w = size["width"]

        # 起点偏左，终点向右
        start_x = random.randint(int(w * 0.15), int(w * 0.35))
        distance = random.randint(min_distance, max_distance)
        end_x = min(start_x + distance, w - 40)
        duration = random.randint(350, 700)

        adb = self._adb_base_args()
        cmd = adb + [
            "shell", "input", "swipe",
            str(start_x), str(y_coordinate),
            str(end_x), str(y_coordinate),
            str(duration)
        ]
        logger.info(f"ADB 右滑: {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise RuntimeError(f"ADB 右滑失败: {r.stderr or r.stdout}")

    def adb_swipe_left(self, y_coordinate=None, min_distance=150, max_distance=450):
        """
        ADB 向左滑动（基于时间轴中心 Y）
        """
        if y_coordinate is None:
            y_coordinate = self.get_timeline_center_y()

        size = self._adb_get_screen_size()
        w = size["width"]

        # 起点偏右，终点向左
        start_x = random.randint(int(w * 0.65), int(w * 0.85))
        distance = random.randint(min_distance, max_distance)
        end_x = max(start_x - distance, 40)
        duration = random.randint(350, 700)

        adb = self._adb_base_args()
        cmd = adb + [
            "shell", "input", "swipe",
            str(start_x), str(y_coordinate),
            str(end_x), str(y_coordinate),
            str(duration)
        ]
        logger.info(f"ADB 左滑: {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise RuntimeError(f"ADB 左滑失败: {r.stderr or r.stdout}")

    def get_event_time(self):
        """获取事件时间"""
        return self.get_text(self.EVENT_TIME)

    def get_record_time_period(self):
        """获取录像片段时段"""
        return self.get_text(self.RECORD_TIME_PERIOD)

    def trigger_video_event(self, x=X, y=Y):
        """触发视频事件"""
        try:
            logger.info(f"点击屏幕坐标({x},{y})，触发视频事件")
            self.tap_at_coordinates(x, y)
            logger.info("成功点击屏幕坐标，触发视频事件")
            return True
        except Exception as e:
            logger.error(f"点击屏幕坐标({x},{y})，触发视频事件失败: {str(e)}")
            return False

    # 点击下载视频
    def click_download_video(self, retry_times=3):
        """
        下载视频
        1. 首先判断下载按钮是否出现，如果出现则直接点击
        2. 如果按钮不存在，则调用trigger_video_event触发点击屏幕
        3. 循环判断下载视频按钮是否可见，默认重试3次

        Args:
            retry_times (int): 重试次数，默认3次
        """
        try:
            logger.info(f"开始下载视频操作，最多重试{retry_times}次")
            for attempt in range(1, retry_times + 1):
                logger.info(f"第{attempt}次尝试下载视频")
                try:
                    # 判断下载视频按钮是否出现
                    if self.is_element_present(self.DOWNLOAD_VIDEO_BUTTON, timeout=2):
                        logger.info("检测到下载按钮，点击下载视频")
                        with allure.step(f"执行时间：{self.get_current_time()} ---- 点击下载视频"):
                            self.click(self.DOWNLOAD_VIDEO_BUTTON)
                            logger.info("成功点击下载视频按钮")
                        return True
                    else:
                        logger.info("未检测到下载按钮，触发点击屏幕")
                        # 点击屏幕
                        self.trigger_video_event()
                        with allure.step(f"执行时间：{self.get_current_time()} ---- 点击下载视频"):
                            self.click(self.DOWNLOAD_VIDEO_BUTTON)
                            logger.info("成功点击下载视频按钮")
                        return True

                except Exception as e:
                    logger.error(f"第{attempt}次尝试下载视频失败: {str(e)}")

                # 如果不是最后一次尝试，等待一段时间再重试
                if attempt < retry_times:
                    wait_time = random.randint(1, 2)
                    logger.info(f"等待{wait_time}秒后进行下一次尝试")
                    time.sleep(wait_time)
            logger.warning(f"尝试{retry_times}次后仍未成功下载视频")
            raise
        except Exception as e:
            error_msg = f"点击下载视频操作失败: {str(e)}"
            logger.error(error_msg)
            self._handle_error(error_msg, f"点击下载视频失败_{self.get_current_time()}")
            raise
    # 检查视频下载时间节点是否正确
    def check_video_download_time(self,actual_time):
        """
        检查视频下载时间节点是否正确
        """
        try:
            # 获取视频下载时间节点
            record_time_period = self.get_record_time_period()

            # 解析录像片段时段范围
            import re
            time_pattern = r"(\d{2}:\d{2}:\d{2})-(\d{2}:\d{2}:\d{2})"
            match = re.search(time_pattern, record_time_period)

            if not match:
                logger.error(f"无法解析录像片段时段范围: {record_time_period}")
                raise ValueError("无法解析录像片段时段范围")

            start_time_str = match.group(1)
            end_time_str = match.group(2)


            if actual_time != start_time_str:
                error_msg = f"录像片段时间不正确：事件时间={actual_time}，开始时间={start_time_str}"
                logger.error(error_msg)
                self._handle_error(error_msg, f"事件时间于录像片段开始时间不匹配_{self.get_current_time()}")
                allure.dynamic.title("下载录像片段时间不正确，执行失败")
                pytest.fail("下载录像片段段时间不正确")
                return False

            from datetime import datetime, timedelta
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M:%S")
                end_time = datetime.strptime(end_time_str, "%H:%M:%S")
                expected_end_time = start_time + timedelta(minutes=2)

                if end_time != expected_end_time:
                    error_msg = f"录像片段时间不正确：期望时间={record_time_period}，实际时间={actual_time}"
                    logger.error(error_msg)
                    self._handle_error(error_msg, f"录像片段时段范围与实际时间不匹配_{self.get_current_time()}")
                    allure.dynamic.title("下载录像片段时间不正确，执行失败")
                    pytest.fail("下载录像片段时间不正确")
                    return False
            except ValueError as e:
                error_msg = f"时间格式解析错误: {e}"
                logger.error(error_msg)

            logger.info(f"录像片段时间节点验证成功：事件时间={start_time_str}，录像片段结束={start_time_str}-{end_time_str}")
            return True

        except Exception as e:
            error_msg = f"获取视频下载时间节点失败: {str(e)}"
            logger.error(error_msg)
            self._handle_error(error_msg, f"获取视频下载时间节点失败_{self.get_current_time()}")
            raise
    # 获取下载状态
    def get_download_status(self):
        """
        获取下载状态
        :return:
        """
        return self.get_text(self.DOWNLOAD_STATUS)
    # 监控下载状态
    def check_monitor_download_status(self, timeout=120, poll_interval=5):
        """
        监控下载状态
        """
        start_time = time.time()
        logger.info(f"开始监控下载状态，超时时间为{timeout}秒")

        while time.time() - start_time < timeout:
            result = self.get_download_status()
            if result ==  "视频已保存到手机相册":
                logger.info("视频下载完成")
                with allure.step(f"执行时间：{self.get_current_time()} ---- 视频已保存到手机相册"):
                    self._take_screenshot(f"视频下载完成_{self.get_current_time()}")
                # 点击完成
                with allure.step(f"执行时间：{self.get_current_time()} ---- 点击完成"):
                    self.click(self.DOWNLOAD_SUCCESS_CONFIRM)
                return True
            elif result == "下载失败，请重试":
                with allure.step(f"执行时间：{self.get_current_time()} ---- 下载失败，请重试"):
                    self._handle_error("下载失败", f"视频下载失败_{self.get_current_time()}")
                # 取消下载
                with allure.step(f"执行时间：{self.get_current_time()} ---- 取消下载"):
                    self.click(self.DOWNLOAD_FAIL_CANCEL)
                raise Exception("录像视频片段下载失败")
            else:
                logger.info(f"下载中，当前状态为：{result}")
                time.sleep(poll_interval)

        with allure.step(f"执行时间：{self.get_current_time()} ---- 超时未完成下载"):
            self._handle_error("下载超时", f"视频下载超时_{self.get_current_time()}")

        raise Exception("录像视频片段下载失败")

    # 播放异常检测 - 优化版（返回布尔值 + 错误文本）
    def check_play_exception(self):
        """
        播放异常检测
        返回: (is_normal: bool, error_msg: str)
        压测场景下只返回结果，不抛异常
        """
        error_elements = [self.error_tips, self.error_tips2]

        try:
            for error_locator in error_elements:
                try:
                    error_element = WebDriverWait(self.driver, 0.8).until(
                        EC.presence_of_element_located(error_locator)
                    )
                    error_text = (error_element.text or "").strip()
                    if error_text:
                        logger.error(f"检测到播放异常提示: {error_text}")
                        # 只截图，不 raise
                        self._take_screenshot(f"播放异常_{self.get_current_time()}")
                        return False, error_text
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"检查错误元素异常: {e}")
                    continue

            logger.info("录像播放正常")
            return True, "播放正常"

        except Exception as e:
            logger.error(f"播放异常检测过程出错: {e}")
            return False, f"检测异常: {str(e)}"

    # 获取当前播放时间
    def get_current_play_time(self):
        """
        获取当前播放时间
        :return:
        """
        # 定位 ID 为 tv_video_time 的元素
        video_time_element = self.driver.find_element(AppiumBy.ID, "com.xm.support.android:id/tv_video_time")

        # 获取其当前的动态 text 值
        current_time_value = video_time_element.get_attribute("text")
        time.sleep(2)
        return current_time_value


