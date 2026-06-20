@echo off
REM Clipshare Windows Build Script (double-click to run)
REM Requires: Python 3.8+ installed and in PATH

cd /d "%~dp0\.."

echo ============================================
echo   Clipshare - Windows Build
echo ============================================
echo.

echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python not found. Install Python 3.8+ first.
    echo   Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo   OK
echo.

echo [2/4] Installing dependencies...
pip install pyinstaller cryptography pyperclip Pillow pywin32 -q
pip install -e . -q
echo   OK
echo.

echo [3/4] Building with PyInstaller...
python -m PyInstaller --clean --noconfirm clipshare.spec
if %errorlevel% neq 0 (
    echo   ERROR: Build failed.
    pause
    exit /b 1
)
echo.

echo [4/4] Build complete!
echo.
echo   Output: dist\clipshare.exe
echo.
echo ============================================
echo   Build Successful!
echo ============================================
echo.
echo   To run: dist\clipshare.exe --help
echo.

pause