# \tests\test_LoginEmail.py
import os

import allure
import pytest
import yaml

from core.base_test_suite import BaseTestSuite
from utils.test_config import test_config
from core.driver import DriverManager
from utils.logger import logger

from utils.test_config import TestConfigManager

# 直接通过配置管理器获取，确保读取的是 test_suite.yaml 里 enabled=true 的那一项
current_app = TestConfigManager().get_current_app()
logger.info(f"当前测试执行识别到的 App 为: {current_app}")


if current_app == 'Humbirdy':
    from apps.Humbirdy.pages.page_login import LoginPage
elif current_app == 'Koocam':
    from apps.Koocam.pages.page_login import LoginPage
elif current_app == 'Koobird':
    from apps.Koobird.pages.page_login import LoginPage
elif current_app == 'baseus':
    from apps.baseus.pages.page_login import LoginPage
elif current_app == 'SoliomHome':
    from apps.baseus.pages.page_login import LoginPage
else:
    raise ValueError(f"不支持的应用类型: {current_app}")


@allure.epic("登录测试模块")
@allure.feature("登录测试")
class TestLoginEmail(BaseTestSuite):

    @pytest.fixture(autouse=True)
    def setup(self, reset_app):
        """前置条件"""
        self.initialize_suite("LoginEmail")
        self.driver = reset_app

        self.login_page = LoginPage()

        self.scenarios = self.suite_config.get("parameter", {}).get("scenarios", [])
        self.enable_scenarios = [s for s in self.scenarios if s.get("enabled", False)]


    repeat_count = test_config.get_repeat_count("LoginEmail", 1)

    @pytest.mark.parametrize('iteration', range(repeat_count))
    def test_login_scenarios(self,iteration):

        if not self.enable_scenarios:
            pytest.skip("当前没有启用任何登录场景")

        for idx, scenario in enumerate(self.enable_scenarios):
            scene_name = scenario["name"]
            logger.info(f"执行登录场景: {scene_name}")

            self.login_page.enter_email(scenario["email"])
            self.login_page.enter_password(scenario["password"])
            self.login_page.check_remember_password()
            self.login_page.check_user_agree()
            self.login_page.click_login_button()









