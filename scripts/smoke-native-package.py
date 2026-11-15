"""Verify and launch the target-OS native artifact with no development runtime on PATH."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile


def main():
    folder = Path(__file__).resolve().parents[1] / 'native/artifacts'
    suffix = '.zip' if os.name == 'nt' else '.tar.gz'
    packages = list(folder.glob('LaserForge-Native-*' + suffix))
    if len(packages) != 1:
        raise RuntimeError('Expected exactly one native package for this runner')
    archive = packages[0]
    expected = archive.with_name(archive.name + '.sha256').read_text().split()[0]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, 'Package checksum mismatch'
    with tempfile.TemporaryDirectory(prefix='LaserForge native smoke ') as temporary:
        with zipfile.ZipFile(archive) if suffix == '.zip' else tarfile.open(archive) as package:
            if suffix == '.zip':
                assert package.testzip() is None
                package.extractall(temporary)
            else:
                package.extractall(temporary, filter='data')
        root = Path(temporary) / 'LaserForge-Native'
        internal = root / '_internal'
        executable = root / ('LaserForge-Native.exe' if os.name == 'nt' else 'LaserForge-Native')
        for required in [executable, internal / 'runtime' / ('node.exe' if os.name == 'nt' else 'node'),
                         internal / 'bridge/server.mjs', internal / 'branding/mark.png', internal / 'notices/Node-LICENSE.txt']:
            assert required.is_file(), f'Missing packaged resource: {required}'
        assert not any('webengine' in p.name.lower() for p in root.rglob('*'))
        environment = dict(os.environ)
        for key in ('LASERFORGE_NODE', 'PYTHONPATH', 'PYTHONHOME'):
            environment.pop(key, None)
        environment['PATH'] = os.path.join(os.environ['SystemRoot'], 'System32') if os.name == 'nt' else '/nonexistent'
        environment['QT_QPA_PLATFORM'] = 'offscreen'
        screenshot = folder / 'packaged-startup.png'
        subprocess.run([str(executable), '--smoke-test', '--screenshot', str(screenshot)],
                       cwd=temporary, env=environment, timeout=60, check=True)
        assert screenshot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'No rendered startup evidence'
    print(f'Verified checksum, bundled resources and native startup: {archive.name}')


if __name__ == '__main__':
    main()
