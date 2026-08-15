@echo off
@chcp 65001 > nul
echo Старт форматирования и проверок ruff
uv run ruff format src test
uv run ruff check --fix src test
