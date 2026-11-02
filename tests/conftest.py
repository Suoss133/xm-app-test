import pytest
import os
from datetime import datetime, timedelta

import yaml

from utils.crash_momitor import CrashMonitor
import subprocess
from pathlib import Path
import sys

from core.exceptions import RestartRequired, BusinessTestFailure
from core.driver import DriverManager
from utils.logger import logger
import time

# 显式注册 allure-pytest 插件，确保打包后能识别 --alluredir 参数
pytest_plugins = ["allure_pytest"]

def _get_actual_root():
    """获取程序运行的逻辑根目录"""
    if getattr(sys, 'frozen', False):
        # 打包后：D:\...\dist\App自动化测试工具
        return Path(sys.executable).parent.absolute()
    # 开发环境
    return Path(__file__).parent.parent.absolute()


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown():
    """全局前置和后置操作（仅在会话开始和结束时执行）"""
    logger.info("====== 开始执行测试套件 ======")

    # 清理过期日志
    _cleanup_old_logs()

    try:
        # 正确调用 classmethod 的方式
        DriverManager.load_app_config()  # ← 这样调用是正确的（classmethod 会自动传入 cls）
        DriverManager.keep_start_driver()

        # 启动App日志记录
        _start_app_log_recording()

    except Exception as e:
        logger.error(f"全局初始化失败: {str(e)}")
        raise

    yield

    # 后置清理
    try:
        _stop_app_log_recording()
        DriverManager.quit_driver()
    except Exception as e:
        logger.error(f"全局清理时发生异常: {str(e)}")

    logger.info("====== 测试套件执行完毕 ======")


