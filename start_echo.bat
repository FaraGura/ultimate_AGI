@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0echo_env\Scripts\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%PYTHON_EXE%" (
    echo [Echo] Python environment not found: %PYTHON_EXE%
    echo [Echo] Run setup_echo.bat first, or restore the echo_env folder.
    pause
    exit /b 1
)

if not exist "%~dp0main.py" (
    echo [Echo] main.py not found in %~dp0
    pause
    exit /b 1
)

:: Очистка только старого Language Kernel (знания графа больше не удаляются)
echo [Echo] Очистка старого Language Kernel...
"%PYTHON_EXE%" -c "import sqlite3; conn=sqlite3.connect('unified_memory_v14.db'); conn.execute(\"DELETE FROM graph_nodes WHERE provenance_source='tabula_rasa_language'\"); conn.execute(\"DELETE FROM graph_edges WHERE provenance_source='tabula_rasa_language'\"); conn.commit(); print('Language Kernel очищен')"

echo [Echo] Starting from source code...
"%PYTHON_EXE%" "%~dp0main.py"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [Echo] Finished with error code %EXIT_CODE%.
    pause
)

endlocal
exit /b %EXIT_CODE%