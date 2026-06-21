@echo off
setlocal enabledelayedexpansion
title OrisX - System Launcher

:menu
cls
echo.
echo =========================================
echo.
echo     OrisX 26.1-inside  System Launcher
echo.
echo =========================================
echo.
echo     [1]  Normal Mode  - Start OrisX normally
echo     [2]  Change Password - Change user password
echo     [3]  Reset System - Reset filesystem to default
echo     [4]  Exit         - Close launcher
echo.
echo =========================================
echo.
set /p choice="Select option (1-4): "

if "%choice%"=="1" goto normal
if "%choice%"=="2" goto changepw
if "%choice%"=="3" goto reset
if "%choice%"=="4" goto exit
goto menu

:normal
cls
echo.
echo =========================================
echo.
echo          Starting Normal Mode
echo.
echo =========================================
echo.
echo Loading OrisX...
echo.
python OrisX.py
echo.
echo OrisX has exited.
pause
goto menu

:changepw
cls
echo.
echo =========================================
echo.
echo          Change User Password
echo.
echo =========================================
echo.
echo Available users: root, orisx, guest
echo.
set /p username="Enter username: "

if "%username%"=="" (
    echo Username cannot be empty.
    pause
    goto changepw
)

set "jsonfile=%~dp0orisx_root\.orisx_meta.json"

if not exist "%jsonfile%" (
    echo.
    echo User database not found. Please run OrisX first.
    echo.
    pause
    goto menu
)

:: 检查用户是否存在
powershell -command "$data = Get-Content '%jsonfile%' -Raw | ConvertFrom-Json; if ($data.users.'%username%' -eq $null) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo User '%username%' does not exist.
    echo Available users: root, orisx, guest
    echo.
    pause
    goto changepw
)

set /p newpass="Enter new password: "

if "%newpass%"=="" (
    echo Password cannot be empty.
    pause
    goto changepw
)

echo.
echo Updating password...

:: 直接修改密码（简洁！）
powershell -command "$data = Get-Content '%jsonfile%' -Raw | ConvertFrom-Json; $data.users.'%username%'.password = '%newpass%'; $data | ConvertTo-Json -Depth 10 | Set-Content '%jsonfile%'"

echo.
echo Password changed successfully!
echo.
pause
goto menu

:reset
cls
echo.
echo =========================================
echo.
echo          Reset Filesystem
echo.
echo =========================================
echo.
echo WARNING: This will delete ALL data in orisx_root!
echo.
set /p confirm="Are you sure? (y/N): "
if /i not "%confirm%"=="y" (
    echo Reset cancelled.
    pause
    goto menu
)
echo.
echo Removing filesystem...
if exist "%~dp0orisx_root" (
    rmdir /s /q "%~dp0orisx_root"
    echo Filesystem removed.
) else (
    echo Filesystem not found.
)
echo.
echo Reset complete. Please restart OrisX.
pause
goto menu

:exit
cls
echo.
echo Thank you for using OrisX.
echo.
exit