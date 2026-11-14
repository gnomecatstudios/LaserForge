# Invoked by scripts/build-native.py; all resources are staged before freezing.
import os
import sys
from pathlib import Path

root = Path(os.environ['LASERFORGE_BUILD_ROOT'])
stage = Path(os.environ['LASERFORGE_BUILD_STAGE'])
node_name = 'node.exe' if os.name == 'nt' else 'node'
datas = [(str(stage / name), name) for name in ('bridge', 'branding', 'notices')]

analysis = Analysis(
    [str(root / 'native' / 'packaging' / 'entry.py')],
    pathex=[str(root / 'native')],
    binaries=[(str(stage / 'runtime' / node_name), 'runtime')],
    datas=datas,
    hiddenimports=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
icon = str(stage / 'branding' / ('LaserForge.icns' if sys.platform == 'darwin' else 'favicon.ico'))
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name='LaserForge-Native', debug=False, strip=False, upx=False,
    console=False, icon=icon if sys.platform in ('win32', 'darwin') else None,
)
collection = COLLECT(exe, analysis.binaries, analysis.datas,
                     strip=False, upx=False, name='LaserForge-Native')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='LaserForge.app', icon=icon,
                 bundle_identifier='studio.gnomecat.laserforge.native',
                 info_plist={'CFBundleShortVersionString': os.environ['LASERFORGE_BUILD_VERSION'],
                             'NSHighResolutionCapable': True,
                             'NSBluetoothAlwaysUsageDescription': 'Future machine connections require Bluetooth access.'})
