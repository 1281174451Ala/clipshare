# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Clipshare."""

import sys
import os
from pathlib import Path

# Determine platform
is_macos = sys.platform == "darwin"
is_windows = sys.platform == "win32"

a = Analysis(
    ['src/clipshare/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'clipshare',
        'clipshare.cli',
        'clipshare.config',
        'clipshare.constants',
        'clipshare.crypto',
        'clipshare.daemon',
        'clipshare.discovery',
        'clipshare.protocol',
        'clipshare.sync',
        'clipshare.clipboard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Additional hidden imports for platform-specific clipboard backends
if is_macos:
    a.hiddenimports += ['AppKit', 'Foundation', 'objc']
elif is_windows:
    a.hiddenimports += ['win32clipboard', 'win32con', 'pywintypes']

# Cryptography library needs special handling
a.hiddenimports += [
    'cryptography',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.backends',
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='clipshare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)