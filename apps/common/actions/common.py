import time
import importlib
from utils.logger import logger
import allure
from core.driver import DriverManager

# 动态加载当前App页面
def get_page_instance(app_name, page_model_name, class_name: str = "Page"):
    """

    :param app_name:  App名称
    :param page_model_name: 页面模块
    :param class_name: 类名
    :return:
    """

    module_path = f"apps.{app_name}.pages.{page_model_name}"

    try:
        module = importlib.import_module(module_path)
        PageClass = getattr(module, class_name)
        instance = PageClass()
        logger.debug(f"成功加载: {app_name}.{page_model_name}.{class_name}")
        return instance
    except (ImportError, AttributeError) as e:
        logger.error(f"加载页面失败 {app_name}.{page_model_name}.{class_name} -> {e}")
        raise ImportError(f"无法加载 {app_name}的{page_model_name}.{class_name}")


# 截图
def take_screenshot(name):
    """
    截图操作
    :param name: 截图名称
    :return:
    """
    if name is None:
        name = f"screenshot_{int(time.time())}"

    try:
        driver = DriverManager.get_driver()
        path = f"reports/screenshot/{name}.png"
        driver.save_screenshot(path)
        logger.info(f"截图保存成功: {path}")
        with allure.step(f"截图: {name}"):
            allure.attach.file(path, name=name, attachment_type=allure.attachment_type.PNG)
    except Exception as e:
        logger.error(f"截图失败: {e}")


# 日志记录
def log_step(message):
    """
    日志记录
    :param message: 日志信息
    :return:
    """
    logger.info(message)
    with allure.step(message):
        pass

# 异常处理
def handle_error(error, screenshot_name=None):
    """
    异常处理
    :param error:
    :param screenshot_name:
    :return:
    """
    logger.error(error)
    take_screenshot(screenshot_name or f"error_{int(time.time())}")
    raise AssertionError(error)