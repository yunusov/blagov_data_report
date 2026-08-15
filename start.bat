@echo off
@chcp 65001 > nul
echo Проверка Python...

rem python --version > nul 2>&1
rem if errorlevel 1 (
rem    echo Ошибка: Python не установлен или не добавлен в PATH
rem    echo Скачайте с https://python.org
rem    pause
rem    exit /b 1
rem )

echo Проверка UV...
rem uv --version > nul 2>&1
rem if errorlevel 1 (
rem    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
rem )

uv run src/main.py