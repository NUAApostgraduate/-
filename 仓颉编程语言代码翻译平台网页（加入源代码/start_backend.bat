@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

set "WEB_DIR=%~dp0"
for %%I in ("%WEB_DIR%..\translator-repo") do set "TRANSLATOR_REPO=%%~fI"

rem Do not silently start a second backend that cannot bind the API port.
set "BACKEND_PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:":8765" ^| findstr /C:"LISTENING"') do set "BACKEND_PORT_PID=%%P"
if "!BACKEND_PORT_PID!"=="" goto port_check_done
curl.exe --silent --show-error --fail --max-time 5 http://127.0.0.1:8765/health >nul 2>&1
if errorlevel 1 goto port_check_failed
curl.exe --silent --show-error --fail --max-time 5 http://127.0.0.1:8765/health | findstr /C:"project_whole_supported" >nul
if errorlevel 1 goto port_check_stale
echo Backend is already healthy on port 8765 (PID !BACKEND_PORT_PID!).
echo Web UI: http://127.0.0.1:8765/
echo API:    http://127.0.0.1:8765/translate
echo Reusing the existing backend; no duplicate process was started.
pause
exit /b 0

:port_check_stale
echo Port 8765 is occupied by an older backend (PID !BACKEND_PORT_PID!) without whole-project translation.
echo Stop that process, then run this file again to load the updated backend.
pause
exit /b 1

:port_check_failed
echo Port 8765 is occupied by PID !BACKEND_PORT_PID!, but its health check failed.
echo Close that process, then run this file again. No request was sent to an unhealthy backend.
pause
exit /b 1

:port_check_done

if exist "%WEB_DIR%.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%WEB_DIR%.env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%TRANSLATOR_PROVIDER%"=="" set "TRANSLATOR_PROVIDER=local_dataset"
if "%SPARK_HTTP_URL%"=="" set "SPARK_HTTP_URL=https://spark-api-open.xf-yun.com/v1/chat/completions"
if "%SPARK_HTTP_MODEL%"=="" set "SPARK_HTTP_MODEL=4.0Ultra"
if "%SPARK_API_URL%"=="" set "SPARK_API_URL=wss://spark-api.xf-yun.com/v4.0/chat"
if "%SPARK_DOMAIN%"=="" set "SPARK_DOMAIN=4.0Ultra"

if not "%CANGJIE_HOME%"=="" if exist "%CANGJIE_HOME%\envsetup.bat" call "%CANGJIE_HOME%\envsetup.bat"
if "%CANGJIE_OUTPUT_ROOT%"=="" set "CANGJIE_OUTPUT_ROOT=%WEB_DIR%outputs"

rem Use a project-local environment so reboots and global Anaconda changes do
rem not change the backend dependency set.
set "BACKEND_VENV=%WEB_DIR%backend\.venv"
set "BACKEND_PYTHON=%BACKEND_VENV%\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
  set "BOOTSTRAP_PYTHON="
  if exist "D:\Anaconda3\python.exe" set "BOOTSTRAP_PYTHON=D:\Anaconda3\python.exe"
  if not defined BOOTSTRAP_PYTHON for /f "delims=" %%P in ('where python 2^>nul') do if not defined BOOTSTRAP_PYTHON set "BOOTSTRAP_PYTHON=%%P"
  if not exist "!BOOTSTRAP_PYTHON!" (
    echo No Python interpreter is available to create the project environment.
    pause
    exit /b 1
  )
  echo Creating project Python environment in: %BACKEND_VENV%
  "!BOOTSTRAP_PYTHON!" -m venv "%BACKEND_VENV%"
  if errorlevel 1 (
    echo Failed to create the project Python environment.
    pause
    exit /b 1
  )
)

"%BACKEND_PYTHON%" -c "import openai, websocket, tree_sitter, tree_sitter_java, tree_sitter_python, tree_sitter_cpp; print('Python dependencies ready')"
if errorlevel 1 (
  echo Project Python dependencies are missing. Installing from requirements.txt...
  "%BACKEND_PYTHON%" -m pip install --disable-pip-version-check -r "%WEB_DIR%backend\requirements.txt"
  if errorlevel 1 (
    echo Backend dependency installation failed.
    pause
    exit /b 1
  )
  "%BACKEND_PYTHON%" -c "import openai, websocket, tree_sitter, tree_sitter_java, tree_sitter_python, tree_sitter_cpp; print('Python dependencies ready')"
  if errorlevel 1 (
    echo Backend dependency verification failed after installation.
    pause
    exit /b 1
  )
)

echo Starting Cangjie translator backend...
echo Backend Python: %BACKEND_PYTHON%
echo Provider: %TRANSLATOR_PROVIDER%
echo Cangjie SDK: %CANGJIE_HOME%
echo Build artifacts: %CANGJIE_OUTPUT_ROOT%
echo Web UI: http://127.0.0.1:8765/
echo API:    http://127.0.0.1:8765/translate
echo.
echo Backend runs independently after startup. This window may be closed after the health check passes.
echo.

if not exist "%CANGJIE_OUTPUT_ROOT%" mkdir "%CANGJIE_OUTPUT_ROOT%"
rem Launch detached from this cmd.exe. Closing this launcher window must not stop
rem a translation that is still processing in the backend.
"%BACKEND_PYTHON%" -B "%WEB_DIR%backend\launch_backend.py" --python "%BACKEND_PYTHON%" --server "%WEB_DIR%backend\server.py" --host 127.0.0.1 --port 8765 --log "%CANGJIE_OUTPUT_ROOT%\backend.log"
if errorlevel 1 (
  echo Backend background launch failed.
  pause
  exit /b 1
)

set "BACKEND_READY="
for /l %%N in (1,1,30) do (
  curl.exe --silent --show-error --fail --max-time 5 http://127.0.0.1:8765/health >nul 2>&1
  if not errorlevel 1 (
    set "BACKEND_READY=1"
    goto backend_ready
  )
  timeout /t 1 /nobreak >nul
)

echo Backend did not become healthy within 30 seconds.
echo Check log: %CANGJIE_OUTPUT_ROOT%\backend.log
if exist "%CANGJIE_OUTPUT_ROOT%\backend.log" type "%CANGJIE_OUTPUT_ROOT%\backend.log"
pause
exit /b 1

:backend_ready
echo Backend health check passed.
echo Web UI is ready: http://127.0.0.1:8765/
echo Backend log: %CANGJIE_OUTPUT_ROOT%\backend.log

pause
