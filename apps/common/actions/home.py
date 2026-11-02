from .common import get_page_instance, log_step, handle_error


# 点击添加设备按钮
def click_add_device_button(app_name):
    """
    首页点击添加设备按钮
    :param app_name:
    :return:
    """
    try:
        home = get_page_instance(app_name, "page_home", "HomePage")
        home.click_add_device_button()
        log_step(f"{app_name} 点击添加设备按钮")
    except Exception as e:
        handle_error(f"{app_name} 点击添加设备按钮失败: {str(e)}")

# 点击指定设备的设置按钮
def click_setting_button(app_name, device_title):
    """
    点击指定设备的直播按钮
    :param app_name: App名称
    :param device_title: 设备名称
    """
    try:
        home = get_page_instance(app_name, "page_home", "HomePage")
        home.click_live_button(device_title)
        log_step(f"{app_name} 点击设备 {device_title} 的设置按钮")
    except AttributeError as e:
        handle_error(f"{app_name} 的HomePage 缺少 click_setting_button 方法")
    except Exception as e:
        handle_error(f"{app_name} 点击设备 {device_title} 的设置按钮失败: {str(e)}")


# 返回上一页
def back_to_home(app_name):
    """
    返回上一页
    :param app_name:
    :return:
    """
    try:
        home = get_page_instance(app_name, "page_home", "HomePage")
        home.back()
        log_step(f"{app_name} 返回上一页")
    except Exception as e:
        handle_error(f"{app_name} 返回上一页失败: {str(e)}")