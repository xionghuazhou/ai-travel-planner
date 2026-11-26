@echo off
title TravelAI - 实时日志
cd /d "%~dp0"

echo 正在显示服务实时日志（按 Ctrl+C 退出，不影响服务运行）...
echo.
docker compose logs -f --tail=80
pause
