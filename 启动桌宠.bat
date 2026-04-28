@echo off
chcp 65001 >nul
echo ========================================
echo  启动 WorkBuddy 服务 + 桌面宠物
echo ========================================
echo.

REM 启动 codebuddy HTTP 服务（完全分离，不占用当前终端）
echo [1/2] 启动 WorkBuddy 服务...
start "" /min powershell.exe -NoProfile -Command "codebuddy --serve --port 8080"

REM 等待服务就绪
echo [2/2] 等待服务启动（5秒）...
timeout /t 5 /nobreak >nul

REM 启动桌面宠物
echo 启动桌面宠物...
start "" pythonw "E:\index\日常模型\盖亚爷爷桌宠\desktop_pet.pyw"

REM 倒计时10秒后自动关闭终端
echo.
echo 服务已启动，窗口将在 10 秒后自动关闭...
timeout /t 10 /nobreak >nul
exit
