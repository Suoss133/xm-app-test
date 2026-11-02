# utils/test_config.py
import yaml
import os
import sys
from pathlib import Path
from utils.logger import logger


class TestConfigManager:
    # 关键：阻止 pytest 尝试收集这个类
    __test__ = False

    _instance = None
    _config = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load_config()
        return cls._instance

    def __init__(self):
        if getattr(__import__("sys"), "frozen", False):
            self.root = Path(__import__("sys").executable).parent / "_internal"
        else:
            self.root = Path(__file__).resolve().parent.parent
        self.suite_yaml_path = self.root / "config" / "test_suite.yaml"

    @classmethod
    def _load_config(cls):
        try:
            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent / "_internal"
            else:
                base_path = Path(__file__).parent.parent

            config_path = base_path / "config" / "test_suite.yaml"

            if not config_path.exists():
                logger.error(f"配置文件不存在: {config_path.absolute()}")
                cls._config = {"items": {}}
                return

            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = yaml.safe_load(f)

            logger.info(f"配置加载成功，路径: {config_path}")
        except Exception as e:
            logger.error(f"配置加载异常: {e}")
            cls._config = {"items": {}}

    def get_test_items(self):
        return self._config.get("items", {}) if self._config else {}


    def get_enabled_suite_name(self):
        """获取当前启用的测试项名称（优先运行时 yaml）"""
        data = self._load_suite_yaml()
        items = data.get("items") or {}
        enabled = [name for name, cfg in items.items() if cfg.get("enabled", False)]
        return enabled[0] if enabled else None

    def _load_suite_yaml(self) -> dict:
        runtime = os.environ.get("TEST_SUITE_YAML")
        if runtime and Path(runtime).exists():
            path = Path(runtime)
            logger.info(f"[TestConfig] 使用运行时配置: {path}")
        else:
            path = self.suite_yaml_path
            # 单例 __init__ 可能尚未执行，兜底
            if not hasattr(self, "suite_yaml_path") or self.suite_yaml_path is None:
                if getattr(sys, "frozen", False):
                    root = Path(sys.executable).parent / "_internal"
                else:
                    root = Path(__file__).resolve().parent.parent
                path = root / "config" / "test_suite.yaml"

        if not path.exists():
            logger.warning(f"suite yaml 不存在: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_current_app(self) -> str:
        # 1. 环境变量最高优先级
        env_app = os.environ.get("CURRENT_APP")
        if env_app:
            return env_app.strip()

        # 2. 运行时 / 默认 suite yaml 中第一个 enabled
        data = self._load_suite_yaml()
        for name, cfg in (data.get("items") or {}).items():
            if cfg.get("enabled"):
                app = (cfg.get("current_app") or "").strip()
                if app:
                    return app
        return ""

    def get_suite_parameter(self, key, default=None):
        """读参数：优先 TEST_SUITE_YAML 里 enabled 套件的 parameter"""
        data = self._load_suite_yaml()
        items = data.get("items") or {}

        suite_name = self.get_enabled_suite_name()
        if suite_name and suite_name in items:
            return items[suite_name].get("parameter", {}).get(key, default)

        # 兜底：任意 enabled
        for name, cfg in items.items():
            if cfg.get("enabled"):
                return (cfg.get("parameter") or {}).get(key, default)
        return default

    def get_enabled_suite(self) -> dict:
        """返回第一个 enabled 套件 {name, config}"""
        data = self._load_suite_yaml()
        for name, cfg in (data.get("items") or {}).items():
            if cfg.get("enabled"):
                return {"name": name, "config": cfg}
        return {}

    def get_repeat_count(self, item_name, default_count=1):
        """
        获取指定套件执行次数。
        必须读 _load_suite_yaml()，这样调度器注入的 test_count 才会生效。
        """
        try:
            data = self._load_suite_yaml()
            items = data.get("items") or {}
            if not items:
                logger.warning("[TestConfig] suite yaml 无 items，使用 default_count")
                return default_count

            suite_config = items.get(item_name)
            if not suite_config:
                for suite_name, config in items.items():
                    if suite_name.lower() == str(item_name).lower():
                        suite_config = config
                        break

            # 仍找不到：用当前 enabled 项（运行时通常只有一个）
            if not suite_config:
                for suite_name, config in items.items():
                    if config.get("enabled"):
                        suite_config = config
                        logger.info(
                            f"[TestConfig] item_name={item_name} 未精确匹配，"
                            f"使用 enabled 套件: {suite_name}"
                        )
                        break

            if not suite_config:
                return default_count

            parameter_config = suite_config.get("parameter") or {}
            param_repeat_count = parameter_config.get("test_count")
            if param_repeat_count is not None:
                count = max(1, int(param_repeat_count))
                logger.info(
                    f"[TestConfig] suite={item_name} test_count={count} "
                    f"(yaml={self._suite_yaml_path_for_log()})"
                )
                return count

            main_repeat_count = suite_config.get("test_count")
            if main_repeat_count is not None:
                return max(1, int(main_repeat_count))

            return default_count

        except Exception as e:
            logger.error(f"获取测试项执行次数失败: {e}")
            return default_count

    def _suite_yaml_path_for_log(self) -> str:
        runtime = os.environ.get("TEST_SUITE_YAML")
        if runtime and Path(runtime).exists():
            return runtime
        return str(self.suite_yaml_path)

# 导出单例
test_config = TestConfigManager()