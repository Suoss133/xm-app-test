# utils/excel_reporter.py
import os
import pandas as pd
from datetime import datetime
from utils.logger import logger


class ExcelReporter:
    def __init__(self, report_dir='reports'):
        """初始化Excel报告生成器"""
        self.base_report_dir = report_dir
        if not os.path.exists(self.base_report_dir):
            os.makedirs(self.base_report_dir)

        # 任务管理
        self._task_file_map = {}  # 存储每个用例的当前任务文件

    def start_new_task(self, suite_name, task_name=None):
        """
        开始一个新的压测任务
        suite_name: 套件名称，用于区分不同用例
        task_name: 可选，自定义任务名称
        """
        if task_name:
            file_name = f"{task_name}.xlsx"
        else:
            # 使用套件名 + 时间戳
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"{suite_name}_{timestamp}.xlsx"

        self._task_file_map[suite_name] = file_name
        logger.info(f"📊 [{suite_name}] 新任务已启动: {file_name}")
        return file_name

    def get_task_file(self, suite_name):
        """获取当前任务的文件名"""
        return self._task_file_map.get(suite_name)

    def append_to_report(self, test_data, filename=None):
        """
        将测试数据追加到报告中
        如果 filename 为 None，则使用任务管理的文件名
        """
        try:
            # 确定文件名
            if filename is None:
                # 从调用栈获取 suite_name
                suite_name = self._get_suite_name_from_stack()
                if suite_name and suite_name in self._task_file_map:
                    filename = self._task_file_map[suite_name]
                else:
                    # 没有任务，使用默认名称
                    filename = "report.xlsx"

            # 确保有 .xlsx 后缀
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            file_path = os.path.join(self.base_report_dir, filename)

            # 如果文件不存在，创建新文件
            if not os.path.exists(file_path):
                df = pd.DataFrame([test_data] if isinstance(test_data, dict) else test_data)
                df.to_excel(file_path, index=False, engine='openpyxl')
                logger.info(f"✅ 创建报告：{file_path}")
                return file_path

            # 追加数据
            existing_df = pd.read_excel(file_path, engine="openpyxl")
            new_df = pd.DataFrame([test_data] if isinstance(test_data, dict) else test_data)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df.to_excel(file_path, index=False, engine='openpyxl')
            logger.debug(f"✅ 数据已追加：{file_path} (当前 {len(combined_df)} 条)")
            return file_path

        except Exception as e:
            logger.error(f"追加数据失败：{e}")
            raise

    def _get_suite_name_from_stack(self):
        """从调用栈中获取测试套件名称"""
        import inspect
        try:
            # 向上查找调用栈，找到测试类
            for frame_info in inspect.stack():
                if 'self' in frame_info.frame.f_locals:
                    obj = frame_info.frame.f_locals.get('self')
                    if obj and hasattr(obj, 'SUITE_NAME'):
                        return obj.SUITE_NAME
                    # 也检查类名
                    if hasattr(obj, '__class__'):
                        class_name = obj.__class__.__name__
                        if class_name.startswith('Test'):
                            # 尝试从类名提取
                            return class_name.replace('Test', '')
        except:
            pass
        return None


excel_reporter = ExcelReporter()