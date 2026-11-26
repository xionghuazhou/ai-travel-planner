@echo off
title TravelAI - 停止服务
cd /d "%~dp0"

echo 正在停止 TravelAI 全部服务（数据会保留）...
docker compose down
echo.
echo [OK] 已停止。下次双击「启动助手.bat」即可再次使用。
echo 如需彻底删除数据（数据库+知识库），请手动执行: docker compose down -v
pause
