from apps.base.base_personal_center_page import BasePersonalCenterPage


class PersonalCenterPage(BasePersonalCenterPage):
    def __init__(self):
        super().__init__(
            page_name="个人中心",
            config_path="apps/Koocam/config.yaml",
            page_config_name="personal_center",
            handle_popup=True
        )