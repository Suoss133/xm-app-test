import os
import time
from datetime import datetime
from io import BytesIO

import allure
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from PIL import Image, ImageChops, ImageStat
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from apps.Koocam.pages.page_event import EventPage
from apps.Koocam.pages.page_home import HomePage
from core.base_test_suite import BaseTestSuite
from core.driver import DriverManager
from utils.logger import logger
from utils.excel_reporter import excel_reporter


@pytest.mark.flaky(reruns=2, reruns_delay=5,
                   reason="用例失败后等待5秒重试，最多重试2次")
class Test_9811_event_video_play(BaseTestSuite):

    # ==================== 事件详情页定位器（从 xml2.txt 提取） ====================
    # 主列表容器
    RECYCLER_VIEW = (AppiumBy.ID, "com.xm.support.android:id/recycler_view")
    # 列表项容器
    ITEM_ROOT = (AppiumBy.XPATH, '//android.widget.FrameLayout[@resource-id="com.xm.support.android:id/layout_root"]')
    # 播放图标（用于判断是否为视频项）
    PLAY_ICON = (AppiumBy.ID, "com.xm.support.android:id/iv_play_state")
    # 事件时间（列表项上的时间，如 "10:47"）
    VIDEO_TIME = (AppiumBy.ID, "com.xm.support.android:id/tv_time")
    # 视频时长（如 "00:11"）
    VIDEO_DURATION = (AppiumBy.ID, "com.xm.support.android:id/tv_video_time")
    # 缩略图（点击进入播放）
    THUMBNAIL = (AppiumBy.ID, "com.xm.support.android:id/niceiamge_thumbnail")

    # ===== 播放控制区域（播放时显示在 layout_function_bottom 下）=====
    # 播放控制底部区域
    LAYOUT_FUNCTION_BOTTOM = (AppiumBy.ID, "com.xm.support.android:id/layout_function_bottom")
    # 当前播放时间（格式 "00:20"；本用例不再用其差分判定成功）
    TV_TIME_VIDEO_PLAY = (AppiumBy.ID, "com.xm.support.android:id/tv_time_video_play")
    # 视频总时长（格式 "00:20"）
    TV_TIME_VIDEO_ALL = (AppiumBy.ID, "com.xm.support.android:id/tv_time_video_all")
    # 播放/暂停按钮
    IV_PLAY = (AppiumBy.ID, "com.xm.support.android:id/iv_play")
    # 加载动画容器
    LAYOUT_LOADING = (AppiumBy.ID, "com.xm.support.android:id/layout_loading")
    # 进度条截图区域（硬编码 bounds，基于 xml 分辨率 720x1552）
    SEEKBAR_BOX = (0, 201, 720, 606)
    # 两次截图平均像素差阈值（0~255）
    PLAY_CHECK_IMAGE_DIFF_THRESHOLD = 5.0

    # 加载消失后，等待若干秒再截屏与错误参考图比对（默认 10s，可通过套件参数 post_loading_screenshot_wait 覆盖）
    DEFAULT_POST_LOADING_SCREENSHOT_WAIT = 5
    # 当前屏与「错误截图」全屏缩略比对：平均像素差 ≤ 该值则视为与错误界面相似（0~255，可按设备微调）
    DEFAULT_ERROR_SCREEN_SIMILARITY_MAX_DIFF = 14.0
    # 错误参考图：与本测试文件同目录，文件名 错误截图.png
    _ERROR_REF_BASENAME = "错误截图.png"

    # 错误提示弹层（检测 tv_tips 可见即判失败）
    ERROR_TOAST = (AppiumBy.ID, "com.xm.support.android:id/tv_tips")

    @pytest.fixture(autouse=True)
    def setup_class(self, keep_app_state):
        self.initialize_suite("9811_event_video_play")
        self.driver = keep_app_state

        self.device_name = self.get_parameter("device_name")
        self.home_page = HomePage()
        self.event_page = EventPage()

        self.post_loading_screenshot_wait = 5
        self.error_screen_similarity_max_diff = 14.0

        # 显式等待
        self.wait = WebDriverWait(self.driver, timeout=10)

    @pytest.fixture(autouse=True)
    def recovery(self, keep_app_state):
        """
        pytest 层面的恢复机制：
        - 每次用例执行前（包含 rerun 重试）检查 App 是否存活
        - 若 App 崩溃/驱动断连，DriverManager 自动重连重启
        - 重启后重新初始化页面对象并导航到事件页，确保用例从正确状态继续
        """
        try:
            DriverManager.heartbeat()
        except Exception:
            logger.warning("检测到驱动失效，正在重连...")
            DriverManager.restart_start_driver()
            time.sleep(3)
            self.home_page = HomePage()
            self.home_page.click_event_button(self.device_name)
            time.sleep(3)

        yield

        # teardown：异常截图归到 Allure 报告
        try:
            self._take_screenshot(f"teardown_{self._get_current_time()}")
        except Exception:
            pass

    def _take_screenshot(self, name):
        """使用 ADB 截图并附加到 Allure 报告"""
        import subprocess
        try:
            from io import BytesIO
            from datetime import datetime

            # 策略1：使用 adb exec-out 直接获取截图数据
            result = subprocess.run(
                ["adb", "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and len(result.stdout) > 0:
                allure.attach(result.stdout, name=name, attachment_type=allure.attachment_type.PNG)
                logger.info(f"截图已保存并附加到 Allure: {name}")
                return

            # 策略2：使用 adb shell screencap + pull
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            remote_path = f"/data/local/tmp/_screenshot_{timestamp}.png"
            local_path = f"./screenshots/_screenshot_{timestamp}.png"

            import os
            os.makedirs("./screenshots", exist_ok=True)

            cap_r = subprocess.run(
                ["adb", "shell", "screencap", "-p", remote_path],
                timeout=5,
                check=False,
            )
            if cap_r.returncode == 0:
                pull_r = subprocess.run(
                    ["adb", "pull", remote_path, local_path],
                    timeout=5,
                    check=False,
                )
                if pull_r.returncode == 0 and os.path.exists(local_path):
                    with open(local_path, "rb") as f:
                        allure.attach(f.read(), name=name, attachment_type=allure.attachment_type.PNG)
                    subprocess.run(["adb", "shell", "rm", remote_path], timeout=3, check=False)
                    try:
                        os.remove(local_path)
                    except:
                        pass
                    logger.info(f"截图已保存并附加到 Allure: {name}")
                    return

            # 策略3：兜底使用 Appium driver
            png = self.driver.get_screenshot_as_png()
            allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
            logger.info(f"截图已保存并附加到 Allure(Appium fallback): {name}")

        except Exception as e:
            logger.warning(f"截图失败: {str(e)}")

    def _get_current_time(self):
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _parse_duration(self, duration_text: str) -> int:
        """解析视频时长字符串，返回秒数"""
        try:
            if not duration_text:
                return 0
            parts = duration_text.strip().split(":")
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            return 0
        except Exception:
            return 0

    def _wait_for_recycler_loaded(self, timeout=10):
        """等待列表加载"""
        try:
            self.wait.until(EC.visibility_of_element_located(self.RECYCLER_VIEW))
            time.sleep(0.5)  # 等待列表渲染
            return True
        except Exception as e:
            logger.error(f"等待列表加载失败: {str(e)}")
            return False

    def _get_video_items(self):
        """获取所有视频列表项（过滤空项）"""
        items = []
        try:
            all_items = self.driver.find_elements(*self.ITEM_ROOT)
            for item in all_items:
                try:
                    # 检查是否有播放图标（有播放图标的是视频项）
                    play_icon = item.find_element(*self.PLAY_ICON)
                    if play_icon and play_icon.is_displayed():
                        # 检查 bounds 是否有效（排除空项）
                        bounds = play_icon.get_attribute("bounds")
                        if bounds and bounds != "[0,0][0,0]":
                            items.append(item)
                except Exception:
                    continue
            logger.info(f"找到 {len(items)} 个视频项")
        except Exception as e:
            logger.error(f"获取视频项失败: {str(e)}")
        return items

    def _is_video_item(self, item_element) -> bool:
        """判断是否为视频项"""
        try:
            play_icon = item_element.find_element(*self.PLAY_ICON)
            return play_icon.is_displayed()
        except Exception:
            return False

    def _get_item_event_time(self, item_element) -> str:
        """获取列表项的事件时间"""
        try:
            return item_element.find_element(*self.VIDEO_TIME).get_attribute("text").strip()
        except Exception:
            return None

    def _get_item_duration(self, item_element) -> int:
        """获取视频时长（秒）"""
        try:
            duration_text = item_element.find_element(*self.VIDEO_DURATION).get_attribute("text").strip()
            return self._parse_duration(duration_text)
        except Exception:
            return 0

    def _is_loading_visible(self) -> bool:
        """检查加载动画是否可见"""
        try:
            loading = self.driver.find_element(*self.LAYOUT_LOADING)
            return loading.is_displayed()
        except Exception:
            return False

    def _is_play_controls_visible(self) -> bool:
        """检查播放控制区域是否可见"""
        try:
            controls = self.driver.find_element(*self.LAYOUT_FUNCTION_BOTTOM)
            return controls.is_displayed()
        except Exception:
            return False

    def _wait_for_loading_disappear(self, timeout=10) -> bool:
        """等待加载动画消失"""
        try:
            start = time.time()
            while time.time() - start < timeout:
                if not self._is_loading_visible():
                    logger.info("[加载] 加载动画已消失")
                    return True
            return False
        except Exception:
            return True

    def _click_play_button(self) -> bool:
        """
        点击播放按钮
        """
        try:
            play_btn = self.driver.find_element(*self.IV_PLAY)
            play_btn.click()
            logger.info("已点击播放按钮")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"点击播放按钮失败: {str(e)}")
            return False

    def _wait_for_play_controls_visible(self, timeout=10) -> bool:
        """等待播放控制区域可见（说明已进入播放状态）"""
        try:
            start = time.time()
            while time.time() - start < timeout:
                if self._is_play_controls_visible():
                    return True
                time.sleep(0.3)
            return False
        except Exception:
            return False

    def _capture_seekbar_region(self, event_time: str = None) -> Image.Image:
        """
        对硬编码的进度条区域 bounds 进行全屏截图并裁剪。
        截图保存到项目下的 temp 文件夹，用于调试验证。
        文件名格式: seekbar_{事件时间}_{系统时间戳}.png
        """
        import os
        temp_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        temp_dir = os.path.join(temp_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if event_time:
            # 清理事件时间中的特殊字符
            safe_event_time = event_time.replace(":", "-").replace(" ", "_")
            save_name = f"seekbar_{safe_event_time}_{timestamp}.png"
        else:
            save_name = f"seekbar_{timestamp}.png"
        save_path = os.path.join(temp_dir, save_name)

        try:
            full_png = self.driver.get_screenshot_as_png()
            full_img = Image.open(BytesIO(full_png)).convert("RGB")
            logger.info(f"[截图] 全屏尺寸: {full_img.size}, bounds: {self.SEEKBAR_BOX}")

            cropped = full_img.crop(self.SEEKBAR_BOX)
            cropped.save(save_path)
            logger.info(f"[截图] 已保存: {save_path}")
            return cropped

        except Exception as e:
            logger.warning(f"[截图] 进度条区域截图失败: {e}")
            return Image.new("RGB", (443, 51), (0, 0, 0))

    def _compute_image_diff(self, img1: Image.Image, img2: Image.Image) -> float:
        """比较两张图像的平均像素差异（0~255）。"""
        diff = ImageChops.difference(img1, img2)
        stat = ImageStat.Stat(diff)
        return sum(stat.mean) / len(stat.mean)

    def _is_video_playing_by_screenshot(self, check_seconds: int = 3, event_time: str = None) -> tuple:
        """
        通过截图区域的时间戳变化和像素差异判断视频是否在播放。

        检测策略：
        1. 右上角时间戳变化检测（主要）：提取截图右上角时间戳区域（HH:MM:SS 格式），
           若时间戳区域像素差异明显（时间数字变化），判定为播放中
        2. 全区域像素差异检测（辅助）：若时间戳检测不通过，再用全区域差异判断

        参数:
            check_seconds: 两次截图间隔时间
            event_time: 事件时间，用于截图文件名

        返回 (is_playing: bool, message: str)
        """
        img1 = self._capture_seekbar_region(event_time)
        logger.info(f"[图像检测] 第1次截图: {img1.size}")

        time.sleep(check_seconds)

        img2 = self._capture_seekbar_region(event_time)
        logger.info(f"[图像检测] 第2次截图: {img2.size} (等待 {check_seconds}s)")

        # 策略1：检测右上角时间戳区域变化
        w, h = img1.size
        # 时间戳在右上角，大约在宽度 60%-100%，高度 0%-15% 区域
        ts_left = int(w * 0.6)
        ts_top = 0
        ts_right = w
        ts_bottom = int(h * 0.15)

        ts_img1 = img1.crop((ts_left, ts_top, ts_right, ts_bottom))
        ts_img2 = img2.crop((ts_left, ts_top, ts_right, ts_bottom))
        ts_diff = self._compute_image_diff(ts_img1, ts_img2)
        logger.info(f"[时间戳检测] 时间戳区域差异: {ts_diff:.2f}")

        # 时间戳区域差异阈值（数字变化通常差异较大，设15）
        TS_DIFF_THRESHOLD = 15.0

        if ts_diff >= TS_DIFF_THRESHOLD:
            logger.info(f"[时间戳检测] 时间戳变化，判定视频正在播放 (差异 {ts_diff:.2f} >= 阈值 {TS_DIFF_THRESHOLD})")
            return True, f"播放成功 - 时间戳变化 (ts_diff={ts_diff:.2f})"

        # 策略2：全区域像素差异检测（备用）
        diff = self._compute_image_diff(img1, img2)
        logger.info(f"[图像检测] 全区域像素差异: {diff:.2f}")

        if diff >= self.PLAY_CHECK_IMAGE_DIFF_THRESHOLD:
            logger.info(f"[图像检测] 全区域变化，判定视频正在播放 (差异 {diff:.2f} >= 阈值 {self.PLAY_CHECK_IMAGE_DIFF_THRESHOLD})")
            return True, f"播放成功 - 全区域变化 (diff={diff:.2f})"

        logger.warning(f"[图像检测] 视频未播放或已暂停 (ts_diff={ts_diff:.2f}, 全diff={diff:.2f})")
        return False, f"播放失败 (ts_diff={ts_diff:.2f}, 全diff={diff:.2f})"

    def _get_error_reference_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self._ERROR_REF_BASENAME)

    def _is_error_toast_visible(self) -> bool:
        """检测 tv_tips 错误提示弹层是否可见，可见即判定播放失败。"""
        try:
            el = self.driver.find_element(*self.ERROR_TOAST)
            if el.is_displayed():
                text = el.text.strip()
                logger.warning(f"[错误弹层] tv_tips 可见，文案: {text!r}")
                return True
            return False
        except Exception:
            return False

    def _is_similar_to_error_reference_screen(self) -> tuple:
        """
        全屏截图与「错误截图.png」缩放到同一尺寸后做平均像素差比对。
        差异 ≤ error_screen_similarity_max_diff 则视为与错误界面相似。
        返回 (is_error_like, detail)
        """
        ref_path = self._get_error_reference_path()
        if not os.path.isfile(ref_path):
            logger.warning(f"[错误界面] 未找到参考图: {ref_path}，跳过图像相似度判定")
            return False, "参考图未配置"

        try:
            ref = Image.open(ref_path).convert("RGB")
            png = self.driver.get_screenshot_as_png()
            cur = Image.open(BytesIO(png)).convert("RGB")
            target_size = ref.size
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            cur_sized = cur.resize(target_size, resample)
            diff = self._compute_image_diff(cur_sized, ref)
            logger.info(
                f"[错误界面] 与参考图平均像素差: {diff:.2f} "
                f"(相似阈值≤{self.error_screen_similarity_max_diff})"
            )
            if diff <= self.error_screen_similarity_max_diff:
                return True, f"与错误参考图相似(diff={diff:.2f})"
            return False, f"与错误参考图不相似(diff={diff:.2f})"
        except Exception as e:
            logger.warning(f"[错误界面] 比对异常: {e}")
            return False, str(e)

    def _check_video_playing(
        self,
        loading_timeout_seconds: int,
        post_load_wait_seconds: float = None,
        event_time: str = None,
    ) -> tuple:
        """
        检查视频是否播放成功。

        流程：
        1. 等待 LAYOUT_LOADING 消失，超时时间 = loading_timeout_seconds（与列表项 VIDEO_DURATION 一致，秒）
           若超时仍未消失 → 判定播放失败（加载超时已达视频时长）。
        2. 加载消失后等待 post_load_wait_seconds（默认取套件参数 post_loading_screenshot_wait，默认 10s）。
        3. 检测 tv_tips 错误弹层（ERROR_TOAST）是否可见；可见则判定播放失败。
        4. 与 tests/event/错误截图.png 做全屏相似度比对，相似则判定播放失败。
        5. 无上述任何失败条件 → 判定播放成功。

        参数:
            loading_timeout_seconds: 与列表项视频时长一致的加载等待上限（秒）
            post_load_wait_seconds: 加载消失后再等待多久截屏比对错误图；None 则用 self.post_loading_screenshot_wait
            event_time: 事件时间，用于截图文件名

        返回 (is_playing, message)
        """
        if post_load_wait_seconds is None:
            post_load_wait_seconds = self.post_loading_screenshot_wait

        try:
            if not self._wait_for_loading_disappear(timeout=float(loading_timeout_seconds)):
                return (
                    False,
                    f"播放失败：加载超时（{loading_timeout_seconds}s 内 LAYOUT_LOADING 未消失，与列表视频时长一致）",
                )

            logger.info(f"[播放检测] 加载已消失，等待 {post_load_wait_seconds}s 后做错误弹层与界面比对")
            time.sleep(post_load_wait_seconds)

            if self._is_error_toast_visible():
                return False, "播放失败：tv_tips 错误弹层可见"

            # err_like, err_detail = self._is_similar_to_error_reference_screen()
            # if err_like:
            #     return False, f"播放失败：{err_detail}"

            logger.info("[播放检测] 无错误弹层且界面与错误参考图不相似，判定播放成功")
            return True, "播放成功"

        except Exception as e:
            return False, f"检测异常: {str(e)}"

    def _play_single_video(self, item_element, item_event_time: str) -> tuple:
        """
        播放单个视频
        返回 (success, message)
        """
        try:
            # 2. 获取视频时长
            duration_sec = self._get_item_duration(item_element)
            # 2. 点击缩略图进入播放
            thumbnail = item_element.find_element(*self.THUMBNAIL)
            thumbnail.click()
            logger.info(f"点击缩略图进入播放: {item_event_time}")

            # 2. 加载超时与列表 VIDEO_DURATION 一致；加载消失后默认再等 1s（可配置）截屏比对错误图 + 进度条区域检测

            loading_timeout = duration_sec if duration_sec > 0 else 60
            if duration_sec <= 0:
                logger.warning(f"[播放] 列表项未解析到视频时长，加载等待使用默认 {loading_timeout}s")

            is_playing, msg = self._check_video_playing(
                loading_timeout_seconds=loading_timeout,
                post_load_wait_seconds=1,
                event_time=item_event_time,
            )

            return is_playing, msg

        except Exception as e:
            return False, f"播放异常: {str(e)}"

    def _get_recycler_signature(self, max_items=5) -> tuple:
        """获取列表签名，用于判断滚动是否加载新内容"""
        try:
            items = self._get_video_items()
            times = []
            for item in items[:max_items]:
                try:
                    t = item.find_element(*self.VIDEO_TIME).get_attribute("text").strip()
                    if t:
                        times.append(t)
                except Exception:
                    pass
            return tuple(times) if times else ("empty",)
        except Exception:
            return ("error",)

    def _has_unprocessed_in_view(self, processed_times: set) -> bool:
        """判断当前可见区域是否还有未处理的视频"""
        try:
            items = self._get_video_items()
            for item in items:
                event_time = self._get_item_event_time(item)
                if event_time and event_time not in processed_times:
                    return True
            return False
        except Exception:
            return True

    @pytest.mark.parametrize("loop_times", [1])
    def test_cycle_play_all_videos(self, loop_times):
        """循环播放所有录像视频压测"""

        self.home_page.click_event_button(self.device_name)
        self.event_page.click_event_play_list_details()

        processed_event_times = set()
        max_loops = 1

        for loop in range(1, max_loops + 1):
            with allure.step(f"第 {loop} 轮 - 从顶部逐条播放所有视频"):
                logger.info(f"第 {loop} 轮，从顶部开始播放...")
                MAX_SCROLL_ROUNDS = 1000
                TARGET_STAGNANT = 3
                stagnant_bottom_times = 0
                scroll_round = 0

                while scroll_round < MAX_SCROLL_ROUNDS:
                    scroll_round += 1

                    self._wait_for_recycler_loaded(timeout=10)
                    items = self._get_video_items()

                    logger.info(
                        f"[loop {loop} / scroll {scroll_round}] 可见 {len(items)} 条，已处理 {len(processed_event_times)} 条"
                    )

                    idx = 0
                    while idx < len(items):
                        item = items[idx]
                        idx += 1

                        if not self._is_video_item(item):
                            continue

                        item_event_time = self._get_item_event_time(item)
                        if not item_event_time or item_event_time in processed_event_times:
                            continue

                        # 过滤短视频（<5秒）
                        duration = self._get_item_duration(item)
                        if duration < 5:
                            logger.info(f"跳过短视频 (时长 {duration}s, 事件时间: {item_event_time})")
                            continue

                        with allure.step(f"播放视频（事件时间 {item_event_time}）"):
                            # 播放视频
                            success, msg = self._play_single_video(item, item_event_time)

                            # 记录结果
                            excel_reporter.append_to_report([{
                                "次数": f"loop{loop}_scroll{scroll_round}",
                                "事件时间": item_event_time,
                                "结果": "PASS" if success else "FAIL",
                                "备注": msg,
                            }], "事件播放结果.xlsx")

                            logger.info(
                                f"事件时间: {item_event_time} | 结果: {'PASS' if success else 'FAIL'} | {msg}"
                            )

                            processed_event_times.add(item_event_time)


                        # 刷新列表引用
                        items = self._get_video_items()
                        idx = 0

                    # 滚动加载更多
                    before_sig = self._get_recycler_signature()
                    before_has_unprocessed = self._has_unprocessed_in_view(processed_event_times)

                    logger.info("向下滑动加载更多...")
                    self.event_page.scroll_down(distance_ratio=0.15)

                    after_sig = self._get_recycler_signature()
                    after_has_unprocessed = self._has_unprocessed_in_view(processed_event_times)

                    if after_sig == before_sig and not after_has_unprocessed:
                        stagnant_bottom_times += 1
                        logger.info(f"疑似到达底部: {stagnant_bottom_times}/{TARGET_STAGNANT}")
                    else:
                        stagnant_bottom_times = 0

                    if stagnant_bottom_times >= TARGET_STAGNANT:
                        logger.info(f"检测到列表底部，已处理 {len(processed_event_times)} 条")
                        break

                logger.info(f"第 {loop} 轮播放完成，共处理 {len(processed_event_times)} 条事件")
