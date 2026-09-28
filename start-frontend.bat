@echo off
setlocal

pushd "%~dp0frontend" 2>nul
if errorlevel 1 (
  echo Cannot find the frontend directory next to this script.
  pause
  exit /b 1
)

where node.exe >nul 2>&1
if errorlevel 1 (
  echo Node.js is not available. Please install Node.js and reopen this script.
  popd
  pause
  exit /b 1
)

if not exist "node_modules\vite\bin\vite.js" goto install_dependencies
if not exist "node_modules\vue\package.json" goto install_dependencies
goto start_server

:install_dependencies
where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo Frontend dependencies are missing, and npm is not available.
  echo Please install Node.js with npm and reopen this script.
  popd
  pause
  exit /b 1
)
echo Installing frontend dependencies...
call npm.cmd install
if errorlevel 1 (
  echo Dependency installation failed.
  popd
  pause
  exit /b 1
)

:start_server
echo Starting the frontend. The default browser will open when Vite is ready.
echo Keep this window open while developing. Press Ctrl+C to stop the server.
node "node_modules\vite\bin\vite.js" --open
set "vite_exit=%errorlevel%"
popd
if not "%vite_exit%"=="0" (
  echo Vite exited with an error. Check the messages above.
  pause
)
exit /b %vite_exit%
