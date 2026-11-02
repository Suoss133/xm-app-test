# core/page_factory.py
def create_pages(app_name: str):
    """
    Returns
    -------
    dict: {
        "HomePage": cls,
        "AddDevicePage": cls,
        "SettingsDevicePage": cls,
        "VideoDetailPage": cls,
        "LoginPage": cls,   # 可选
        "EventPage": cls,   # 可选
    }
    """
    app_name = (app_name or "").strip()
    if not app_name:
        raise ValueError("create_pages: app_name 为空")

    if app_name == "Humbirdy":
        from apps.Humbirdy.pages.page_home import HomePage
        from apps.Humbirdy.pages.page_add_device import AddDevicePage
        from apps.Humbirdy.pages.page_settings_device import SettingsDevicePage
        from apps.Humbirdy.pages.page_video_detail import VideoDetailPage
        from apps.Humbirdy.pages.page_login import LoginPage
        EventPage = None
    elif app_name == "Koocam":
        from apps.Koocam.pages.page_home import HomePage
        from apps.Koocam.pages.page_add_device import AddDevicePage
        from apps.Koocam.pages.page_settings_device import SettingsDevicePage
        from apps.Koocam.pages.page_video_detail import VideoDetailPage
        from apps.Koocam.pages.page_login import LoginPage
        try:
            from apps.Koocam.pages.page_event import EventPage
        except ImportError:
            EventPage = None
    elif app_name == "Koobird":
        from apps.Koobird.pages.page_home import HomePage
        from apps.Koobird.pages.page_add_device import AddDevicePage
        from apps.Koobird.pages.page_settings_device import SettingsDevicePage
        from apps.Koobird.pages.page_video_detail import VideoDetailPage
        from apps.Koobird.pages.page_login import LoginPage
        EventPage = None
    elif app_name == "baseus":
        from apps.baseus.pages.page_home import HomePage
        from apps.baseus.pages.page_video_detail import VideoDetailPage
        from apps.baseus.pages.page_login import LoginPage
        # 若 add/settings 复用 Koobird，按你项目实际改
        try:
            from apps.baseus.pages.page_add_device import AddDevicePage
            from apps.baseus.pages.page_settings_device import SettingsDevicePage
        except ImportError:
            from apps.Koobird.pages.page_add_device import AddDevicePage
            from apps.Koobird.pages.page_settings_device import SettingsDevicePage
        EventPage = None
    elif app_name == "SoliomHome":
        from apps.SoliomHome.pages.page_home import HomePage
        from apps.SoliomHome.pages.page_add_device import AddDevicePage
        from apps.SoliomHome.pages.page_settings_device import SettingsDevicePage
        from apps.SoliomHome.pages.page_video_detail import VideoDetailPage
        from apps.SoliomHome.pages.page_login import LoginPage
        EventPage = None
    else:
        raise ValueError(f"不支持的应用类型: {app_name}")

    return {
        "HomePage": HomePage,
        "AddDevicePage": AddDevicePage,
        "SettingsDevicePage": SettingsDevicePage,
        "VideoDetailPage": VideoDetailPage,
        "LoginPage": LoginPage,
        "EventPage": EventPage,
    }