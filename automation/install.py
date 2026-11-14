#!/usr/bin/env python3
"""Install the reviewed source kit into an existing game directory; dry-run by default."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT_FILES = {
    'automation.py', 'ai-game.py', 'autoplay.py', 'codex_repair.py', 'motion_watch.py', 'world_map.py',
    'inn_recovery.py', 'inn_routes.py',
    'quest_catalog.py', 'game-control.py', 'login-ai-game.py', 'play-linux.sh',
    'start-ai-game.sh', 'print-game-state.sh', 'pyproject.toml', 'uv.lock',
    '.env.example', '.gitignore', 'README-AUTOPLAY.md', 'AI-GAME-CONTROL.md',
    'GAME-STATE-PRINTING.md', 'WORLD-ATLAS.md', 'README-LINUX.md',
    'LINUX-PORT-GUIDE-STE100.md', 'AI-SETUP.md', 'AI-LINUX-PORT-PLAYBOOK-STE100.md',
}


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid payload path.')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Payload paths must be relative and contain no traversal.')
    if any(part.startswith('.env') and part != '.env.example' for part in path.parts):
        raise ValueError('Private environment files cannot be installed.')
    allowed = (value in ROOT_FILES or value == 'scripts/export-quest-text.py'
               or value in {'docs/autoplay-design.md', 'docs/inn-routing-findings.md'}
               or value == 'skills/dw3-linux-control/agents/openai.yaml'
               or (value.startswith('skills/dw3-linux-control/') and path.suffix == '.md')
               or (value.startswith('linux/native/') and path.suffix in {'.py', '.java', '.c', '.sh'}))
    if not allowed:
        raise ValueError('Path is outside the source-only allowlist: ' + value)
    return path


def safe_destination(root, relative):
    target = root.joinpath(*PurePosixPath(relative).parts)
    for parent in [target.parent, *target.parent.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('Refusing a destination with a symlink parent: ' + str(target))
    if not target.resolve().is_relative_to(root):
        raise ValueError('Destination escapes the game directory: ' + str(target))
    return target


def merged_ignore(existing, incoming):
    known = set(existing.splitlines())
    missing = [line for line in incoming.splitlines() if line and line not in known]
    if not missing:
        return existing
    return existing.rstrip('\n') + ('\n\n' if existing else '') + '\n'.join(missing) + '\n'


def install(game_dir, *, apply=False, payload_dir=None, manifest_path=None):
    game = Path(game_dir).resolve()
    if not (game / 'app/client.jar').is_file():
        raise ValueError('Provide an existing game directory containing app/client.jar.')
    payload = Path(payload_dir) if payload_dir is not None else HERE / 'files'
    manifest = Path(manifest_path) if manifest_path is not None else HERE / 'manifest.json'
    if payload.is_symlink():
        raise ValueError('The source payload cannot be a symlink.')
    payload = payload.resolve()
    data = json.loads(manifest.read_text())
    if data.get('version') != 1 or not isinstance(data.get('files'), list):
        raise ValueError('Unsupported source manifest.')
    plan = []; seen = set()
    for entry in data['files']:
        relative = relative_path(entry['path']); name = str(relative)
        if name in seen:
            raise ValueError('Duplicate manifest path: ' + name)
        seen.add(name)
        source = payload.joinpath(*relative.parts)
        if any(parent.is_symlink() for parent in [source, *source.parents] if parent != payload and parent.is_relative_to(payload)):
            raise ValueError('Source payload symlinks are not permitted: ' + name)
        if not source.resolve().is_relative_to(payload) or not source.is_file():
            raise ValueError('Missing or escaped source payload: ' + name)
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry.get('sha256'):
            raise ValueError('Source checksum mismatch: ' + name)
        mode = entry.get('mode', 0o644)
        if mode not in (0o644, 0o755):
            raise ValueError('Unsupported source mode: ' + name)
        target = safe_destination(game, relative)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('Refusing a non-regular destination: ' + name)
        old = target.read_bytes() if target.exists() else None
        if name == '.gitignore':
            content = merged_ignore((old or b'').decode('utf-8'), content.decode('utf-8')).encode('utf-8')
        if old != content or (target.exists() and target.stat().st_mode & 0o777 != mode):
            plan.append((name, target, content, mode))
    if 'game-control.py' not in seen:
        raise ValueError('The manifest must include game-control.py for its import alias.')
    alias = safe_destination(game, 'game_control.py')
    alias_needed = not (alias.is_symlink() and os.readlink(alias) == 'game-control.py')
    if alias.exists() and not alias.is_file():
        raise ValueError('Refusing a non-file import alias.')
    backup_root = safe_destination(game, 'linux/automation-backups')
    if backup_root.is_symlink():
        raise ValueError('The backup directory cannot be a symlink.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backups = []
    if apply:
        def backup(name, target):
            if not target.exists() and not target.is_symlink():
                return
            destination = safe_destination(game, 'linux/automation-backups/' + stamp + '/' + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                os.symlink(os.readlink(target), destination)
            else:
                shutil.copy2(target, destination)
            backups.append(name)
        for name, target, content, mode in plan:
            backup(name, target)
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.automation-', dir=target.parent)
            try:
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(content)
                os.chmod(temporary, mode); os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        if alias_needed:
            backup('game_control.py', alias)
            alias.unlink(missing_ok=True)
            alias.symlink_to('game-control.py')
    return {'applied': apply, 'game_dir': str(game), 'files_changed': len(plan),
            'alias_changed': alias_needed, 'backups': backups,
            'backup_dir': str(backup_root / stamp) if backups else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='Copy checked sources; otherwise only report the plan')
    args = parser.parse_args()
    result = install(args.game_dir, apply=args.apply)
    print(json.dumps(result, indent=2))
    print('\nNext steps in your game directory (not executed by this installer):')
    print('cd -- ' + shlex.quote(result['game_dir']))
    print('uv sync --locked')
    print('uv run --locked python linux/native/build.py')
    print('bash linux/native/build-executable.sh')
    print('uv run --locked automation.py')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
