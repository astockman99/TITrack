# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for TITrack."""

import os
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(SPECPATH) / 'src'
sys.path.insert(0, str(src_path))

block_cipher = None

# Data files to include
datas = [
    # Item database seed file
    ('tlidb_items_seed_en.json', '.'),
    # Static web files
    ('src/titrack/web/static', 'titrack/web/static'),
    # README for users
    ('src/titrack/data/README.txt', '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'starlette.routing',
    'starlette.responses',
    'starlette.middleware',
    'starlette.middleware.cors',
    'pydantic',
    'pydantic.deprecated.decorator',
    'fastapi',
    'fastapi.responses',
    'email_validator',
    'httptools',
    'watchfiles',
    'websockets',
    # pywebview for native window
    'webview',
    'webview.platforms',
    'webview.platforms.edgechromium',
    'clr_loader',
    'pythonnet',
]

# Exclude unnecessary modules to reduce size
excludes = [
    'pytest',
    'black',
    'ruff',
    'mypy',
    'tkinter',
    '_tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL',
    'cv2',
]

a = Analysis(
    ['src/titrack/__main__.py'],
    pathex=[str(src_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TITrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disabled - UPX compression triggers AV false positives
    console=False,  # Hide console - logs go to data/titrack.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add icon file
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # Disabled - UPX compression triggers AV false positives
    upx_exclude=[],
    name='TITrack',
)
