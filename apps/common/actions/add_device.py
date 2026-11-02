from .common import get_page_instance, handle_error, log_step

# 选择蓝牙设备
def select_bluetooth_device_by_sn(app_name, device_sn):
    """选择指定的蓝牙设备"""
    try:
        add_device = get_page_instance(app_name, "page_add_device", "AddDevicePage")
        add_device.select_device_by_sn(device_sn)
        log_step(f"{app_name} 已选择蓝牙设备{device_sn}")
    except Exception as e:
        handle_error(f"选择蓝牙设备{device_sn}失败 :{e}")


# 选择wifi信息
def select_network(app_name, ssid, password):
    """
    选择wifi信息
    :param app_name: App名称
    :param ssid: wifi名称
    :param password: wifi没密码
    :return:
    """
    try:
        add_device = get_page_instance(app_name, "page_add_device", "AddDevicePage")
        add_device.select_network(ssid, password)
        log_step(f"{app_name} 已选择wifi信息{ssid}")
    except Exception as e:
        handle_error(f"选择wifi信息{ssid}失败 :{e}")

# 检查设备配网状态
def check_network_config_status(app_name, device_sn, timeout=120):
    """
    检查设备配网状态
    :param app_name:
    :param device_sn:
    :param timeout:
    :return:
    """
    try:
        add_device = get_page_instance(app_name, "page_add_device", "AddDevicePage")
        result = add_device.check_network_config_status(device_sn,timeout)
        if result and result.get("text") == "连接成功":
            log_step(f"{app_name} 设备 {device_sn} 配网成功")
            return True
        else:
            log_step(f"{app_name} 设备 {device_sn}配网失败")
            return False
    except Exception as e:
        handle_error(f"检查设备 {device_sn} 配网状态失败 :{e}")
        return False

# 设置设备名称
def set_device_name(app_name, device_name):
    """
    设置设备名称
    :param app_name:
    :param device_name:
    :return:
    """
    try:
        add_device = get_page_instance(app_name, "page_add_device", "AddDevicePage")
        add_device.set_device_name(device_name)
        log_step(f"{app_name} 已成功设置设备名称为：{device_name}")
    except Exception as e:
        handle_error(f"{app_name} 设置设备名称失败 :{e}")

# 自动关闭安装向导
def close_install_guide(app_name):

    try:
        add_device = get_page_instance(app_name, "page_add_device", "AddDevicePage")
        add_device.auto_close_install_guide()
        log_step(f"{app_name} 已成功关闭安装向导")
    except Exception as e:
        log_step(f"{app_name} 不需要处理安装先导")