def _get_log_dir():
    """获取日志目录"""
    log_dir = os.path.join(os.getcwd(), "app_log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return log_dir


def _cleanup_old_logs():
    """清理一周前的日志文件"""
    log_dir = _get_log_dir()
    now = datetime.now()
    one_week_ago = now - timedelta(days=7)

    for filename in os.listdir(log_dir):
        if (filename.startswith("app_error_log_") or filename.startswith("app_log_")) and filename.endswith(".log"):
            # 提取日期部分
            try:
                parts = filename.split("_")
                date_str = None

                # 遍历所有部分，找到可能的日期部分
                for part in parts:
                    # 去掉文件扩展名
                    if part.endswith(".log"):
                        part = part[:-4]

                    # 检查是否为8位数字格式的日期 (YYYYMMDD)
                    if len(part) == 8 and part.isdigit():
                        date_str = part
                        break

                # 如果找到了日期部分
                if date_str:
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    if file_date < one_week_ago:
                        file_path = os.path.join(log_dir, filename)
                        os.remove(file_path)
                        logger.info(f"已删除过期日志文件: {filename}")
                else:
                    logger.debug(f"无法从文件名中提取日期: {filename}")

            except ValueError as e:
                logger.debug(f"无法解析日志文件日期 {filename}: {str(e)}")
            except Exception as e:
                logger.warning(f"处理日志文件 {filename} 时出错: {str(e)}")


def _start_app_log_recording():
    """开始记录App后台日志（只记录错误日志）"""
    try:
        # 创建日志目录
        log_dir = _get_log_dir()

        # 生成日志文件名（按天保存）
        date_str = datetime.now().strftime("%Y%m%d")
        log_file_path = os.path.join(log_dir, f"app_error_log_{date_str}.log")

        # 启动adb logcat进程，只记录错误日志
        global log_process, log_file
        log_file = open(log_file_path, 'a')

        # 启动adb logcat进程，只记录错误日志
        log_process = subprocess.Popen([
            'adb', 'logcat',
            '-s', 'AndroidRuntime:E System.err:E',  # 只记录错误日志
            '*:S'  # 静默其他日志
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # 定义需要过滤掉的错误关键字列表
        filtered_errors = [
            "UiAutomation not connected",
            "Bad file descriptor",
            "NoSuchMethodException",
            "RuntimeException",
            "io.appium.uiautomator2.server"
        ]

        # 启动一个线程来处理日志输出，过滤掉不需要的日志
        import threading
        def filter_logs():
            try:
                for line in iter(log_process.stdout.readline, ''):
                    # 检查是否包含需要过滤的关键字
                    should_filter = any(error_keyword in line for error_keyword in filtered_errors)

                    # 如果不包含需要过滤的关键字，则记录该日志
                    if not should_filter:
                        log_file.write(line)
                        log_file.flush()
            except Exception as e:
                logger.error(f"日志过滤过程出错: {str(e)}")

        log_thread = threading.Thread(target=filter_logs, daemon=True)
        log_thread.start()

        logger.info(f"开始记录App错误日志到文件: {log_file_path}")
    except Exception as e:
        logger.error(f"启动错误日志记录失败: {str(e)}")


def _stop_app_log_recording():
    """停止记录App后台日志"""
    try:
        global log_process, log_file
        if 'log_process' in globals() and log_process and log_process.poll() is None:
            log_process.terminate()
            log_process.wait(timeout=5)
            logger.info("已停止App日志记录")

        if 'log_file' in globals() and log_file:
            log_file.close()
    except Exception as e:
        logger.error(f"停止日志记录失败: {str(e)}")


# 不重置app
@pytest.fixture(scope="function")
def keep_app_state():
    """每个测试用例执行前确保App存活，如果不存活则重新启动"""
    driver = DriverManager.get_driver()
    test_case_name = None

    try:
        test_case_name = pytest.current_test_node.nodeid.split("::")[-1]

        # 检查App是否存活，如果不存活则重新启动
        if not _is_app_alive(driver):
            logger.warning(f"检测到App未存活，正在重新启动App...")
            _restart_app(driver)

        yield driver
    except Exception as e:
        # 检查是否是闪退
        if CrashMonitor.is_app_crashed(e) and test_case_name:
            CrashMonitor.handle_crash(test_case_name)
        raise
    finally:
        pass  # 每条用例结束后，不在默认返回到首页


def _is_app_alive(driver):
    """检查App是否存活"""
    try:
        # 尝试获取当前Activity，如果App崩溃或未响应会抛出异常
        current_activity = driver.current_activity
        # 检查是否能正常执行基本操作
        driver.current_package
        return True
    except Exception as e:
        logger.debug(f"App状态检查失败: {str(e)}")
        return False


def _restart_app(driver):
    """重新启动App"""
    try:
        app_package = driver.capabilities.get('appPackage', 'com.xm.support.android')
        # 终止App
        driver.terminate_app(app_package)
        # 启动App
        driver.activate_app(app_package)
        # 等待App启动完成
        time.sleep(3)
        logger.info(f"App已重新启动: {app_package}")
    except Exception as e:
        logger.error(f"重启App失败: {str(e)}")
        # 如果重启失败，尝试完全重启驱动
        try:
            DriverManager.restart_start_driver()
            logger.info("驱动已重新启动")
        except Exception as restart_error:
            logger.error(f"驱动重启失败: {str(restart_error)}")
            raise


# 每个测试前重置app
@pytest.fixture(scope="function")
def reset_app():
    """每个测试用例执行前重置App状态"""
    DriverManager.quit_driver()  # 退出当前驱动
    DriverManager.restart_start_driver()  # 启动新驱动（触发App重置）
    driver = DriverManager.get_driver()
    test_case_name = None

    try:
        test_case_name = pytest.current_test_node.nodeid.split("::")[-1]
        yield driver
    except Exception as e:
        if CrashMonitor.is_app_crashed(e) and test_case_name:
            CrashMonitor.handle_crash(test_case_name)
        raise
    finally:
        # 测试结束后也执行清理
        try:
            logger.info("重置App fixture结束后清理App状态")
            app_package = driver.capabilities.get('appPackage', 'com.xm.support.android')
            driver.terminate_app(app_package)
            logger.info(f"测试结束后终止App进程: {app_package}")
        except Exception as e:
            logger.error(f"测试结束后清理App状态时发生错误: {str(e)}")
            raise AssertionError(e)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        exc = call.excinfo.value if call.excinfo else None
        err_msg = str(exc) if exc else ""

        # 1. 明确需要重启
        if isinstance(exc, RestartRequired):
            logger.info("收到 RestartRequired，执行 App 重启...")
            _restart_app_only()
            return

        # 2. 业务失败但不需要重启（出图失败等）
        if isinstance(exc, BusinessTestFailure):
            logger.info(f"业务失败（不重启）: {err_msg}")
            return

        # 3. 驱动级致命错误
        fatal_errors = [
            "instrumentation process is not running",
            "socket hang up",
            "Could not proxy",
        ]
        if any(e in err_msg for e in fatal_errors):
            logger.error("检测到驱动崩溃，执行全量重连...")
            DriverManager.restart_start_driver()
            return

        # 4. 其他失败默认重启 App
        logger.info("其他失败，重启 App 进程...")
        _restart_app_only()

def _restart_app_only():
    """只重启 App，不重建驱动"""
    try:
        d = DriverManager.get_driver()
        pkg = DriverManager.get_current_package()
        d.terminate_app(pkg)
        time.sleep(2)
        d.activate_app(pkg)
        logger.info(f"App 已重启: {pkg}")
    except Exception as e:
        logger.error(f"App 重启失败: {e}")

# 获取当前测试节点
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    pytest.current_test_node = item


import os
from pathlib import Path
import yaml
from utils.logger import logger

def pytest_collection_modifyitems(config, items):
    """根据 YAML 配置过滤测试用例；优先使用调度器注入的 TEST_SUITE_YAML"""
    runtime = os.environ.get("TEST_SUITE_YAML")
    if runtime and Path(runtime).exists():
        yaml_path = Path(runtime)
        logger.info(f"[conftest] 使用运行时配置: {yaml_path}")
    else:
        # 兼容打包 / 开发路径（按你现有逻辑保留）
        if getattr(sys, "frozen", False):
            root = Path(sys.executable).parent
            yaml_path = root / "_internal" / "config" / "test_suite.yaml"
        else:
            root = Path(__file__).resolve().parent.parent  # 若 conftest 在 tests/ 下
            # 若 conftest 在项目根，则用 Path(__file__).resolve().parent
            yaml_path = root / "config" / "test_suite.yaml"
            if not yaml_path.exists():
                yaml_path = Path(__file__).resolve().parent / "config" / "test_suite.yaml"

    if not yaml_path.exists():
        logger.error(f"找不到配置文件: {yaml_path}")
        return

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            suite_config = yaml.safe_load(f) or {}

        enabled_suites = set()
        for name, cfg in suite_config.get("items", {}).items():
            if cfg.get("enabled", False):
                enabled_suites.add(name.lower())

        logger.info(f"启用的测试套件：{enabled_suites}")

        if not enabled_suites:
            logger.warning("没有 enabled:true 的套件，将不过滤（收集全部）")
            # 可选策略 A：不过滤
            # return
            # 可选策略 B：全部取消（保持你原来的严格行为）
            items[:] = []
            logger.info("过滤后收集到的测试用例数: 0")
            return

        filtered = []
        for item in items:
            file_path = str(item.fspath if hasattr(item, "fspath") else item.path)
            file_name = os.path.basename(file_path)

            pure_name = ""
            if file_name.startswith("test_") and file_name.endswith(".py"):
                pure_name = file_name[5:-3].lower()  # test_KoocamSlidingEvent.py → koocamslidingevent

            # 套件名与文件名对齐：KoocamSlidingEvent → koocamslidingevent
            if pure_name in enabled_suites:
                filtered.append(item)
            else:
                # 兼容：suite 名带下划线、路径在子目录等
                for suite in enabled_suites:
                    if suite in pure_name or pure_name in suite:
                        filtered.append(item)
                        break

        items[:] = filtered
        logger.info(f"过滤后收集到的测试用例数: {len(items)}")

    except Exception as e:
        logger.error(f"过滤用例插件执行异常: {e}")