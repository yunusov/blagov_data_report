@echo off
@chcp 65001 > nul
echo Старт форматирования и проверок ruff
uv run ruff format src
uv run ruff check --fix src
