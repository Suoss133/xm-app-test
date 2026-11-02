import os
import re
import time
import subprocess
import numpy as np
from datetime import datetime
from io import BytesIO

import allure
from appium.webdriver.common.appiumby import AppiumBy
from PIL import Image, ImageStat
from selenium.webdriver.support.wait import WebDriverWait

from apps.base.base_event_page import BaseEventDevicePage
from utils.logger import logger
from selenium.webdriver.support import expected_conditions as EC
from utils.excel_reporter import excel_reporter


class EventPage(BaseEventDevicePage):

    def __init__(self):
        super().__init__(
            page_name="事件页",
            config_path="apps/Koocam/config.yaml",
            page_config_name="event"
        )

        # 总列表控件
        self.recycler_view = (AppiumBy.ID, "com.xm.support.android:id/recycler_view")
        # 每条列表控件
        self.item_root = (AppiumBy.XPATH, '//android.widget.FrameLayout[@resource-id="com.xm.support.android:id/layout_root"]')
        # 视频播放
        self.play_icon = (AppiumBy.ID, "com.xm.support.android:id/iv_play_state")
        # 播放时间
        self.video_time = (AppiumBy.ID, "com.xm.support.android:id/tv_time")
        # 视频时长（用于过滤少于10秒的事件）
        self.video_duration = (AppiumBy.ID, "com.xm.support.android:id/tv_video_time")
        # 时间轴区域：用于获取"当前正在播放"的时间（注意：与列表项 tv_time 不同）
        self.timeline_date = (
            AppiumBy.XPATH,
            '//*[@resource-id="com.xm.support.android:id/layout_timeline_time"]//*[@resource-id="com.xm.support.android:id/tv_video_date"]',
        )
        self.timeline_time = (
            AppiumBy.XPATH,
            '//*[@resource-id="com.xm.support.android:id/layout_timeline_time"]//*[@resource-id="com.xm.support.android:id/tv_video_time"]',
        )
        # 云录/卡录顶部大画面区域（与 xml.txt 中 bounds 一致，用于 Pillow 采样）
        self.live_root_zoom = (
            AppiumBy.XPATH,
            '//android.widget.FrameLayout[@resource-id="com.xm.support.android:id/layout_live_root_zoom1"]',
        )
        # 视频预览区域：点击后才会弹出播放按钮（texture_view 是播放层，初始可见）
        self.video_preview_area = (
            AppiumBy.ID,
            "com.xm.support.android:id/texture_view1",
        )
        # 播放按钮：在 layout_live_root_zoom1 内，点击预览区域后才显示（对应 xml2.txt 状态）
        self.play_button_on_video = (
            AppiumBy.XPATH,
            '//android.widget.FrameLayout[@resource-id="com.xm.support.android:id/layout_live_root_zoom1"]'
            '//android.widget.RelativeLayout[@resource-id="com.xm.support.android:id/layout_function_root"]'
            '//android.widget.LinearLayout[@resource-id="com.xm.support.android:id/layout_play_state"]'
            '//android.widget.ImageView[@resource-id="com.xm.support.android:id/iv_play_state"]',
        )

        # 加载动画区域（视频预览区中央，用于亮度检测）
        self._loading_region = {
            "left_ratio": 0.35, "right_ratio": 0.65,   # 屏幕宽度 35%~65%
            "top_ratio": 0.15, "bottom_ratio": 0.50,   # 屏幕高度 15%~50%
        }

        # 与 wait_for_loading_by_brightness 同区域，用于判断是否真的在播画面（排除「正在连接…」类灰底）
        self._PLAY_FAIL_DARK_PLAIN_RATIO = 0.55   # 像素亮度落在 ~#333 邻域的占比
        self._PLAY_FAIL_LUMA_STD_MAX = 28.0       # 低于则认为缺乏画面纹理
        self._PLAY_FAIL_LUMA_MEAN_MAX = 102.0     # 同时均值仍偏低 → 占位/连接中
        self._PLAY_FAIL_ABSOLUTE_LUMA_MEAN = 50.0
        self._PLAY_FAIL_ABSOLUTE_LUMA_STD = 12.0

        # temp 目录用于保存检测截图
        self._temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(self._temp_dir, exist_ok=True)

    def _save_adb_screenshot_to_temp(self, prefix="loading_done"):
        """
        使用 ADB 截图并保存到 temp 目录

        Args:
            prefix (str): 文件名前缀，默认 "loading_done"

        Returns:
            str: 保存的文件路径，失败返回 None
        """
        try:
            # 生成文件名（避免使用 %f，可能被 ADB 误解析）
            now = datetime.now()
            filename = f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}.png"
            filepath = os.path.join(self._temp_dir, filename)

            # 使用 adb shell screencap 保存到手机临时目录
            subprocess.run(
                ["adb", "shell", "screencap", "-p", f"/data/local/tmp/{filename}"],
                timeout=5,
                check=False
            )

            # 拉取到本地
            pull_result = subprocess.run(
                ["adb", "pull", f"/data/local/tmp/{filename}", filepath],
                timeout=5,
                check=False
            )

            if pull_result.returncode == 0 and os.path.exists(filepath):
                logger.info(f"[ADB截图] 已保存: {filepath}")
            else:
                logger.warning(f"[ADB截图] 拉取失败: {pull_result.stderr or '未知错误'}")

            # 清理手机端临时文件
            subprocess.run(
                ["adb", "shell", "rm", f"/data/local/tmp/{filename}"],
                timeout=3,
                check=False
            )

            return filepath if os.path.exists(filepath) else None

        except Exception as e:
            logger.warning(f"[ADB截图] 截图异常: {str(e)}")
            return None

    def _capture_screenshot_as_pil(self) -> Image.Image:
        """
        通过 ADB exec-out screencap 获取实时屏幕截图，返回 Pillow Image 对象。
        相比 Appium get_screenshot_as_png() 更实时、更稳定，不会因 UiAutomator2 崩溃而失败。

        兜底策略：
        1. ADB exec-out screencap -p（优先，高实时性）
        2. ADB shell screencap -p + pull（备选）
        3. Appium driver.get_screenshot_as_png()（最后兜底）

        Returns:
            PIL.Image: RGB 格式全屏截图
        """
        # 策略1：exec-out 直传（最实时）
        try:
            result = subprocess.run(
                ["adb", "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and len(result.stdout) > 0:
                img = Image.open(BytesIO(result.stdout)).convert("RGB")
                return img
        except Exception as e1:
            logger.debug(f"[截图] ADB exec-out 失败，尝试策略2: {e1}")

        # 策略2：shell screencap + pull
        tmp_file = None
        try:
            now = datetime.now()
            tmp_file = f"/data/local/tmp/_capture_{now.strftime('%Y%m%d_%H%M%S_%f')}.png"
            cap_r = subprocess.run(
                ["adb", "shell", "screencap", "-p", tmp_file],
                timeout=5,
                check=False,
            )
            if cap_r.returncode == 0:
                pull_r = subprocess.run(
                    ["adb", "pull", tmp_file, "/dev/stdout"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if pull_r.returncode == 0 and len(pull_r.stdout) > 0:
                    img = Image.open(BytesIO(pull_r.stdout)).convert("RGB")
                    subprocess.run(["adb", "shell", "rm", tmp_file], timeout=3, check=False)
                    return img
        except Exception as e2:
            logger.debug(f"[截图] ADB shell+pull 失败: {e2}")
        finally:
            if tmp_file:
                subprocess.run(["adb", "shell", "rm", tmp_file], timeout=3, check=False)

        # 策略3：Appium 最后兜底
        try:
            png_bytes = self.driver.get_screenshot_as_png()
            return Image.open(BytesIO(png_bytes)).convert("RGB")
        except Exception as e3:
            logger.error(f"[截图] 所有截图方式均失败: {e3}")
            raise RuntimeError(f"截图获取失败（已尝试 ADB exec-out / shell+pull / Appium）: {e3}")

    def _is_uiautomator2_crashed(self, exc: Exception) -> bool:
        """
        根据异常信息判断是否为 UiAutomator2 服务崩溃。

        崩溃特征（两种模式均支持）：
        - "cannot be proxied to UiAutomator2 server because the instrumentation process is not running"
        - "instrumentation process is not running (probably crashed)"
        """
        msg = str(exc)
        return (
            "UiAutomator2" in msg
            and "cannot be proxied" in msg
            and "instrumentation process is not running" in msg
        ) or (
            "instrumentation process is not running (probably crashed)" in msg
        )

    def _recover_uiautomator2(self) -> bool:
        """
        尝试自动恢复 UiAutomator2 服务。

        恢复策略（由轻到重）：
        1. activate_app — 仅激活前台，最轻量
        2. terminate_app + activate_app — 强制重启 App
        3. raise — 恢复失败，抛给上层处理

        Returns:
            bool: 恢复成功返回 True
        """
        logger.warning("[UIA2恢复] 检测到 UiAutomator2 服务崩溃，开始恢复...")

        # 获取当前 App 包名
        current_pkg = None
        try:
            current_pkg = self.driver.current_package
        except Exception:
            pass

        if not current_pkg:
            logger.error("[UIA2恢复] 无法获取当前 App 包名，恢复失败")
            raise RuntimeError("UiAutomator2 崩溃且无法获取包名，无法自动恢复")

        # 策略1：仅激活 App
        try:
            self.driver.activate_app(current_pkg)
            logger.info(f"[UIA2恢复] activate_app({current_pkg}) 成功")
            time.sleep(1.5)
            return True
        except Exception as e1:
            logger.warning(f"[UIA2恢复] activate_app 失败: {e1}")

        # 策略2：强制终止后重新激活
        try:
            self.driver.terminate_app(current_pkg)
            time.sleep(1.0)
            self.driver.activate_app(current_pkg)
            time.sleep(2.0)
            logger.info(f"[UIA2恢复] terminate_app + activate_app({current_pkg}) 成功")
            return True
        except Exception as e2:
            logger.warning(f"[UIA2恢复] terminate_app + activate_app 失败: {e2}")

        logger.error("[UIA2恢复] 两种策略均失败，无法自动恢复 UiAutomator2")
        raise RuntimeError(
            f"UiAutomator2 崩溃，自动恢复失败（已尝试 activate_app 和 terminate_app+activate_app）"
        )

    # ==================== 加载动画检测方法 ====================

    def _is_event_stream_loading_visible(self):
        """
        事件页大画面是否仍处于加载/连接中（与纯亮度互补，避免白底+白字误判）。
        覆盖 layout_loading、gif_view（yaml loading）及「正在连接」类文案。
        """
        for loc in (
            (AppiumBy.ID, "com.xm.support.android:id/layout_loading"),
            self.LOADING,
        ):
            try:
                el = self.driver.find_element(*loc)
                if el.is_displayed():
                    return True
            except Exception:
                pass
        try:
            xps = (
                '//*[contains(@text,"正在连接")]',
                '//*[contains(@text,"连接中")]',
                '//*[contains(@content-desc,"正在连接")]',
                '//*[contains(@content-desc,"连接中")]',
            )
            for xp in xps:
                for el in self.driver.find_elements(AppiumBy.XPATH, xp):
                    try:
                        if el.is_displayed():
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    @staticmethod
    def _likely_connecting_overlay_by_horizontal_edges(region_rgb: np.ndarray) -> bool:
        """
        在加载区下半部检测横向文字/条状 loading 引起的水平梯度增强（相对上半参考区）。
        用于 DOM 未暴露「正在连接」但画面叠字时的兜底；对白底白字不保证百分百，与 DOM 组合使用。
        """
        if region_rgb is None or region_rgb.size == 0 or region_rgb.ndim != 3:
            return False
        reg = region_rgb.astype(np.float64)
        h, w = reg.shape[:2]
        luma = 0.299 * reg[..., 0] + 0.587 * reg[..., 1] + 0.114 * reg[..., 2]
        c0, c1 = int(w * 0.1), int(w * 0.9)
        if c1 <= c0 + 4:
            return False

        def mean_hgrad(block):
            if block.size == 0 or block.shape[1] < 2:
                return 0.0
            return float(np.mean(np.abs(np.diff(block, axis=1))))

        r0, r1 = int(h * 0.50), min(h, int(h * 0.93))
        u0, u1 = int(h * 0.06), max(1, int(h * 0.40))
        band = luma[r0:r1, c0:c1]
        upper = luma[u0:u1, c0:c1]
        if band.size == 0 or upper.size == 0:
            return False
        g_band = mean_hgrad(band)
        g_up = max(mean_hgrad(upper), 1.0)
        return g_band > 10.0 and g_band > g_up * 1.28

    def wait_for_loading_by_brightness(self, timeout=30, check_interval=0.2,
                                       brightness_threshold=180, stable_count=3):
        """
        方法1：区域亮度 + DOM（layout_loading / gif_view / 正在连接）+ 条带梯度兜底

        原理：
        - 旧版仅看「区域/中心亮度 < 阈值」：在「正在连接…」叠在很亮的画面上时，
          半透明遮罩会把均值拉低，易误判为加载已结束。
        - 现要求：亮度条件满足 **且** 原生加载层与连接文案均不可见 **且** 图像条带未提示连接 overlay。

        Args:
            timeout (int): 最大等待时间（秒），默认 30
            check_interval (float): 检测间隔（秒），默认 0.2
            brightness_threshold (int): 亮度阈值 0-255，默认 180
            stable_count (int): 连续满足「可判定为已结束」的次数

        Returns:
            bool: 加载动画消失返回 True，超时返回 False
        """
        start_time = time.time()
        consecutive_ok = 0
        saved = False

        logger.info(f"[亮度检测] 开始检测加载动画，亮度阈值={brightness_threshold}，含 DOM/条带兜底")

        while time.time() - start_time < timeout:
            try:
                full_img = self._capture_screenshot_as_pil()
                img_array = np.array(full_img)

                h, w = img_array.shape[:2]

                left = int(w * self._loading_region["left_ratio"])
                right = int(w * self._loading_region["right_ratio"])
                top = int(h * self._loading_region["top_ratio"])
                bottom = int(h * self._loading_region["bottom_ratio"])

                region = img_array[top:bottom, left:right]

                avg_brightness = float(np.mean(region))
                center_h = region.shape[0] // 2
                center_w = region.shape[1] // 2
                center_region = region[
                    max(0, center_h - 20):center_h + 20,
                    max(0, center_w - 20):center_w + 20
                ]
                center_brightness = float(np.mean(center_region))

                elapsed = time.time() - start_time
                loading_ui = self._is_event_stream_loading_visible()
                edge_hint = self._likely_connecting_overlay_by_horizontal_edges(region)

                # ---- OCR 检测「正在连接」（EasyOCR 可用时）----
                ocr_still_connecting = False
                if not loading_ui and not edge_hint:
                    # 仅在 DOM/梯度均未发现时才走 OCR；否则已在等待
                    try:
                        self._easyocr_reader_lazy()  # 检查是否可用
                        ocr_region = full_img.crop((left, top, right, bottom))
                        raw = self._ocr_recognize_connecting_region_text(ocr_region)
                        ocr_still_connecting = self._ocr_text_is_still_loading(raw)
                    except Exception:
                        pass  # 未装 OCR，继续用亮度路径

                if loading_ui:
                    consecutive_ok = 0
                    logger.debug(
                        f"[亮度检测] 原生加载层/连接文案仍可见，继续等待… "
                        f"区域亮度={avg_brightness:.1f}, 中心={center_brightness:.1f}"
                    )
                elif edge_hint:
                    consecutive_ok = 0
                    logger.debug(
                        f"[亮度检测] 条带梯度疑似「正在连接」overlay，继续等待… "
                        f"区域亮度={avg_brightness:.1f}, 中心={center_brightness:.1f}"
                    )
                elif ocr_still_connecting:
                    consecutive_ok = 0
                    logger.debug(
                        f"[亮度检测] OCR 仍识别到「正在连接」，继续等待… "
                        f"区域亮度={avg_brightness:.1f}"
                    )
                elif avg_brightness < brightness_threshold and center_brightness < brightness_threshold:
                    consecutive_ok += 1
                    if consecutive_ok >= stable_count:
                        logger.info(
                            f"[亮度检测] 加载动画已消失（耗时 {elapsed:.1f}s，"
                            f"亮度={avg_brightness:.1f}，中心={center_brightness:.1f}）"
                        )
                        if not saved:
                            self._save_adb_screenshot_to_temp("brightness_loading_done")
                            saved = True
                        return True
                else:
                    consecutive_ok = 0
                    logger.debug(
                        f"[亮度检测] 等待中… 区域亮度={avg_brightness:.1f}, 中心亮度={center_brightness:.1f}"
                    )

                time.sleep(check_interval)

            except Exception as e:
                if self._is_uiautomator2_crashed(e):
                    try:
                        self._recover_uiautomator2()
                    except RuntimeError:
                        logger.error("[亮度检测] UiAutomator2 恢复失败，终止等待")
                        raise
                    elapsed = time.time() - start_time
                    logger.warning(f"[亮度检测] UiAutomator2 已恢复，继续等待（已用时 {elapsed:.1f}s）")
                    consecutive_ok = 0
                    time.sleep(1.0)
                    continue
                logger.warning(f"[亮度检测] 检测异常（不计为加载结束）: {str(e)[:120]}")
                consecutive_ok = 0
                time.sleep(check_interval)

        logger.warning(f"[亮度检测] 等待加载动画消失超时（{timeout}秒）")
        return False

    def _pil_crop_loading_region(self, full_image: Image.Image):
        """按 _loading_region 比例从整屏 PIL 图裁剪加载判定区域。"""
        w, h = full_image.size
        left = int(w * self._loading_region["left_ratio"])
        right = int(w * self._loading_region["right_ratio"])
        top = int(h * self._loading_region["top_ratio"])
        bottom = int(h * self._loading_region["bottom_ratio"])
        return full_image.crop((left, top, right, bottom))

    # ---- EasyOCR 单例（首次调用时才加载模型，避免启动慢）----
    _easyocr_reader = None

    @classmethod
    def _easyocr_reader_lazy(cls):
        """
        获取 EasyOCR Reader 单例，首次调用时初始化（中英文语言包）。
        懒加载：只在使用 OCR 相关功能时才加载模型。
        """
        if cls._easyocr_reader is None:
            try:
                import easyocr
                cls._easyocr_reader = easyocr.Reader(
                    ["ch_sim", "en"],
                    gpu=False,
                    verbose=False,
                )
                logger.info("[OCR] EasyOCR 模型加载完成（中英文）")
            except Exception as e:
                logger.error(f"[OCR] EasyOCR 初始化失败: {str(e)}")
                raise
        return cls._easyocr_reader

    def _ocr_recognize_connecting_region_text(self, region_pil: Image.Image) -> str:
        """
        对裁剪区域做 OCR，返回识别到的所有文本拼接字符串。
        依赖：pip install easyocr（首次调用自动下载模型，约 300MB）。
        兼容 EasyOCR v1.6（旧：tuple）和 v1.7+（新：dict 带 details）两种返回格式。
        """
        try:
            reader = self._easyocr_reader_lazy()
        except Exception:
            return ""

        try:
            img_np = np.array(region_pil)
            results = reader.readtext(img_np)
            parts = []
            for item in results:
                # EasyOCR v1.7+：item 为 dict，v1.6：item 为 tuple
                if isinstance(item, dict):
                    text = item.get("text", "")
                    conf = item.get("confidence", 0.0)
                else:
                    # (bbox, text, conf)  三元组，可能还有第四个元素 details（v1.7+）
                    try:
                        _, text, conf, *_ = item  # 兼容 3~4+ 元素
                    except TypeError:
                        continue
                if conf >= 0.35 and text:
                    parts.append(text.strip())
            return "".join(parts)
        except Exception as e:
            logger.warning(f"[OCR] 识别异常: {str(e)[:120]}")
            return ""

    @staticmethod
    def _ocr_text_indicates_connecting(text: str) -> bool:
        """根据 OCR 结果判断是否仍含「正在连接」类提示（兼容常见误识）。"""
        if not text:
            return False
        compact = re.sub(r"\s+", "", text)
        compact = compact.replace("…", ".").replace("···", "...")
        if "正在连接" in compact:
            return True
        if re.search(r"正在.{0,4}连接", compact):
            return True
        if "正在连" in compact and "接" in compact:
            return True
        return False

    @staticmethod
    def _ocr_text_indicates_preparing(text: str) -> bool:
        """根据 OCR 结果判断是否仍含「准备播放」类提示（兼容常见误识）。"""
        if not text:
            return False
        compact = re.sub(r"\s+", "", text)
        compact = compact.replace("…", ".").replace("···", "...")
        if "准备播放" in compact:
            return True
        if re.search(r"准备.{0,4}播放", compact):
            return True
        if "准备播" in compact:
            return True
        return False

    @staticmethod
    def _ocr_text_is_still_loading(text: str) -> bool:
        """
        综合判断：OCR 结果中是否还有未消失的加载/准备类文案。
        任一存在即视为「仍在加载中」。
        """
        return (
            EventPage._ocr_text_indicates_connecting(text)
            or EventPage._ocr_text_indicates_preparing(text)
        )

    def wait_for_loading_by_ocr_connecting_text(
        self,
        timeout=30,
        check_interval=0.5,
        stable_clear_count=2,
    ):
        """
        通过 EasyOCR 截图识别「正在连接...」/「准备播放...」文案：
        连续 stable_clear_count 次两者都未识别到 → 判定加载提示已消失，并保存 ADB 截图到 temp。

        依赖：pip install easyocr（首次运行自动下载模型，约 300MB）

        Args:
            timeout (int): 最大等待秒数，默认 30
            check_interval (float): 轮询间隔，默认 0.5s（OCR 耗时略长，不宜太密）
            stable_clear_count (int): 连续多少次两者都未识别到才认为结束（防抖），默认 2

        Returns:
            bool: 认为加载提示已消失返回 True；超时或 OCR 不可用返回 False
        """
        try:
            self._easyocr_reader_lazy()  # 预检查模型是否可加载
        except Exception:
            logger.error("[OCR等待] EasyOCR 初始化失败，无法使用 wait_for_loading_by_ocr_connecting_text")
            return False

        start = time.time()
        consecutive_clear = 0
        saved = False
        logger.info(
            f"[OCR等待] 开始通过 EasyOCR 监测「正在连接/准备播放」消失，timeout={timeout}s，"
            f"stable_clear_count={stable_clear_count}"
        )

        while time.time() - start < timeout:
            try:
                full = self._capture_screenshot_as_pil()
                region = self._pil_crop_loading_region(full)
                raw_text = self._ocr_recognize_connecting_region_text(region)
                still_loading = self._ocr_text_is_still_loading(raw_text)
                elapsed = time.time() - start

                if still_loading:
                    consecutive_clear = 0
                    snippet = re.sub(r"\s+", " ", raw_text).strip()[:80]
                    logger.debug(f"[OCR等待] 仍识别到加载类文案（{elapsed:.1f}s）: {snippet!r}")
                else:
                    consecutive_clear += 1
                    if consecutive_clear >= stable_clear_count:
                        logger.info(
                            f"[OCR等待] 已连续 {stable_clear_count} 次未识别到「正在连接/准备播放」，"
                            f"判定加载提示已消失（耗时 {elapsed:.1f}s）"
                        )
                        if not saved:
                            self._save_adb_screenshot_to_temp("ocr_loading_done")
                            saved = True
                        return True

                time.sleep(check_interval)
            except Exception as e:
                if self._is_uiautomator2_crashed(e):
                    try:
                        self._recover_uiautomator2()
                    except RuntimeError:
                        # 恢复失败才真正退出
                        logger.error("[OCR等待] UiAutomator2 恢复失败，终止等待")
                        raise
                    # 恢复成功后继续等待，不计入超时
                    elapsed = time.time() - start
                    logger.warning(f"[OCR等待] UiAutomator2 已恢复，继续等待（已用时 {elapsed:.1f}s）")
                    consecutive_clear = 0
                    time.sleep(1.0)
                    continue
                logger.warning(f"[OCR等待] 循环异常: {str(e)[:120]}")
                consecutive_clear = 0
                time.sleep(check_interval)

        # 超时时：若从未保存过截图，保存一张 ADB 截图供排查
        if not saved:
            logger.warning("[OCR等待] 超时，保存 ADB 截图到 temp 供排查")
            self._save_adb_screenshot_to_temp("ocr_loading_timeout")
        logger.warning(f"[OCR等待] 超时（{timeout}s），仍可能存在加载提示")
        return False

    def wait_for_loading_by_adb_screen(self, timeout=30, check_interval=0.3):
        """
        方法2：基于 ADB 实时截图检测加载动画消失（备选方案）

        原理：
        - 使用 ADB screencap 直接获取屏幕帧，比 Appium 截图更实时
        - 通过帧间差异检测画面是否还在变化（加载动画会持续变化）
        - 画面静止后认为加载完成

        Args:
            timeout (int): 最大等待时间（秒），默认 30
            check_interval (float): 检测间隔（秒），默认 0.3

        Returns:
            bool: 加载动画消失返回 True，超时返回 False
        """
        start_time = time.time()
        last_hash = None
        stable_frame_count = 0
        stable_threshold = 3  # 连续 3 帧相同认为画面静止
        saved = False

        logger.info("[ADB检测] 开始检测加载动画消失")

        while time.time() - start_time < timeout:
            try:
                # 使用 ADB screencap 获取原始帧数据
                result = subprocess.run(
                    ["adb", "exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=2,
                    check=False
                )

                if result.returncode == 0 and len(result.stdout) > 0:
                    img = Image.open(BytesIO(result.stdout)).convert("RGB")
                    img_array = np.array(img)

                    # 计算屏幕中央区域的哈希值（简化版：采样像素）
                    h, w = img_array.shape[:2]
                    left = int(w * 0.35)
                    right = int(w * 0.65)
                    top = int(h * 0.15)
                    bottom = int(h * 0.50)
                    region = img_array[top:bottom, left:right]

                    # 简化的帧哈希：采样少量像素
                    sample_points = [
                        (region.shape[0]//2, region.shape[1]//2),
                        (region.shape[0]//3, region.shape[1]//3),
                        (region.shape[0]//3*2, region.shape[1]//3*2),
                    ]
                    hash_value = tuple(
                        tuple(region[y, x]) for x, y in sample_points
                    )

                    if last_hash is None:
                        last_hash = hash_value
                    elif hash_value == last_hash:
                        stable_frame_count += 1
                        if stable_frame_count >= stable_threshold:
                            elapsed = time.time() - start_time
                            logger.info(f"[ADB检测] 画面已静止（耗时 {elapsed:.1f}s）")
                            # 检测到消失后，使用 ADB 截图保存到 temp 目录
                            if not saved:
                                self._save_adb_screenshot_to_temp("adb_loading_done")
                                saved = True
                            return True
                    else:
                        stable_frame_count = 0
                        last_hash = hash_value

                    logger.debug(f"[ADB检测] 帧变化中... stable={stable_frame_count}")

                time.sleep(check_interval)

            except subprocess.TimeoutExpired:
                logger.debug("[ADB检测] ADB 超时，继续等待")
            except Exception as e:
                logger.debug(f"[ADB检测] 检测异常: {str(e)}")

        logger.warning(f"[ADB检测] 等待加载动画消失超时（{timeout}秒）")
        return False

    def _playback_region_stats_from_rgb_array(self, img_rgb: np.ndarray):
        """
        在整张 RGB 图上按 self._loading_region 比例取子区域，计算与 wait_for_loading_by_brightness 一致的采样语义。
        """
        h, w = img_rgb.shape[:2]
        left = int(w * self._loading_region["left_ratio"])
        right = int(w * self._loading_region["right_ratio"])
        top = int(h * self._loading_region["top_ratio"])
        bottom = int(h * self._loading_region["bottom_ratio"])
        region = img_rgb[top:bottom, left:right].astype(np.float64)
        r = region[..., 0]
        g = region[..., 1]
        b = region[..., 2]
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        avg_luma = float(np.mean(luma))
        std_luma = float(np.std(luma))
        ch = region.shape[0] // 2
        cw = region.shape[1] // 2
        ctr = luma[max(0, ch - 20): ch + 20, max(0, cw - 20): cw + 20]
        center_luma = float(np.mean(ctr))
        # 典型「连接中 / 未起播」大灰底 (#333 附近)
        dark_plain = (luma >= 38) & (luma <= 72)
        dark_plain_ratio = float(np.mean(dark_plain))
        return {
            "avg_luma": avg_luma,
            "std_luma": std_luma,
            "center_luma": center_luma,
            "dark_plain_ratio": dark_plain_ratio,
        }

    def _infer_play_success_from_region_stats(self, s: dict):
        """
        根据区域亮度、纹理、灰底占比推断是否已真正播放画面（非静态占位）。
        """
        if (
            s["dark_plain_ratio"] >= self._PLAY_FAIL_DARK_PLAIN_RATIO
            and s["std_luma"] < self._PLAY_FAIL_LUMA_STD_MAX
            and s["avg_luma"] < self._PLAY_FAIL_LUMA_MEAN_MAX
        ):
            return False, (
                f"疑似未起播/连接中(灰底占比={s['dark_plain_ratio']:.2f}>={self._PLAY_FAIL_DARK_PLAIN_RATIO}, "
                f"luma_std={s['std_luma']:.1f}<{self._PLAY_FAIL_LUMA_STD_MAX}, "
                f"luma_mean={s['avg_luma']:.1f}<{self._PLAY_FAIL_LUMA_MEAN_MAX})"
            )
        if (
            s["avg_luma"] < self._PLAY_FAIL_ABSOLUTE_LUMA_MEAN
            and s["std_luma"] < self._PLAY_FAIL_ABSOLUTE_LUMA_STD
        ):
            return False, (
                f"亮度过低且无纹理(luma_mean={s['avg_luma']:.1f}, luma_std={s['std_luma']:.1f})"
            )
        return True, (
            f"判定已起播(luma_mean={s['avg_luma']:.1f}, luma_std={s['std_luma']:.1f}, "
            f"center={s['center_luma']:.1f}, gray_ratio={s['dark_plain_ratio']:.2f})"
        )

    def check_play_exception_by_pillow(self):
        """
        通过 Pillow 全屏截图灰底判定视频是否播放成功。
        与 check_play_exception（DOM 播放按钮）签名一致，返回 (is_normal, error_msg)。

        判断逻辑：取屏幕 _loading_region 区域，计算灰底占比与亮度方差，
        识别「正在连接/未起播」的灰色占位画面。
        """
        try:
            full_im = self._capture_screenshot_as_pil()
            arr = np.array(full_im.convert("RGB"))
            stats = self._playback_region_stats_from_rgb_array(arr)
            play_ok, detail = self._infer_play_success_from_region_stats(stats)
            msg = detail if play_ok else f"Pillow判定播放失败: {detail}"
            return play_ok, msg
        except Exception as e:
            return False, f"Pillow判定异常: {str(e)[:120]}"

    def _save_pillow_debug_screenshot(self, item_event_time):
        """
        纯存档：截取视频大画面区域，保存到 screenshots/pillow_debug/。
        不做播放判定，仅供事后人工复查。
        """
        try:
            el = self.driver.find_element(*self.live_root_zoom)
            full_im = self._capture_screenshot_as_pil()
            r = el.rect
            left, top = int(r["x"]), int(r["y"])
            w, h = int(r["width"]), int(r["height"])
            crop_im = full_im.crop((left, top, left + w, top + h))

            save_dir = os.path.join("screenshots", "pillow_debug")
            os.makedirs(save_dir, exist_ok=True)
            safe_event_time = item_event_time.replace(":", "-").replace(" ", "_")
            save_name = f"Pillow_{safe_event_time}.png"
            save_path = os.path.join(save_dir, save_name)
            crop_im.save(save_path)
            logger.info(f"[存档] Pillow截图已保存: {save_path}")
        except Exception as e:
            logger.warning(f"[存档] Pillow截图保存失败: {str(e)[:120]}")

    @staticmethod
    def merge_verdict(play_ok, play_msg, pillow_ok, pillow_detail, screenshot_path=None):
        """
        将 play_check_fn 结果与 Pillow 判定合并：两者均通过才记为 PASS。
        单通道（只用 Pillow）时 play_msg 可传空字符串。
        """
        final_ok = bool(play_ok) and bool(pillow_ok)
        if final_ok:
            remark = f"{play_msg} | {pillow_detail}" if play_msg else pillow_detail
        else:
            parts = []
            if play_msg:
                parts.append(play_msg)
            if not pillow_ok:
                parts.append(f"PillowFAIL:{pillow_detail}")
            elif not play_ok:
                parts.append(f"PillowOK({pillow_detail})")
            remark = " | ".join(parts) if parts else pillow_detail
        if screenshot_path:
            remark += f" | 截图:{screenshot_path}"
        return final_ok, remark

    def _take_pillow_debug_screenshot(self, item_event_time):
        """
        截取视频大画面区域，保存到 screenshots/pillow_debug/，并按与 wait_for_loading_by_brightness
        相同的区域比例做亮度/纹理分析，判断是否真的在播放（排除「正在连接…」类灰底占位）。

        Returns:
            tuple: (save_path 或 None, play_ok: bool, detail: str)
        """
        play_ok, detail, save_path = self.check_video_play_by_pillow_with_screenshot(item_event_time)
        if save_path:
            logger.info(f"Pillow截图已保存: {save_path} | {'PASS' if play_ok else 'FAIL'} | {detail}")
        else:
            logger.warning(f"Pillow截图保存失败: {detail}")
        return save_path, play_ok, detail

    def analyze_pillow_screenshots_and_report(self, screenshot_dir, output_file="事件播放结果.xlsx"):
        """
        遍历 screenshots/pillow_debug/ 目录下所有 Pillow_*.png，
        用 Pillow 分析并汇总结果到 Excel。
        截图文件以 Pillow_事件时间 命名，解析文件名得到 item_event_time。
        """
        report_rows = []
        seq = 0
        if not os.path.isdir(screenshot_dir):
            logger.warning(f"Pillow截图目录不存在: {screenshot_dir}")
            return

        for fname in sorted(os.listdir(screenshot_dir)):
            if not fname.startswith("Pillow_") or not fname.endswith(".png"):
                continue
            seq += 1
            fpath = os.path.join(screenshot_dir, fname)
            try:
                im = Image.open(fpath).convert("RGB")
                im.thumbnail((256, 256))
                gray = im.convert("L")
                st = ImageStat.Stat(gray)
                std = float(st.stddev[0])
                mean = float(st.mean[0])

                # 从文件名解析事件时间
                # 保存格式：item_event_time = "03-26 17:38:02"
                #   → safe_event_time = "03-26_17-38-02"
                #   → save_name = "Pillow_03-26_17-38-02.png"
                # 解析回来：把时分秒的 "-" 换回 ":"
                #   raw = "03-26_17-38-02" → 把最后两个 "-" 换回 ":"
                safe = fname.replace("Pillow_", "").replace(".png", "")
                parts = safe.rsplit("-", 2)
                event_time = f"{parts[0]} {parts[1]}:{parts[2]}"

                # 判定：std 过低（灰底/加载中）或 mean 极低（夜间暗景）
                std_threshold = 14.0
                mean_threshold = 80.0
                if std < std_threshold or mean < mean_threshold:
                    result = "FAIL"
                    msg = f"灰度std={std:.1f}(<{std_threshold}), mean={mean:.1f}(<{mean_threshold})"
                else:
                    result = "PASS"
                    msg = f"灰度std={std:.1f}, mean={mean:.1f}"

                logger.info(f"[{seq}] {event_time} → {result} | {msg}")
                report_rows.append({
                    "次数": seq,
                    "事件时间": event_time,
                    "结果": result,
                    "备注": msg,
                })
            except Exception as e:
                logger.warning(f"分析截图失败 {fname}: {str(e)}")
                report_rows.append({
                    "次数": seq,
                    "事件时间": fname,
                    "结果": "FAIL",
                    "备注": f"分析异常: {str(e)[:60]}",
                })

        if report_rows:
            excel_reporter.append_to_report(report_rows, output_file)
            logger.info(f"Pillow分析完成，共 {len(report_rows)} 条，已写入 {output_file}")
        else:
            logger.warning("未找到任何Pillow截图，无需写入报告")

    # 点击卡录
    def click_card_record(self):
        current_time = self.get_current_time()
        try:
            with allure.step(f"执行时间：{current_time} ---- 点击卡录按钮"):
                self.click(self.sd_record)
        except Exception as e:
            self._handle_error(f"点击卡录按钮失败: {str(e)}", f"点击卡录按钮失败{current_time}")


    # 判断录像是否是视频
    def _is_video_item(self, item_element):
        """
        判断是否为视频（存在播放图标）
        :param item_element:
        :return:
        """
        try:
            play_icon = item_element.find_element(*self.play_icon)
            return play_icon.is_displayed()
        except Exception as e:
            return  False

    @staticmethod
    def _parse_duration(duration_text: str) -> int:
        """
        解析视频时长字符串，返回秒数。
        支持格式：MM:SS（如 "00:09"、"01:30"）
        :param duration_text: 时长文本，如 "00:09"
        :return: 秒数，如 9
        """
        try:
            if not duration_text:
                return 0
            parts = duration_text.strip().split(":")
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            elif len(parts) == 1:
                return int(parts[0])
            return 0
        except Exception:
            return 0

    def _get_video_duration(self, item_element) -> int:
        """
        获取指定列表项的视频时长（秒）
        :param item_element: 列表项元素
        :return: 时长秒数
        """
        try:
            duration_text = item_element.find_element(*self.video_duration).get_attribute("text").strip()
            return self._parse_duration(duration_text)
        except Exception:
            return 0

    # 简单粗暴使用adb命令直接执行
    def adb_play_exception_by_play_button(self):
        # 第一步 点击预览区域
        self.tap_adb(x=87, y=353)
        logger.info("adb 点击预览区域")
        time.sleep(1)
        # 第二步 点击播放按钮
        self.tap_adb(x=358, y=339)
        logger.info("adb 点击播放按钮")
        # 第三步 关闭预览区域
        self.tap_adb(x=87, y=353)
        logger.info("adb 关闭预览区域")

    # 通过播放按钮(iv_play_state)是否可见来判断视频是否播放成功。
    def check_play_exception_by_play_button(self, item_event_time: str = None):
        """
        通过播放按钮(iv_play_state)是否可见来判断视频是否播放成功。
        流程（对应 xml.txt → xml2.txt 状态变化）：
          1. 检测播放按钮是否可见；
          2. 已可见 → 直接点击 → PASS；
          3. 不可见 → 点击视频预览区弹出按钮 → 等待按钮出现 → 点击 → PASS；
          4. 超时仍不可见 → FAIL。
        返回 (is_normal, error_msg)，与 check_play_exception 签名一致。
        """
        def _wait_and_click_button(timeout=2):
            """等待播放按钮出现并点击，超时返回 False"""
            try:
                wait = WebDriverWait(self.driver, timeout=timeout)
                btn = wait.until(EC.visibility_of_element_located(self.play_button_on_video))
                btn.click()
                return True
            except Exception:
                return False

        try:
            # ① 先检测播放按钮是否已可见
            if self.is_element_visible(self.play_button_on_video):
                # 播放按钮
                self.click(self.play_button_on_video)
                msg = f"播放按钮已可见并点击(item_event_time={item_event_time})，PASS"
                logger.info(msg)
                return True, msg

            # ② 按钮不可见，点击预览区弹出按钮
            preview = self.driver.find_element(*self.video_preview_area)
            preview.click()
            logger.info("播放按钮不在眼前，已点击预览区域(texture_view1)，等待按钮出现...")

            # ③ 等待播放按钮出现并点击
            if _wait_and_click_button(timeout=5):
                msg = f"点击预览区后播放按钮出现并点击(item_event_time={item_event_time})，PASS"
                logger.info(msg)
                return True, msg

            # ④ 超时：按钮始终未出现
            msg = f"播放按钮未出现(超时)(item_event_time={item_event_time})"
            logger.error(msg)
            self._handle_error("播放按钮未出现", f"播放按钮异常_{item_event_time}")
            return False, msg
        except Exception as e:
            err = f"播放按钮检测异常: {str(e)[:80]}"
            logger.error(err)
            return False, err

    def _play_all_videos_from_top_option(self, max_loops, play_check_fn):
        """
        从顶部开始逐条播放所有视频（压测用）；播放是否正常统一由 play_check_fn 判定。
        play_check_fn(item_event_time) 返回 (ok: bool, msg: str)。

        每条视频播放结束后：
        1. 调用 play_check_fn → 获得 (is_normal, error_msg)
        2. 调用 _save_pillow_debug_screenshot → 截图存档（不参与 PASS/FAIL）
        3. 记入 report_buffer，finally 中统一落 Excel

        直到滚动到列表底部时结束。
        """
        processed_event_times = set()
        last_play_time = None
        report_buffer = []

        try:
            for loop in range(1, max_loops + 1):
                with allure.step(f"第 {loop} 轮 - 从顶部逐条播放所有视频"):
                    logger.info(f"第 {loop} 轮，从顶部开始播放...")
                    MAX_SCROLL_ROUNDS = 1000
                    TARGET_STAGNANT = 3
                    stagnant_bottom_times = 0
                    scroll_round = 0

                    while scroll_round < MAX_SCROLL_ROUNDS:
                        scroll_round += 1

                        self.wait_for_recycler_view_loaded(timeout=10)
                        items = self.driver.find_elements(*self.item_root)
                        logger.info(
                            f"[loop {loop} / scroll {scroll_round}] 可见 {len(items)} 条，已处理 {len(processed_event_times)} 条"
                        )

                        idx = 0
                        while idx < len(items):
                            item = items[idx]
                            idx += 1

                            if not self._is_video_item(item):
                                continue

                            item_event_time = None
                            try:
                                item_event_time = (
                                    item.find_element(*self.video_time)
                                    .get_attribute("text")
                                    .strip()
                                )
                            except Exception:
                                item_event_time = None

                            if not item_event_time or item_event_time in processed_event_times:
                                continue

                            # 过滤时长 < 5s 的短视频
                            video_duration = self._get_video_duration(item)
                            if video_duration < 5:
                                logger.info(
                                    f"跳过短视频 (时长 {video_duration}s < 5s, 事件时间: {item_event_time})"
                                )
                                continue

                            # 记录上个视频播放完到当前 item 开始点击之间的间隔
                            if idx > 1:
                                _prev_done = getattr(self, "_load_done_time", None)
                                if _prev_done is not None:
                                    _elapsed = time.time() - _prev_done
                                    logger.info(
                                        f"[耗时] 上个视频播放完 → 当前 item 开始点击: "
                                        f"{_elapsed:.2f}s（已处理 {len(processed_event_times)} 条）"
                                    )

                            with allure.step(f"播放视频（事件时间 {item_event_time}）"):
                                try:
                                    item.click()
                                    self.wait_for_loading_by_ocr_connecting_text()
                                    time.sleep(1)
                                    self._load_done_time = time.time()

                                    self.adb_play_exception_by_play_button()

                                    current_play_time = self.get_current_play_time(
                                        previous_value=last_play_time, timeout=3
                                    )
                                    last_play_time = current_play_time

                                    # ---- play_check_fn 唯一判定 ----
                                    try:
                                        is_normal, error_msg = play_check_fn(item_event_time)
                                    except TypeError:
                                        is_normal, error_msg = play_check_fn()

                                    # 无论何种判定方式，统一落盘存档（供事后人工复查）
                                    self._save_pillow_debug_screenshot(item_event_time)

                                    report_buffer.append({
                                        "次数": f"loop{loop}_scroll{scroll_round}",
                                        "事件时间": current_play_time,
                                        "结果": "PASS" if is_normal else "FAIL",
                                        "备注": error_msg,
                                    })
                                    logger.info(
                                        f"item_event_time: {item_event_time} | 当前播放时间: {current_play_time} "
                                        f"| 结果: {'PASS' if is_normal else 'FAIL'} | 备注: {error_msg}"
                                    )

                                    processed_event_times.add(item_event_time)

                                except Exception as e:
                                    error_text = f"异常: {str(e)[:80]}"
                                    self._handle_error("播放失败", f"item_event_time={item_event_time}")
                                    report_buffer.append({
                                        "次数": f"loop{loop}_scroll{scroll_round}",
                                        "事件时间": "N/A",
                                        "结果": "FAIL",
                                        "备注": error_text,
                                    })
                                    if item_event_time:
                                        processed_event_times.add(item_event_time)

                        # 本轮列表播完 → 滑动加载更多
                        items = self.driver.find_elements(*self.item_root)
                        idx = 0

                        (before_sig, before_has_unprocessed) = (
                            self.get_recycler_signature_and_has_unprocessed(processed_event_times)
                        )

                        logger.info("向下滑动加载更多...")
                        self.scroll_down_adb(distance_ratio=0.12)
                        self.wait_for_recycler_view_loaded(timeout=2)

                        (after_sig, after_has_unprocessed) = (
                            self.get_recycler_signature_and_has_unprocessed(processed_event_times)
                        )

                        if after_sig == before_sig and not after_has_unprocessed:
                            stagnant_bottom_times += 1
                            logger.info(
                                f"疑似到达底部: {stagnant_bottom_times}/{TARGET_STAGNANT} "
                                f"(before_has_unprocessed={before_has_unprocessed})"
                            )
                        else:
                            stagnant_bottom_times = 0

                        if stagnant_bottom_times >= TARGET_STAGNANT:
                            logger.info(
                                f"检测到列表底部，无未播放可播放事件。结束。已处理 {len(processed_event_times)} 条"
                            )
                            break

                    logger.info(f"第 {loop} 轮播放完成，共处理 {len(processed_event_times)} 条事件")

        finally:
            if report_buffer:
                logger.info(f"统一写入报告，共 {len(report_buffer)} 条记录...")
                excel_reporter.append_to_report(report_buffer, "事件播放结果.xlsx")
                logger.info("报告写入完成")


    def play_all_videos_from_top_option(self, max_loops=1):
        """
        从顶部开始逐条播放所有视频（压测用）；
        播放是否正常由 check_play_exception（DOM 播放按钮可见性）判定。

        自定义判定方式示例：

            # 仅 Pillow（灰底占位判定）
            self._play_all_videos_from_top_option(
                max_loops=2,
                play_check_fn=lambda item_time: self.check_play_exception_by_pillow()
            )

            # DOM + Pillow 双重判定（双 PASS 才记 PASS）
            def dom_plus_pillow(item_time):
                dom_ok, dom_msg = self.check_play_exception(item_time)
                pillow_ok, pillow_msg = self.check_play_exception_by_pillow()
                final = dom_ok and pillow_ok
                remark = dom_msg if final else f"{dom_msg} | {pillow_msg}"
                return final, remark
            self._play_all_videos_from_top_option(max_loops=2, play_check_fn=dom_plus_pillow)
        """
        self._play_all_videos_from_top_option(max_loops, self.check_play_exception)

    def play_all_videos_from_top_option_debug_pillow(self, max_loops=1):
        """
        PILLOW 识别
        :param max_loops:
        :return:
        """
        self._play_all_videos_from_top_option(max_loops, self.check_play_exception_by_pillow)

    def get_recycler_signature_and_has_unprocessed(self, processed_event_times: set, max_items=6):
        """
        获取 recycler_view 签名 + 判断是否存在未处理视频。
        合并调用，减少 find_elements 次数。
        返回 (signature, has_unprocessed)
        """
        try:
            items = self.driver.find_elements(*self.item_root)
            if not items:
                return ("empty", 0, ()), False

            times = []
            has_unprocessed = False

            for item in items:
                try:
                    t = item.find_element(*self.video_time).get_attribute("text").strip()
                except Exception:
                    t = None
                if t:
                    times.append(t)
                    if not has_unprocessed and self._is_video_item(item):
                        if t not in processed_event_times:
                            has_unprocessed = True

            if not times:
                return ("empty", 0, ()), False

            prefix_n = max_items // 2
            prefix = tuple(times[:prefix_n])
            suffix = tuple(times[-prefix_n:]) if prefix_n > 0 else tuple(times)
            signature = (len(times), prefix, suffix)
            return signature, has_unprocessed
        except Exception:
            return ("error", 0, ()), True
    def has_unprocessed_video_in_view(self, processed_event_times: set):
        """
        判断当前可见区域是否还存在"未处理过"的可播放事件（用于到底部判定）。
        """
        try:
            items = self.driver.find_elements(*self.item_root)
            for item in items:
                if not self._is_video_item(item):
                    continue
                try:
                    item_event_time = item.find_element(*self.video_time).get_attribute("text").strip()
                except Exception:
                    item_event_time = None
                if item_event_time and item_event_time not in processed_event_times:
                    return True
            return False
        except Exception:
            return True
    # 获取播放时间
    def get_current_play_time(self, previous_value=None, timeout: int = 20):
        """
        """
        try:
            def _read_timeline_time():
                date_el = self.driver.find_element(*self.timeline_date)
                time_el = self.driver.find_element(*self.timeline_time)

                # date_text 例： "3月 25"
                date_text = (date_el.text or date_el.get_attribute("text") or "").strip()
                time_text = (time_el.text or time_el.get_attribute("text") or "").strip()

                # 解析：3月 25 => 03-25
                m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", date_text.replace(" ", ""))
                if m:
                    month = int(m.group(1))
                    day = int(m.group(2))
                    date_part = f"{month:02d}-{day:02d}"
                else:
                    # 解析失败就原样去空格
                    date_part = date_text.replace(" ", "")

                return f"{date_part} {time_text}".strip()

            start = time.time()
            last = None
            while time.time() - start < timeout:
                current_play_time = _read_timeline_time()
                last = current_play_time
                if previous_value is None or current_play_time != previous_value:
                    logger.info(f"当前播放时长（时间轴）: {current_play_time}")
                    return current_play_time
                time.sleep(0.3)

            # 超时兜底
            logger.warning(f"获取播放时长超时，使用最后读到的值: {last}")
            return last or "N/A"
        except Exception as e:
            self._handle_error(f"获取播放时长失败: {str(e)}", "获取播放时长失败")
            return "N/A"
    def wait_for_recycler_view_loaded(self, timeout: int = 15):
        """
        显式等待 recycler_view 列表加载出来（可见 + 至少有一条记录）
        在每次点击播放视频之前必须调用
        """
        try:
            logger.info("正在等待 recycler_view 列表加载...")

            # 等待 recycler_view 控件本身可见
            self.wait.until(
                EC.visibility_of_element_located(self.recycler_view),
                message="recycler_view 列表控件未出现"
            )

            # 额外等待列表至少有一条子元素（防止空列表或正在刷新）
            WebDriverWait(self.driver, timeout, poll_frequency=0.5).until(
                lambda d: len(d.find_elements(*self.item_root)) > 0,
                message="recycler_view 已可见，但列表中没有加载出任何记录"
            )

            logger.info("列表加载完成")
            return True

        except Exception as e:
            self._handle_error(f"列表加载失败: {str(e)}", "列表加载失败")
            return False
    # 9811 详情事件播放
    def click_event_play_list_details(self):
        """
        点击详情事件播放
        """
        locator = (AppiumBy.ID, "com.xm.support.android:id/niceiamge_thumbnail")

        try:
            self.wait.until(
                EC.visibility_of_element_located(locator),
                message="详情事件列表失败"
            )
            with allure.step("点击详情事件播放"):
                self.driver.find_element(*locator).click()
        except Exception as e:
            self._handle_error(f"点击详情事件播放失败: {str(e)}", "点击详情事件播放失败")
    # 事件播放
    def click_event_play(self):
        """
        点击事件播放并判断播放是否成功
        流程：
        1. 检测当前是否正在播放（通过 layout_loading 消失 + tv_date_time 变化判断）
        2. 如果未播放，等待视频加载（layout_loading 消失）
        3. 验证播放成功：时间轴推进
        """
        try:
            with allure.step("点击事件播放并验证"):
                # 定义关键元素定位器
                loading_locator = (AppiumBy.ID, "com.xm.support.android:id/layout_loading")
                date_time_locator = (AppiumBy.ID, "com.xm.support.android:id/tv_date_time")
                timeline_date_locator = self.timeline_date
                timeline_time_locator = self.timeline_time

                # 读取初始时间轴
                def _read_timeline():
                    """读取并解析时间轴，转换为 (date_str, seconds_of_day)"""
                    try:
                        date_el = self.driver.find_element(*timeline_date_locator)
                        time_el = self.driver.find_element(*timeline_time_locator)
                        date_text = (date_el.text or date_el.get_attribute("text") or "").strip()
                        time_text = (time_el.text or time_el.get_attribute("text") or "").strip()

                        # 解析日期：3月 25 => "03-25"
                        m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", date_text.replace(" ", ""))
                        if m:
                            date_str = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
                        else:
                            date_str = date_text.replace(" ", "")

                        # 解析时间：HH:MM:SS => 秒
                        try:
                            parts = time_text.strip().split(":")
                            h = int(parts[0])
                            mn = int(parts[1])
                            s = int(parts[2]) if len(parts) > 2 else 0
                            seconds = h * 3600 + mn * 60 + s
                        except Exception:
                            seconds = -1

                        return date_str, seconds, time_text
                    except Exception:
                        return None, -1, None

                # 读取初始时间轴状态
                start_date, start_seconds, start_text = _read_timeline()
                logger.info(f"[click_event_play] 初始时间轴: {start_date} {start_text}")

                # 等待加载完成（layout_loading 消失）或时间轴推进
                max_wait_time = 15  # 最大等待15秒
                poll_interval = 1.0  # 每1秒轮询
                start_wait = time.time()
                play_success = False

                while time.time() - start_wait < max_wait_time:
                    time.sleep(poll_interval)

                    # 检查加载动画是否消失
                    try:
                        loading = self.driver.find_element(*loading_locator)
                        if not loading.is_displayed():
                            logger.info("[click_event_play] 加载动画已消失")
                    except Exception:
                        # 加载动画不存在，说明已加载
                        logger.info("[click_event_play] 未检测到加载动画")

                    # 检查时间轴是否推进
                    curr_date, curr_seconds, curr_text = _read_timeline()
                    if curr_date is not None and curr_seconds >= 0:
                        if curr_date == start_date:
                            delta = max(curr_seconds, start_seconds) - start_seconds
                            if delta > 0:
                                logger.info(f"[click_event_play] 时间轴推进正常: {start_text} → {curr_text} (+{delta}s)，播放成功")
                                play_success = True
                                break
                        elif curr_date != start_date and curr_seconds >= 0:
                            logger.info(f"[click_event_play] 日期变化/时间轴已更新: {curr_date} {curr_text}，播放成功")
                            play_success = True
                            break

                if not play_success:
                    final_date, final_seconds, final_text = _read_timeline()
                    msg = f"播放超时: 初始={start_date} {start_text}, 最终={final_date} {final_text}"
                    logger.error(f"[click_event_play] {msg}")
                    self._handle_error("视频播放超时", f"播放超时_{self.get_current_time()}")
                    return False

                logger.info(f"[click_event_play] 播放成功确认")
                return True

        except Exception as e:
            error_msg = f"点击事件播放异常: {str(e)}"
            logger.error(f"[click_event_play] {error_msg}")
            self._handle_error(error_msg, f"播放异常_{self.get_current_time()}")
            return False
