@echo off
echo ========================================
echo Установка окружения Echo AGI v16.1
echo ========================================

:: 1. Создание виртуального окружения
echo [1/4] Создание виртуального окружения...
python -m venv echo_env

:: 2. Активация и установка зависимостей
echo [2/4] Установка зависимостей...
call echo_env\Scripts\activate
pip install -r requirements.txt

:: 3. Миграция базы данных
echo [3/4] Миграция базы данных...
python migrate_schema.py

:: 4. Готово
echo [4/4] Настройка завершена!
echo.
echo Для запуска Echo выполните:
echo   echo_env\Scripts\activate
echo   python main.py
pause