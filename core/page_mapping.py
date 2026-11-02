# core/page_mapping.py
from pages.login_page import LoginEmailPage


class PageMappingManager:
    """全局页面映射管理器（单例模式）"""
    _instance = None
    _page_mapping = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 初始化所有页面映射
            cls._page_mapping = {
                "login": LoginEmailPage,
            }
        return cls._instance

    def get_page(self, page_name):
        """根据页面名称获取对应的Page实例"""
        page = self._page_mapping.get(page_name)
        if not page:
            raise ValueError(f"未找到页面映射: {page_name}，请在PageMappingManager中添加")
        return page