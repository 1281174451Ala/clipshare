# Clipshare Windows Build Script
# Run in PowerShell: .\scripts\build.ps1
# Or double-click: scripts\build.bat

param(
    [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Clipshare - Windows Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# Step 2: Install dependencies
Write-Host ""
Write-Host "[2/4] Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip 2>&1 | Out-Null

$deps = @(
    "pyinstaller",
    "cryptography",
    "pyperclip",
    "Pillow",
    "pywin32"
)

foreach ($dep in $deps) {
    Write-Host "  Installing $dep..." -ForegroundColor Gray
    pip install $dep 2>&1 | Out-Null
}

# Install project in dev mode
Write-Host "  Installing clipshare..." -ForegroundColor Gray
pip install -e . 2>&1 | Out-Null
Write-Host "  All dependencies installed." -ForegroundColor Green

# Step 3: Build
Write-Host ""
Write-Host "[3/4] Building with PyInstaller..." -ForegroundColor Yellow

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist, __pycache__
    Remove-Item -Force -ErrorAction SilentlyContinue *.spec.orig
}

python -m PyInstaller --clean --noconfirm clipshare.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: PyInstaller build failed." -ForegroundColor Red
    exit 1
}

# Step 4: Verify
Write-Host ""
Write-Host "[4/4] Build complete!" -ForegroundColor Green
Write-Host ""

$exePath = Join-Path $ProjectDir "dist\clipshare.exe"
if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 1)
    Write-Host "  Output: $exePath" -ForegroundColor White
    Write-Host "  Size:   $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Build Successful!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run:" -ForegroundColor White
    Write-Host "  .\dist\clipshare.exe --help" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To share with another PC, copy the entire 'dist' folder." -ForegroundColor White
} else {
    Write-Host "  ERROR: clipshare.exe not found in dist\" -ForegroundColor Red
    Write-Host "  Contents of dist\:" -ForegroundColor Red
    Get-ChildItem dist -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    exit 1
}