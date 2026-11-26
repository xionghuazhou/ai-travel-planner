@echo off
title TravelAI 智能旅行规划助手 - 启动器
cd /d "%~dp0"

echo ================================================
echo    TravelAI 智能旅行规划助手 - 一键启动
echo ================================================
echo.

rem ---------- 检查 Docker ----------
docker info >nul 2>&1
if %errorlevel% equ 0 goto docker_ready

echo [提示] Docker 未运行，正在尝试启动 Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else if exist "D:\Docker\DockerDesktop\Docker Desktop.exe" (
    start "" "D:\Docker\DockerDesktop\Docker Desktop.exe"
) else (
    start "" "Docker Desktop"
)
echo 等待 Docker 启动（最多 2 分钟）...
set /a wcount=0
:waitdocker
timeout /t 6 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% equ 0 goto docker_ready
set /a wcount+=1
if %wcount% lss 20 goto waitdocker
echo [错误] Docker 未能自动启动。请手动打开 Docker Desktop，等它完全启动后重新双击本脚本。
pause
exit /b 1

:docker_ready
echo [OK] Docker 已就绪
echo.
echo 正在启动全部服务（首次运行会自动构建，约 5-10 分钟，请耐心等待）...
docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo [错误] 服务启动失败，请查看上方错误信息（常见原因：端口被占用、Docker 未联网）。
    pause
    exit /b 1
)
echo.

echo 正在等待后端服务就绪（首次启动需要导入景点知识库）...
set /a tries=0
:waitbackend
curl -s -o nul -m 3 http://localhost:8000/health
if %errorlevel% equ 0 goto backend_ok
set /a tries+=1
if %tries% lss 40 goto waitbackend
echo [警告] 后端 2 分钟内未就绪，仍将打开页面（可稍后手动刷新）。
goto open_page

:backend_ok
echo [OK] 后端服务已就绪

:open_page
echo.
echo ================================================
echo    [OK] TravelAI 已启动！
echo.
echo    前端页面 : http://localhost:5173
echo    后端接口 : http://localhost:8000/docs
echo    停止服务 : 双击「停止助手.bat」
echo ================================================
echo.
start http://localhost:5173
echo 浏览器已打开，按任意键关闭本窗口（关闭窗口不影响服务运行）。
pause >nul
