# utils/logger.py
import logging
import sys


def _setup():
    logger = logging.getLogger("appium_platform")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    # ===== 修改格式：添加毫秒、文件名、行号 =====
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logger.addHandler(handler)
    return logger


logger = _setup()