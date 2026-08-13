@echo off
setlocal

cd /d "%~dp0"

:: Проверяем, есть ли системный Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [Echo] Python not found. Please install Python 3.11.
    pause
    exit /b 1
)

if not exist "%~dp0main.py" (
    echo [Echo] main.py not found in %~dp0
    pause
    exit /b 1
)

:: Указываем путь к библиотекам
set "PYTHONPATH=%~dp0echo_core\libs;%PYTHONPATH%"
set "PYTHONDONTWRITEBYTECODE=1"

:: Очистка старого Language Kernel
echo [Echo] Очистка старого Language Kernel...
python -c "import sqlite3; conn=sqlite3.connect('unified_memory_v14.db'); conn.execute(\"DELETE FROM graph_nodes WHERE provenance_source='tabula_rasa_language'\"); conn.execute(\"DELETE FROM graph_edges WHERE provenance_source='tabula_rasa_language'\"); conn.commit(); print('Language Kernel очищен')"

echo [Echo] Starting from source code...
python "%~dp0main.py"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [Echo] Finished with error code %EXIT_CODE%.
    pause
)

endlocal
exit /b %EXIT_CODE%