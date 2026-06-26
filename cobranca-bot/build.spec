# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para o Bot de Cobranca.

Gera um executavel Windows incluindo os templates de e-mail e os
arquivos web do dashboard.

Uso:
    pyinstaller build.spec
"""
from PyInstaller.utils.hooks import collect_submodules, collect_all

block_cipher = None

datas = [
    ("app/templates", "app/templates"),
    ("app/web", "app/web"),
]
binaries = []
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview")
    + ["openpyxl"]
)

# numpy/pandas carregam C-extensions e dados que precisam ser coletados
# integralmente (senao o exe quebra com "numpy._core._exceptions").
for pkg in ("numpy", "pandas"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BotCobranca",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # app de janela (pywebview), sem console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
