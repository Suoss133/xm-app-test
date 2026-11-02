# core/yaml_utils.py
import logging
import sys
from pathlib import Path

import yaml
import os
from appium.webdriver.common.appiumby import AppiumBy


class YamlUtils:
    @staticmethod
    def get_resource_path(relative_path):
        """获取资源的绝对路径，适配开发和打包环境"""
        if getattr(sys, 'frozen', False):
            # 打包后：路径在 .exe 同级的 _internal 文件夹内
            base_path = Path(sys.executable).parent / "_internal"
        else:
            # 开发环境：路径在项目根目录
            base_path = Path(__file__).parent.parent

        return base_path / relative_path

    @staticmethod
    def read_yaml_file(file_path):
        """读取YAML文件内容"""

        actual_path = YamlUtils.get_resource_path(file_path)

        if not os.path.exists(actual_path):
            raise FileNotFoundError(f"文件不存在: {actual_path}")

        with open(actual_path, 'r', encoding='utf-8') as f:
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as e:
                logging.error(f"YAML文件解析错误: {e}")
                raise Exception(f"解析YAML文件出错: {e}")

    @staticmethod
    def get_element_locator(file_path, page_name):
        """
        获取元素定位信息
        :param file_path: YAML配置文件路径
        :param page_name: 页面名称
        :return: 元素定位信息字典
        """
        config = YamlUtils.read_yaml_file(file_path)

        if "pages" not in config:
            logging.error("配置文件中缺少 'pages' 节点")
            raise KeyError("配置文件中缺少 'pages' 节点")

        if page_name not in config["pages"]:
            logging.error(f"页面 '{page_name}' 在配置文件中不存在")
            raise KeyError(f"页面 '{page_name}' 在配置文件中不存在")

        return config["pages"][page_name]

    @staticmethod
    def parse_locator(locator_string):
        """
        解析定位符字符串为Appium定位符元组
        :param locator_string: 定位符字符串
        :return: 定位符元组
        """
        # 创建包含AppiumBy的命名空间
        namespace = {'AppiumBy': AppiumBy}
        return eval(locator_string, namespace)

    @staticmethod
    def parse_dynamic_locator(locator_string, *args):
        """
        解析动态定位符字符串，支持格式化参数
        :param locator_string: 包含占位符的定位符字符串
        :param args: 格式化参数
        :return: 定位符元组
        """
        # 先格式化字符串，再解析为定位符元组
        formatted_locator = locator_string.format(*args)
        return YamlUtils.parse_locator(formatted_locator)
