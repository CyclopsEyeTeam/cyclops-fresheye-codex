#!/usr/bin/env python3
"""Install a self-contained experimental candidate without pip or runtime downloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = 'cyclops-fresheye-codex'


def owned(command, versions):
    if not command.is_symlink():
        return False
    target = command.resolve()
    if versions not in target.parents:
        return False
    manifest = target.parent.parent/'install-manifest.json'
    try:
        return json.loads(manifest.read_text()).get('product') == PRODUCT
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', default=str(Path.home()/'.local'))
    parser.add_argument('--data-dir', help='Optional explicit local runtime state location')
    parser.add_argument('--browser-temp-dir', help='Optional short private browser temporary directory')
    parser.add_argument('--replace', action='store_true', help='Back up and replace an existing command')
    parser.add_argument('--uninstall', action='store_true', help='Remove only this installer-owned command')
    args = parser.parse_args()
    prefix = Path(args.prefix).expanduser().resolve()
    base = prefix/'share'/PRODUCT
    versions = base/'versions'
    command = prefix/'bin/codex-fresheye'
    exists = command.exists() or command.is_symlink()
    if args.uninstall:
        if exists and not owned(command, versions):
            parser.error('The command is not owned by this installer; nothing removed')
        if exists:
            command.unlink()
        print('Command removed. Settings, sessions, receipts and installed versions are preserved.')
        return 0
    if exists and not args.replace and not owned(command, versions):
        parser.error('An unrelated command exists. Use --replace only to preserve a backup and replace it.')
    if exists and command.is_dir() and not command.is_symlink():
        parser.error('The command path is a directory; nothing changed')
    if not shutil.which('codex'):
        parser.error('Install the native Codex CLI first; this installer does not download it')
    files = [ROOT/'bin/codex-fresheye', ROOT/'LICENSE', ROOT/'README.md', ROOT/'pyproject.toml']
    files += sorted((ROOT/'src/cyclops_fresheye').glob('*.py'))
    config = {'data_dir': str(Path(args.data_dir).expanduser().resolve()) if args.data_dir else None,
              'browser_tmp': str(Path(args.browser_temp_dir).expanduser().resolve()) if args.browser_temp_dir else None}
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    digest = hashlib.sha256(json.dumps([hashes, config], sort_keys=True).encode()).hexdigest()[:16]
    target = versions/digest
    versions.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        stage = Path(tempfile.mkdtemp(prefix='.install-', dir=versions))
        try:
            for path in files:
                destination = stage/path.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
            (stage/'bin/codex-fresheye').chmod(0o755)
            (stage/'install-config.json').write_text(json.dumps(config, indent=2)+'\n')
            (stage/'install-manifest.json').write_text(json.dumps({
                'product': PRODUCT, 'source_sha256': hashes, 'config': config}, indent=2)+'\n')
            os.replace(stage, target)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    else:
        # Reusing a content-addressed install must not trust edited files.
        for name, expected in hashes.items():
            if hashlib.sha256((target/name).read_bytes()).hexdigest() != expected:
                parser.error('Existing installed version was changed; refusing to reuse it')
        if json.loads((target/'install-config.json').read_text()) != config:
            parser.error('Existing installation settings were changed; nothing replaced')
    command.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if exists:
        backups = base/'backups'
        backups.mkdir(exist_ok=True)
        backup = backups/('codex-fresheye-'+uuid.uuid4().hex)
        if command.is_symlink():
            backup.symlink_to(command.resolve())
        else:
            shutil.copy2(command, backup)
    temporary = command.with_name('.codex-fresheye-'+uuid.uuid4().hex)
    try:
        temporary.symlink_to(target/'bin/codex-fresheye')
        os.replace(temporary, command)
    finally:
        if temporary.is_symlink():
            temporary.unlink()
    print(f'Installed experimental V0: {command}')
    if backup:
        print(f'Previous command preserved: {backup}')
    print('Existing runtime settings and sessions were not moved or modified.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        raise SystemExit(2)
