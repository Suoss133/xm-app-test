# scheduler/runner.py
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Callable, Optional

import yaml

from utils.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_runtime_suite_yaml(
    suite: str,
    device_udid: str,
    params: dict,
    current_app: Optional[str] = None,
) -> Path:
    base_suite_path = PROJECT_ROOT / "config" / "test_suite.yaml"
    with open(base_suite_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    items = data.get("items", {})
    for name, cfg in items.items():
        cfg["enabled"] = False

    if suite not in items:
        raise ValueError(f"未知 suite: {suite}")

    items[suite]["enabled"] = True
    items[suite]["device_udid"] = device_udid
    if current_app:
        items[suite]["current_app"] = current_app

    items[suite].setdefault("parameter", {})
    items[suite]["parameter"].update(params or {})

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
        dir=str(PROJECT_ROOT / "config"),
    )
    yaml.safe_dump({"items": items}, tmp, allow_unicode=True, sort_keys=False)
    tmp.close()
    return Path(tmp.name)


def resolve_allure_cmd() -> Optional[list]:
    """定位项目内 allure 可执行文件"""
    candidates = [
        PROJECT_ROOT / "allure" / "bin" / "allure.bat",
        PROJECT_ROOT / "allure" / "bin" / "allure",
        PROJECT_ROOT / "allure.bat",
        PROJECT_ROOT / "allure" / "allure.bat",
    ]
    for p in candidates:
        if p.exists():
            return [str(p)]
    # 系统 PATH
    which = shutil.which("allure")
    if which:
        return [which]
    return None


def generate_allure_report(results_dir: Path, report_dir: Path, log_callback=None) -> bool:
    def _out(msg: str):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    cmd_base = resolve_allure_cmd()
    if not cmd_base:
        _out("[Allure] 未找到 allure 可执行文件，请确认已放到项目根目录 allure/bin/")
        return False

    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    cmd = cmd_base + [
        "generate",
        str(results_dir),
        "-o",
        str(report_dir),
        "--clean",
    ]
    _out(f"[Allure] 生成报告: {' '.join(cmd)}")
    try:
        r = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if r.stdout:
            _out(r.stdout.strip())
        if r.returncode != 0:
            _out(f"[Allure] 生成失败 exit={r.returncode} stderr={r.stderr}")
            return False
        index = report_dir / "index.html"
        _out(f"[Allure] 报告已生成: {index}")

        # allure open 起本地服务
        try:
             open_cmd = cmd_base + ["open", str(report_dir)]
             subprocess.Popen(
                open_cmd,
                 cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL,
             )
             _out(f"[Allure] 已启动 allure open: {report_dir}")

        except Exception as e:
             _out(f"[Allure] allure open 失败: {e}")
        return True
    except Exception as e:
        _out(f"[Allure] 生成异常: {e}")
        return False


def run_pytest_job(
    suite: str,
    device_udid: str,
    params: dict,
    current_app=None,
    log_callback=None,
    stop_flag=None,
    job_id: str = None,
) -> int:
    def _out(msg: str):
        logger.info(msg)
        if log_callback:
            try:
                log_callback(msg)
            except Exception as e:
                logger.error(f"log_callback 失败: {e}")

    runtime_yaml = build_runtime_suite_yaml(suite, device_udid, params, current_app)
    _out(f"[Runner] params={params}")
    _out(f"[Runner] TEST_SUITE_YAML={runtime_yaml}")

    suite_to_path = {
        "binding": "tests/bin_ding/test_binding.py",
        "BluetoothBinding": "tests/bin_ding/test_binding.py",
        "LiveImageUniversal": "tests/live_image/test_LiveImageUniversal.py",
        "KoocamSlidingEvent": "tests/event/test_KoocamSlidingEvent.py",
        "event_video_play": "tests/event/test_event_video_play.py",
        "9811_event_video_play": "tests/event/test_event_video_play.py",
    }
    test_path = suite_to_path.get(suite) or f"tests/{suite}"
    full_test_path = PROJECT_ROOT / test_path
    if not full_test_path.exists():
        _out(f"[Runner] 测试文件不存在: {full_test_path}")
        return 2

    # 每个 job 独立 allure-results，避免并行互相覆盖
    job_key = job_id or "default"
    allure_results = PROJECT_ROOT / "reports" / "allure-results" / job_key
    allure_report = PROJECT_ROOT / "reports" / "allure-report" / job_key
    allure_results.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["ANDROID_SERIAL"] = device_udid
    env["TEST_SUITE_YAML"] = str(runtime_yaml)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    app = current_app
    if not app:
        try:
            with open(runtime_yaml, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for _n, cfg in (data.get("items") or {}).items():
                if cfg.get("enabled"):
                    app = cfg.get("current_app")
                    break
        except Exception:
            pass
    if app:
        env["CURRENT_APP"] = str(app)
        _out(f"[Runner] CURRENT_APP={app}")

    cmd = [
        sys.executable, "-u", "-m", "pytest",
        str(test_path),
        "-v", "--tb=short", "-s",
        f"--alluredir={allure_results}",
    ]
    _out(f"[Runner] cmd={' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if stop_flag and stop_flag():
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                _out("[Runner] 收到停止信号，已终止进程")
                return -1
            _out(line.rstrip("\n\r"))
        code = proc.wait()
        _out(f"[Runner] pytest 结束 exit_code={code}")

        # 用例结束后生成 Allure HTML
        generate_allure_report(allure_results, allure_report, log_callback=_out)
        return code
    finally:
        try:
            runtime_yaml.unlink(missing_ok=True)
        except Exception:
            pass