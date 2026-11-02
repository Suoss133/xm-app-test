# core/driver.py
import os
import sys
import threading
import time
import subprocess
from pathlib import Path

import yaml
from appium import webdriver
from appium.options.android import UiAutomator2Options

from selenium.common import WebDriverException, TimeoutException, InvalidSessionIdException, NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.logger import logger


class DriverManager:
    _driver = None
    _current_app_config = None
    _screen_keep_alive_set = False  # 新增：标记是否已设置屏幕常亮

    _heartbeat_lock = threading.Lock()  # 防止并发心跳
    _last_heartbeat_time = 0.0
    _heartbeat_interval_sec = 35
    _max_reconnect_attempts = 4

    # ====================== 屏幕常亮 ======================
    @classmethod
    def _set_screen_keep_alive(cls):
        """
        使用 adb 命令把屏幕超时设置为最大值，防止自动休眠
        只在驱动启动后执行一次
        """
        if cls._screen_keep_alive_set:
            logger.debug("屏幕常亮已设置，跳过")
            return

        try:
            # 获取设备 UDID
            udid = None
            if cls._driver:
                try:
                    udid = cls._driver.capabilities.get("appium:udid") or cls._driver.capabilities.get("udid")
                except:
                    pass

            # 如果从 driver 获取不到，从配置中获取
            if not udid and cls._current_app_config:
                udid = cls._current_app_config.get("udid") or cls._current_app_config.get("device_name")

            # 构建 adb 命令
            cmd = ["adb"]
            if udid:
                cmd.extend(["-s", udid])
            cmd.extend(["shell", "settings", "put", "system", "screen_off_timeout", "2147483647"])

            logger.info(f"[屏幕常亮] 执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                cls._screen_keep_alive_set = True
                logger.info("[屏幕常亮] ✅ 已成功设置屏幕超时时间为最大值（防止自动休眠）")
            else:
                logger.warning(f"[屏幕常亮] ⚠️ 设置失败: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning("[屏幕常亮] ⚠️ adb 命令执行超时")
        except Exception as e:
            logger.warning(f"[屏幕常亮] ⚠️ 设置屏幕常亮失败: {e}")

    # ====================== 心跳与重连 ======================
    @classmethod
    def heartbeat(cls):
        """发送心跳，保持 session 活跃。建议在每个操作前调用"""
        with cls._heartbeat_lock:
            now = time.time()
            if now - cls._last_heartbeat_time < cls._heartbeat_interval_sec:
                return

            if cls._driver is None:
                cls.keep_start_driver()
                return

            try:
                _ = cls._driver.current_package
                cls._last_heartbeat_time = now
                logger.debug("Appium heartbeat sent successfully")
            except (WebDriverException, InvalidSessionIdException, ConnectionResetError) as e:
                logger.warning(f"Heartbeat failed, session likely lost: {str(e)}")
                cls._attempt_reconnect()

    @classmethod
    def _attempt_reconnect(cls):
        """尝试重连，失败次数过多则抛出异常"""
        attempts = 0
        while attempts < cls._max_reconnect_attempts:
            attempts += 1
            wait_sec = min(10 * (2 ** (attempts - 1)), 60)
            logger.info(f"Attempting reconnect ({attempts}/{cls._max_reconnect_attempts}) after {wait_sec}s...")
            time.sleep(wait_sec)

            try:
                cls.restart_start_driver()
                cls._last_heartbeat_time = time.time()
                logger.info("Reconnect succeeded")
                return
            except Exception as e:
                logger.error(f"Reconnect failed: {str(e)}")

        logger.critical("Max reconnect attempts reached. Giving up.")
        raise RuntimeError("Appium session cannot be recovered after multiple attempts")

    # ====================== 动态获取设备 ======================
    @classmethod
    def _get_device_name_from_adb(cls):
        """通过 adb devices 动态获取当前连接的设备 UDID"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False
            )

            output = result.stdout.strip()
            logger.info(f"[ADB] 执行 adb devices 输出:\n{output}")

            lines = output.splitlines()
            devices = []

            for line in lines[1:]:  # 跳过标题行 "List of devices attached"
                line = line.strip()
                if line and "device" in line and "unauthorized" not in line.lower():
                    udid = line.split()[0].strip()
                    if udid:
                        devices.append(udid)

            if not devices:
                logger.error("[ADB] 未检测到任何已连接的 Android 设备！")
                raise RuntimeError("未检测到 Android 设备，请连接设备并在手机上允许 USB 调试和 ADB 授权后重试。")

            if len(devices) > 1:
                logger.warning(f"[ADB] 检测到多个设备 ({len(devices)} 个)，自动使用第一个: {devices[0]}")

            logger.info(f"[ADB] 成功获取设备 UDID: {devices[0]}")
            return devices[0]

        except subprocess.TimeoutExpired:
            logger.error("[ADB] 执行 adb devices 超时")
            raise RuntimeError("ADB 命令执行超时，请检查 ADB 是否正常安装并运行")
        except Exception as e:
            logger.error(f"[ADB] 获取设备失败: {str(e)}")
            raise RuntimeError(f"ADB 获取设备失败: {str(e)}")

    @classmethod
    def load_app_config(cls, app_name=None):
        """
        优先级：
        1. 入参 app_name
        2. 环境变量 CURRENT_APP
        3. TEST_SUITE_YAML（或默认 test_suite.yaml）中第一个 enabled 项的 current_app
        """
        try:
            if getattr(sys, "frozen", False):
                base_path = Path(sys.executable).parent / "_internal"
            else:
                base_path = Path(__file__).parent.parent

            # ---------- 解析 suite yaml 路径 ----------
            runtime = os.environ.get("TEST_SUITE_YAML")
            if runtime and Path(runtime).exists():
                suite_path = Path(runtime)
                logger.info(f"[Driver] 使用运行时配置: {suite_path}")
            else:
                suite_path = base_path / "config" / "test_suite.yaml"
                logger.info(f"[Driver] 使用默认配置: {suite_path}")

            current_app = None
            preferred_udid = None

            if suite_path.exists():
                with open(suite_path, "r", encoding="utf-8") as f:
                    suite_config = yaml.safe_load(f) or {}

                for item_name, item_data in (suite_config.get("items") or {}).items():
                    if item_data.get("enabled") is True:
                        current_app = item_data.get("current_app")
                        preferred_udid = (
                                item_data.get("device_udid")
                                or item_data.get("device_serial")
                        )
                        logger.info(
                            f"[Driver] enabled 套件: {item_name} → "
                            f"App={current_app}, udid={preferred_udid or '自动'}"
                        )
                        break

            # 环境变量覆盖
            env_app = os.environ.get("CURRENT_APP")
            if env_app:
                current_app = env_app.strip()
                logger.info(f"[Driver] CURRENT_APP 环境变量覆盖: {current_app}")

            if app_name:
                current_app = app_name
                logger.info(f"[Driver] 入参 app_name 覆盖: {current_app}")

            if not current_app:
                raise ValueError(
                    "无法确定 current_app。请设置环境变量 CURRENT_APP，"
                    "或在 test_suite.yaml 中为启用项填写 current_app"
                )

            # ---------- environment.yaml ----------
            env_path = base_path / "config" / "environment.yaml"
            if not env_path.exists():
                raise FileNotFoundError(f"environment.yaml 不存在: {env_path}")

            with open(env_path, "r", encoding="utf-8") as f:
                env_config = yaml.safe_load(f)

            if "environments" not in env_config or current_app not in env_config["environments"]:
                raise KeyError(f"environment.yaml 中未找到 App 配置: {current_app}")

            # 设备：环境变量 ANDROID_SERIAL > yaml device_udid > adb 第一台
            preferred_udid = (
                    os.environ.get("ANDROID_SERIAL")
                    or preferred_udid
            )
            device_udid = cls._resolve_device_udid(preferred_udid)

            cls._current_app_config = env_config["environments"][current_app].copy()
            cls._current_app_config["app_name_key"] = current_app
            cls._current_app_config["device_name"] = device_udid
            cls._current_app_config["udid"] = device_udid

            os.environ["ANDROID_SERIAL"] = device_udid
            os.environ["CURRENT_APP"] = current_app

            logger.info(
                f"[Driver] 配置完成 → App: {current_app} | UDID: {device_udid}"
            )
            return cls._current_app_config

        except Exception as e:
            logger.error(f"[Driver] load_app_config 失败: {e}")
            raise

    # ------------------------------------------------------------------
    # 设备列表 / UDID 解析
    # ------------------------------------------------------------------
    @classmethod
    def _list_connected_devices(cls):
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            devices = []
            for line in result.stdout.strip().splitlines()[1:]:
                line = line.strip()
                if not line:
                    continue
                if "\tdevice" in line or line.endswith(" device"):
                    udid = line.split()[0].strip()
                    if udid:
                        devices.append(udid)
            return devices
        except subprocess.TimeoutExpired:
            raise RuntimeError("ADB 命令执行超时")
        except Exception as e:
            raise RuntimeError(f"ADB 获取设备列表失败: {e}")

    @classmethod
    def _resolve_device_udid(cls, preferred_udid: str = None) -> str:
        devices = cls._list_connected_devices()
        if not devices:
            raise RuntimeError("未检测到任何已连接的 Android 设备")

        logger.info(f"[ADB] 当前在线设备: {devices}")

        if preferred_udid:
            preferred_udid = str(preferred_udid).strip()
            if preferred_udid in devices:
                logger.info(f"[ADB] 使用指定设备: {preferred_udid}")
                return preferred_udid
            logger.warning(
                f"[ADB] 指定设备 [{preferred_udid}] 不在线，回退到: {devices[0]}"
            )

        if len(devices) > 1:
            logger.warning(f"[ADB] 多设备在线，使用第一台: {devices[0]}")
        return devices[0]

    # ====================== 安全操作方法（你需要的两个函数） ======================
    @classmethod
    def safe_find_element(cls, by, value, timeout=15, poll_frequency=0.5):
        """安全的查找元素"""
        cls.heartbeat()

        def _find():
            return WebDriverWait(cls._driver, timeout, poll_frequency=poll_frequency).until(
                EC.presence_of_element_located((by, value))
            )

        try:
            return _find()

        except (TimeoutException, NoSuchElementException) as e:
            logger.debug(f"safe_find_element - 业务找不到元素: {type(e).__name__} - {str(e)[:200]}")
            raise

        except InvalidSessionIdException as e:
            logger.warning(f"Invalid session id，尝试重连: {str(e)}")
            cls._attempt_reconnect()
            return _find()

        except WebDriverException as e:
            err_str = str(e).lower()
            if any(word in err_str for word in ["session", "invalid session", "connection", "socket", "disconnected", "closed"]):
                logger.warning(f"检测到 session 相关异常，尝试重连: {str(e)[:200]}")
                cls._attempt_reconnect()
                return _find()
            else:
                logger.debug(f"safe_find_element - 非 session 的 WebDriverException: {str(e)[:200]}")
                raise
        except Exception as e:
            logger.error(f"safe_find_element 未知异常: {type(e).__name__} - {str(e)}")
            raise

    @classmethod
    def safe_click(cls, element):
        """安全的点击"""
        cls.heartbeat()

        def _click():
            element.click()

        try:
            _click()
        except (WebDriverException, InvalidSessionIdException) as e:
            logger.warning(f"click failed due to session issue: {str(e)}")
            cls._attempt_reconnect()
            _click()  # 重试一次

    # ====================== 驱动管理 ======================
    @classmethod
    def _setup_appium_options(cls):
        if cls._current_app_config is None:
            raise ValueError("App配置未加载，请先调用 load_app_config")

        options = UiAutomator2Options()
        cfg = cls._current_app_config

        capabilities = {
            "appium:platformName": cfg.get("platform_name"),
            "appium:deviceName": cfg.get("device_name"),
            "appium:udid": cfg.get("udid") or cfg.get("device_name"),
            "appium:appPackage": cfg.get("app_package"),
            "appium:appActivity": cfg.get("app_activity"),
            "appium:automationName": cfg.get("automation_name"),
            "appium:noReset": cfg.get("no_reset"),
            "appium:fullReset": cfg.get("full_reset"),
            "appium:newCommandTimeout": cfg.get("new_command_timeout"),
            "appium:uiautomator2ServerInstallTimeout": 60000,
            "appium:uiautomator2ServerLaunchTimeout": 60000,
            "appium:adbExecTimeout": 60000,
            "appium:shouldTerminateApp": True,
            "appium:forceAppLaunch": True,
        }

        chromedriver_path = cfg.get("chromedriver_executable")
        if chromedriver_path:
            if getattr(sys, "frozen", False):
                base_path = Path(sys.executable).parent / "_internal"
                new_path = (base_path / "driver" / Path(chromedriver_path).name).resolve()
                if new_path.exists():
                    capabilities["appium:chromedriverExecutable"] = str(new_path)
                else:
                    capabilities["appium:chromedriverAutodownload"] = True
            else:
                capabilities["appium:chromedriverExecutable"] = chromedriver_path

        if cfg.get("chromedriver_autodownload"):
            capabilities["appium:chromedriverAutodownload"] = True

        options.load_capabilities(capabilities)
        return options

    @classmethod
    def get_current_app(cls):
        if cls._current_app_config:
            return cls._current_app_config.get("app_name_key", "")
        return os.environ.get("CURRENT_APP", "")

    @classmethod
    def get_current_package(cls):
        if not cls._current_app_config:
            cls.load_app_config()
        return cls._current_app_config.get("app_package", "")

    @classmethod
    def get_current_activity(cls):
        if not cls._current_app_config:
            cls.load_app_config()
        return cls._current_app_config.get("app_activity", "")

    @classmethod
    def start_driver(cls, no_reset=None, full_reset=None):
        """启动驱动"""
        try:
            if cls._current_app_config is None:
                cls.load_app_config()

            options = cls._setup_appium_options()
            if no_reset is not None:
                options.no_reset = no_reset
            if full_reset is not None:
                options.full_reset = full_reset

            appium_server_url = cls._current_app_config["appium_server"]
            cls._driver = webdriver.Remote(command_executor=appium_server_url, options=options)

            logger.info(f"Appium 驱动启动成功，当前 App: {cls._current_app_config.get('app_name_key')} | Device: {cls._current_app_config.get('device_name')}")

            # ===== 新增：驱动启动后自动设置屏幕常亮 =====
            cls._set_screen_keep_alive()

            return cls._driver
        except Exception as e:
            logger.error(f"Appium 驱动启动失败: {str(e)}")
            raise


    @classmethod
    def keep_start_driver(cls):
        return cls.start_driver()

    @classmethod
    def restart_start_driver(cls):
        """彻底重置驱动"""
        try:
            cls.quit_driver()
            # 重置屏幕常亮标记，让重启后重新设置
            cls._screen_keep_alive_set = False
            time.sleep(2)
            return cls.start_driver(no_reset=True, full_reset=False)
        except Exception as e:
            logger.error(f"彻底重启驱动失败: {str(e)}")
            raise

    @classmethod
    def quit_driver(cls):
        """安全退出驱动"""
        if cls._driver is not None:
            try:
                cls._driver.quit()
                # 重置屏幕常亮标记，让重启后重新设置
                cls._screen_keep_alive_set = False
            except Exception:
                pass
            cls._driver = None
            logger.info("Appium 驱动已清理完毕")

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            if cls._current_app_config is None:
                cls.load_app_config()
            cls.keep_start_driver()
        return cls._driver
