# core/base_test_suite.py
import sys
import traceback
from datetime import datetime
from pathlib import Path

import allure
import pytest
import yaml
import importlib
import time
import os
import threading

from utils.logger import logger
from utils.crash_momitor import CrashMonitor


class BaseTestSuite:
    """测试套件基类"""

    def initialize_suite(self, suite_name):
        self.suite_name = suite_name

        runtime = os.environ.get("TEST_SUITE_YAML")
        if runtime and Path(runtime).exists():
            self.test_suite_config = self._load_yaml_file(Path(runtime))
            logger.info(f"[Suite] 使用运行时配置: {runtime}")
        else:
            self.test_suite_config = self.load_yaml_config("config/test_suite.yaml")

        self.subtest_mapping = self.load_yaml_config("config/subtest_mapping.yaml")
        self.suite_config = self.test_suite_config.get("items", {}).get(suite_name, {})
        logger.info(
            f"[Suite] {suite_name} parameter={self.suite_config.get('parameter')}"
        )

    def _load_yaml_file(self, path: Path) -> dict:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def load_yaml_config(self, config_path):
        """
        智能加载YAML配置文件 - 同时兼容开发环境和 PyInstaller 打包环境

        config_path 参数示例：
            "config/test_suite.yaml"
            "config/subtest_mapping.yaml"
        """
        try:
            # 判断是否为打包环境
            if getattr(sys, 'frozen', False):
                # 打包后路径：_internal/config/xxx.yaml
                base_path = Path(sys.executable).parent / "_internal"
                full_path = base_path / config_path
                logger.info(f"[打包环境] 尝试加载配置文件: {full_path}")
            else:
                # 开发环境路径
                base_path = Path(__file__).parent.parent
                full_path = base_path / config_path
                logger.info(f"[开发环境] 尝试加载配置文件: {full_path}")

            if not full_path.exists():
                logger.error(f"配置文件不存在: {full_path}")
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"配置文件加载成功: {full_path.name}")
                return config

        except Exception as e:
            logger.error(f"加载配置文件失败 {config_path}: {str(e)}")
            return {}

    def execute_sub_items(self):
        """根据subItems配置执行子测试项"""
        if not hasattr(self, 'suite_config') or not self.suite_config.get('enabled', True):
            logger.info(f"测试套件 '{getattr(self, 'suite_name', 'unknown')}' 未启用")
            return

        # 获取配置的子测试项名称列表
        sub_item_names = self.suite_config.get('subItems', [])

        # 如果没有子测试项，直接返回
        if not sub_item_names:
            logger.info("没有配置子测试项，跳过执行")
            return

        # 遍历所有配置的子测试项名称
        for sub_item_name in sub_item_names:
            try:
                # 根据名称查找映射配置
                if sub_item_name in self.subtest_mapping.get('subtest_mapping', {}):
                    sub_item_config = self.subtest_mapping['subtest_mapping'][sub_item_name]
                    # 如果在subItems中配置了，就默认启用（除非映射配置中明确禁用）
                    is_enabled = sub_item_config.get('enabled', True)
                    if is_enabled:
                        self.execute_single_sub_item(sub_item_config)
                    else:
                        logger.info(f"子测试项 '{sub_item_name}' 已禁用，跳过执行")
                else:
                    logger.info(f"未找到子测试项 '{sub_item_name}' 的映射配置")
            except Exception as e:
                logger.info(f"执行子测试项 '{sub_item_name}' 失败: {e}")

    def execute_single_sub_item(self, sub_item_config):
        """执行单个子测试项"""
        module_path = sub_item_config.get('module')
        class_name = sub_item_config.get('class')
        method_name = sub_item_config.get('method')

        if not all([module_path, class_name, method_name]):
            logger.info(f"子测试项配置不完整: {sub_item_config}")
            return

        # 动态导入模块
        module = importlib.import_module(module_path)
        # 获取类
        cls = getattr(module, class_name)
        # 创建实例
        instance = cls()

        # 如果实例有manual_setup方法，调用它并传递driver
        if hasattr(instance, 'manual_setup') and hasattr(self, 'driver'):
            instance.manual_setup(self.driver)

        # 执行方法
        method = getattr(instance, method_name)
        method()  # 调用普通方法，而不是pytest测试方法
        logger.info(f"成功执行子测试项: {class_name}.{method_name}")

    def execute_with_timing_control(self, test_func, timeout_ms=None, before_wait_ms=None, after_wait_ms=None):
        """
        通用的测试执行方法，包含超时控制和等待时间控制

        Args:
            test_func: 要执行的测试函数
            timeout_ms: 超时时间(毫秒)，None表示使用配置中的默认值
            before_wait_ms: 执行前等待时间(毫秒)，None表示使用配置中的默认值
            after_wait_ms: 执行后等待时间(毫秒)，None表示使用配置中的默认值
        """
        # 确保配置已初始化
        if not hasattr(self, 'suite_config'):
            logger.info("警告: 测试套件未初始化")
            return

        # 获取配置值
        if timeout_ms is None:
            timeout_ms = self.suite_config.get('timeout', 30000)
        if before_wait_ms is None:
            before_wait_ms = self.suite_config.get('before_wait', 0)
        if after_wait_ms is None:
            after_wait_ms = self.suite_config.get('after_wait', 0)

        # 执行前等待
        if before_wait_ms > 0:
            logger.info(f"执行前等待 {before_wait_ms} 毫秒")
            time.sleep(before_wait_ms / 1000.0)

        # 超时控制执行测试
        result = None
        try:
            if timeout_ms > 0:
                # 使用线程实现超时控制
                result = self._execute_with_timeout(test_func, timeout_ms)
            else:
                result = test_func()
        except TimeoutError:
            logger.info(f"测试执行超时 ({timeout_ms} 毫秒)")
            raise
        except Exception as e:
            test_func_name = test_func.__name__
            if self._handle_crash_exception(e, test_func_name):
                raise pytest.fail(f"测试用例 '{test_func_name}' 执行过程发生闪退")
            else:
                logger.info(f"测试用例 '{test_func_name}' 执行失败: {e}")
                raise

        # 执行后等待
        if after_wait_ms > 0:
            logger.info(f"执行后等待 {after_wait_ms} 毫秒")
            time.sleep(after_wait_ms / 1000.0)

        return result

    def _execute_with_timeout(self, test_func, timeout_ms):
        """使用线程执行函数并控制超时"""
        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = test_func()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout_ms / 1000.0)

        if thread.is_alive():
            # 线程仍在运行，说明超时了
            raise TimeoutError(f"测试执行超时 ({timeout_ms} 毫秒)")

        if exception[0]:
            raise exception[0]

        return result[0]

    def is_enabled(self):
        """检查测试套件是否启用"""
        if not hasattr(self, 'suite_config'):
            return False
        return self.suite_config.get('enabled', True)

    def get_parameter(self, param_name, default=None):
        """获取测试参数"""
        if not hasattr(self, 'suite_config'):
            return default
        parameters = self.suite_config.get('parameter', {})
        return parameters.get(param_name, default)

    # 处理闪退异常
    def _handle_crash_exception(self, e, test_func_name):
        """
        处理闪退异常的方法
        :param e: 捕获的异常
        :param test_func_name: 测试
        :return:
        """
        try:
            # 检查是否为闪退
            if CrashMonitor.is_app_crashed(e):
                crash_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._log_crash_details(test_func_name, crash_time, e)

                # 截图
                self._save_crash_screenshot(test_func_name,crash_time)
                return True
            return False
        except Exception as e:
            logger.error(f"处理闪退异常时发生错误: {e}")
            return False



    def _log_crash_details(self, test_func_name, crash_time, exception):

        """
        记录闪退详情的方法
        :param crash_time: 闪退时间
        :param test_func_name: 测试函数名称
        :return:
        """
        logger.info(f"====== 用例[{test_func_name}]在{crash_time}发生闪退 ======")
        logger.error(traceback.format_exc())
        if hasattr(self, 'driver'):
            with allure.step(f"用例[{test_func_name}]在{crash_time}发生闪退"):
                allure.attach(str(exception), name="闪退异常详情", attachment_type=allure.attachment_type.TEXT)



    def _save_crash_screenshot(self, test_func_name, crash_time):
        """保存闪退时的截图"""
        try:
            if hasattr(self, 'driver'):
                screenshot_name = f"crash_{test_func_name}_{crash_time.replace(':', '-')}"
                self.driver.save_screenshot(f"reports/screenshots/{screenshot_name}.png")
                logger.info(f"闪退截图已保存: {screenshot_name}.png")
                # 添加到Allure报告
                with open(f"reports/screenshots/{screenshot_name}.png", "rb") as f:
                    allure.attach(f.read(), name=screenshot_name, attachment_type=allure.attachment_type.PNG)
        except Exception as e:
            logger.warning(f"保存闪退截图失败: {str(e)}")
