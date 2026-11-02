# flows/bluetooth_binding/flow.py
from utils.logger import logger
from .steps import (
    step_click_add_button,
    step_select_bluetooth_device,
    step_select_wifi,
    step_wait_binding_result,
    step_back_to_home,
    step_enter_device_setting,
    step_wait_and_delete_device,
)
from apps.common.actions.common import handle_error
from utils.excel_reporter import excel_reporter
import time


class FatalDeletionError(Exception):
    """删除失败 → 需要终止整个压测"""
    pass


def bluetooth_binding_full_flow(context):
    """
    执行一轮完整的蓝牙绑定 + 删除流程
    1~4 步失败只标记当前轮失败
    删除失败抛出 FatalDeletionError 让上层终止
    """
    start_time = time.time()
    row = {
        "轮次": context.get("current_round", 1),
        "开始时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "状态": "FAIL",
        "错误": "",
        "配网成功": False,
        "耗时(秒)": 0,
    }

    try:
        # 前置步骤（允许失败）
        for step in [
            step_click_add_button,
            step_select_bluetooth_device,
            step_select_wifi,
        ]:
            try:
                step(context)
            except Exception as e:
                row["错误"] += f"{step.__name__} 失败: {str(e)}; "
                logger.warning(f"步骤 {step.__name__} 失败，继续执行后续")

        # 等待配网结果（关键判断点）
        success = step_wait_binding_result(context)
        row["配网成功"] = success

        # 返回首页
        step_back_to_home(context)

        # 进入设置 & 删除（不允许失败）
        step_enter_device_setting(context)
        step_wait_and_delete_device(context)

        row["状态"] = "PASS"
        row["错误"] = "无"

    except FatalDeletionError as e:
        row["错误"] = str(e)
        row["状态"] = "FATAL_DELETE"
        raise  # 抛给上层终止

    except Exception as e:
        row["错误"] += f"其他异常: {str(e)}; "

    finally:
        row["耗时(秒)"] = f"{time.time() - start_time:.2f}"
        excel_reporter.append_to_report(row, "bluetooth_binding_results.xlsx")

    return row["状态"] == "PASS"