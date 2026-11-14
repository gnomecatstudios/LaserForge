#!/usr/bin/env python3
"""Build an experimental native bundle on the target OS; never publishes artifacts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def copy_runtime_notices(stage: Path, node: Path, node_license: Path | None) -> None:
    notices = stage / 'notices'
    notices.mkdir()
    for source, destination in [
        (ROOT / 'LICENSE', 'LaserForge-LICENSE.txt'),
        (ROOT / 'packages/libopenlaser/LICENSE', 'libopenlaser-LICENSE.txt'),
        (ROOT / 'native/packaging/THIRD-PARTY.md', 'THIRD-PARTY.md'),
        (ROOT / 'pnpm-lock.yaml', 'pnpm-lock.yaml'),
    ]:
        shutil.copy2(source, notices / destination)
    shutil.copytree(ROOT / 'native/packaging/licenses', notices / 'Qt-LGPL-GPL')
    python_license = next((p for p in [Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt',
                                       Path(sys.base_prefix) / 'LICENSE.txt'] if p.is_file()), None)
    if python_license is None:
        raise RuntimeError('Missing Python runtime LICENSE.txt; cannot redistribute without its notice')
    shutil.copy2(python_license, notices / 'Python-LICENSE.txt')
    versions = {'python': platform.python_version(), 'node': subprocess.check_output(
        [str(node), '--version'], text=True).strip()}
    for name in ('PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6', 'pyinstaller'):
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        metadata = notices / name / 'METADATA.txt'
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(distribution.read_text('METADATA') or '', encoding='utf-8')
        for entry in distribution.files or ():
            if any('license' in part.lower() or 'copying' in part.lower() for part in entry.parts):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = notices / name / str(entry).replace('..', '_')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    candidates = [node_license] if node_license else [
        node.parent / 'LICENSE', node.parent.parent / 'LICENSE',
        node.parent / 'LICENSE.txt', node.parent.parent / 'LICENSE.txt',
    ]
    local_license = next((p for p in candidates if p is not None and p.is_file()), None)
    if local_license:
        shutil.copy2(local_license, notices / 'Node-LICENSE.txt')
    else:
        url = f"https://raw.githubusercontent.com/nodejs/node/{versions['node']}/LICENSE"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read(2 * 1024 * 1024)
            if b'Node.js' not in content or b'Copyright' not in content:
                raise ValueError('Unexpected Node license content')
            (notices / 'Node-LICENSE.txt').write_bytes(content)
        except Exception as error:
            raise RuntimeError('Cannot obtain Node license; provide --node-license PATH') from error
    # Preserve all installed production dependency notices. Duplicate package
    # versions retain distinct pnpm store paths instead of overwriting one another.
    modules = ROOT / 'node_modules/.pnpm'
    entries = list(modules.glob('*/node_modules/*/*')) + list(modules.glob('*/node_modules/@*/*/*'))
    for source in sorted(entries):
        if source.is_file() and source.name.lower().startswith(('license', 'copying', 'notice')):
            target = notices / 'javascript' / source.relative_to(modules)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    (notices / 'runtime-versions.json').write_text(json.dumps(versions, indent=2) + '\n')


def target_id() -> str:
    system = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform)
    architecture = {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64'}.get(
        platform.machine().lower(), platform.machine().lower())
    if system not in {'windows', 'linux', 'macos'}:
        raise ValueError(f'No native packaging recipe for {system}')
    return f'{system}-{architecture}'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'native/artifacts')
    parser.add_argument('--node', type=Path, help='target-platform Node executable (defaults to PATH)')
    parser.add_argument('--node-license', type=Path, help='complete license for the packaged Node version')
    parser.add_argument('--skip-bridge-build', action='store_true', help='use existing native/bridge/dist/server.mjs')
    args = parser.parse_args()
    version = json.loads((ROOT / 'package.json').read_text())['version']
    node = (args.node or Path(shutil.which('node') or 'missing-node')).resolve()
    if not node.is_file():
        parser.error('Install Node.js 24 or supply --node PATH')
    node_version = subprocess.check_output([str(node), '--version'], text=True).strip()
    if int(node_version.removeprefix('v').split('.')[0]) < 24:
        parser.error('Node.js 24 or newer is required')
    node_architecture = subprocess.check_output([str(node), '-p', 'process.arch'], text=True).strip()
    host_architecture = target_id().rsplit('-', 1)[-1]
    if node_architecture != host_architecture:
        parser.error(f'Node architecture {node_architecture} differs from target {host_architecture}')
    if not args.skip_bridge_build:
        subprocess.run(['corepack', 'pnpm', 'exec', 'vite', 'build', '--config',
                        'native/bridge/vite.config.ts'], cwd=ROOT, check=True)
    bridge = ROOT / 'native/bridge/dist/server.mjs'
    if not bridge.is_file():
        parser.error('Missing bundled bridge; build it before packaging')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='laserforge-native-build-') as temporary:
        work = Path(temporary)
        stage = work / 'resources'
        (stage / 'runtime').mkdir(parents=True)
        shutil.copy2(node, stage / 'runtime' / ('node.exe' if os.name == 'nt' else 'node'))
        shutil.copytree(bridge.parent, stage / 'bridge')
        branding = stage / 'branding'
        branding.mkdir()
        for name in ('mark.png', 'icon-192.png', 'icon-512.png', 'favicon.ico'):
            shutil.copy2(ROOT / 'public' / name, branding / name)
        if sys.platform == 'darwin':
            from PIL import Image
            with Image.open(ROOT / 'public/icon-512.png') as artwork:
                artwork.save(branding / 'LaserForge.icns')
        copy_runtime_notices(stage, node, args.node_license)
        environment = {**os.environ, 'LASERFORGE_BUILD_ROOT': str(ROOT),
                       'LASERFORGE_BUILD_STAGE': str(stage), 'LASERFORGE_BUILD_VERSION': version,
                       'PYINSTALLER_CONFIG_DIR': str(work / 'cache')}
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                        '--distpath', str(work / 'dist'), '--workpath', str(work / 'build'),
                        str(ROOT / 'native/packaging/LaserForge.spec')], env=environment, cwd=ROOT, check=True)
        package = work / 'dist' / ('LaserForge.app' if sys.platform == 'darwin' else 'LaserForge-Native')
        # QtWebEngine is neither imported nor permitted in the distributable.
        if any('webengine' in path.name.lower() for path in package.rglob('*')):
            raise RuntimeError('Unexpected QtWebEngine dependency in native package')
        if sys.platform.startswith('linux'):
            shutil.copy2(ROOT / 'native/packaging/laserforge-native.desktop', package)
            shutil.copy2(ROOT / 'public/icon-192.png', package / 'laserforge-native.png')
        archive_base = work / f'LaserForge-Native-{target_id()}-v{version}'
        if sys.platform == 'darwin':
            # ditto preserves .app framework symlinks and resource forks.
            archive = Path(str(archive_base) + '.zip')
            subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                            str(package), str(archive)], check=True)
        elif sys.platform.startswith('linux'):
            archive = Path(str(archive_base) + '.tar.gz')
            with tarfile.open(archive, 'w:gz', compresslevel=6) as bundle:
                bundle.add(package, arcname=package.name)
        else:
            archive = Path(shutil.make_archive(str(archive_base), 'zip', root_dir=package.parent,
                                               base_dir=package.name))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        # Interrupted builds retain the previous complete artifact.
        destination = output / archive.name
        staged_archive = output / f'.{archive.name}.{os.getpid()}.tmp'
        shutil.copy2(archive, staged_archive)
        staged_archive.replace(destination)
        destination.with_name(destination.name + '.sha256').write_text(f'{digest}  {destination.name}\n')
        print(f'Built experimental native package: {destination}')
        print('Platform support requires successful runtime and feature validation on this OS.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
