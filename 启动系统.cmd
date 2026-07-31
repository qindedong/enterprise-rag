@echo off
REM ============================================================
REM 企业知识库 RAG — 双击启动（开发模式）
REM 等同于运行: powershell -File start-dev.ps1
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" %*
pause
