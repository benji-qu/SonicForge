# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from PyInstaller.config import CONF
CONF['cachedir'] = '/tmp/pyinstaller_cache'

ffmpeg_bin = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
extra_binaries = [(ffmpeg_bin, '.')] if os.path.exists(ffmpeg_bin) else []


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
# Exclude the unbranded ~/.flet/client cache from PyInstaller's datas;
# we embed the branded SonicForge.app client directly into Contents/Resources/flet_client.
a.datas = [d for d in a.datas if not d[0].startswith('flet_desktop/app')]
a.binaries = [b for b in a.binaries if not b[0].startswith('flet_desktop/app')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SonicForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SonicForge',
)
app = BUNDLE(
    coll,
    name='SonicForge.app',
    icon='assets/icon.icns',
    bundle_identifier='com.sonicforge.launcher',
    info_plist={
        'CFBundleName': 'SonicForge',
        'CFBundleDisplayName': 'SonicForge',
        'CFBundleShortVersionString': '1.5.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,
    },
)

# Post-build: embed and sign the branded SonicForge.app Flet client inside Contents/Resources/flet_client
import plistlib
import shutil
import subprocess
from pathlib import Path

dist_app = Path(DISTPATH) / 'SonicForge.app'
if dist_app.exists():
    client_dest = dist_app / 'Contents' / 'Resources' / 'flet_client' / 'SonicForge.app'
    if client_dest.exists():
        shutil.rmtree(client_dest)
    client_dest.parent.mkdir(parents=True, exist_ok=True)

    # Locate source Flet.app from /tmp/flet_client_template or ~/.flet/client
    src_client = Path('/tmp/flet_client_template')
    if not src_client.exists():
        import flet_desktop
        base_cache = Path(flet_desktop.ensure_client_cached())
        for entry in base_cache.iterdir():
            if entry.suffix == '.app':
                src_client = entry
                break

    if src_client.exists():
        shutil.copytree(src_client, client_dest, symlinks=True)
        res_dir = client_dest / 'Contents' / 'Resources'
        shutil.copy2('assets/icon.icns', res_dir / 'AppIcon.icns')
        assets_car = res_dir / 'Assets.car'
        if assets_car.exists():
            assets_car.unlink()

        plist_path = client_dest / 'Contents' / 'Info.plist'
        pl = plistlib.loads(plist_path.read_bytes())
        pl['CFBundleName'] = 'SonicForge'
        pl['CFBundleDisplayName'] = 'SonicForge'
        pl['CFBundleIdentifier'] = 'com.sonicforge.client'
        pl['CFBundleIconFile'] = 'AppIcon.icns'
        pl.pop('CFBundleIconName', None)
        plist_path.write_bytes(plistlib.dumps(pl))

        subprocess.run(['codesign', '-s', '-', '--force', '--deep', str(client_dest)], check=True)
        subprocess.run(['codesign', '-s', '-', '--force', str(dist_app)], check=True)

