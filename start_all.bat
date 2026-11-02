@echo off
chcp 65001 >nul
set ROOT=%~dp0
cd /d "%ROOT%"

echo ========================================
echo   Appium Platform 一键启动
echo ========================================

echo [1/3] 启动 Appium，日志覆盖写入 appium-server.log
start "Appium" cmd /k "cd /d "%ROOT%" && appium --allow-insecure uiautomator2:chromedriver_autodownload --log appium-server.log --log-no-colors --log-timestamp"

timeout /t 3 /nobreak >nul

echo [2/3] 启动 FastAPI...
if exist "%ROOT%.venv\Scripts\activate.bat" (
  start "FastAPI" cmd /k "cd /d "%ROOT%" && call .venv\Scripts\activate.bat && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
) else (
  start "FastAPI" cmd /k "cd /d "%ROOT%" && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
)

timeout /t 2 /nobreak >nul

echo [3/3] 启动前端...
start "Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo Appium 日志: %ROOT%appium-server.log
echo FastAPI:     http://127.0.0.1:8000
echo Frontend:    http://localhost:5173
pause