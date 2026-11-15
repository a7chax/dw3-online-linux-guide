#!/usr/bin/env python3
"""Refresh the source-only publication snapshot from an explicit local workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import install

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args(); workspace = args.workspace.resolve(); payload = HERE / 'files'
    sources = {}
    for name in install.ROOT_FILES:
        source = (HERE.parent / name if name in {'AI-SETUP.md', 'AI-LINUX-PORT-PLAYBOOK-STE100.md'}
                  else workspace / name)
        if not source.is_file():
            raise ValueError('Missing reviewed source: ' + name)
        sources[name] = source
    for source in (workspace / 'linux/native').rglob('*'):
        if source.is_file() and source.suffix in {'.py', '.java', '.c', '.sh'}:
            sources[str(source.relative_to(workspace))] = source
    for source in (workspace / 'skills/dw3-linux-control').rglob('*'):
        if source.is_file() and (source.suffix == '.md' or source.name == 'openai.yaml'):
            sources[str(source.relative_to(workspace))] = source
    for name in (*sorted(install.FIXTURE_FILES), 'scripts/export-quest-text.py', 'docs/autoplay-design.md', 'docs/inn-routing-findings.md'):
        sources[name] = workspace / name
    entries = []
    for name, source in sorted(sources.items()):
        relative = install.relative_path(name)
        if source.is_symlink() or not source.is_file():
            raise ValueError('Source snapshot requires a regular source file: ' + name)
        destination = payload.joinpath(*relative.parts); destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == '.md':
            text = source.read_text().replace(str(workspace), '/path/to/DW3 Online')
            destination.write_text(text)
        else:
            shutil.copyfile(source, destination)
        mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
        destination.chmod(mode)
        entries.append({'path': name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'mode': mode})
    (HERE / 'manifest.json').write_text(json.dumps({'version': 1, 'files': entries}, indent=2) + '\n')
    print(json.dumps({'files': len(entries), 'native_tests': sum('/tests/test_' in entry['path'] for entry in entries),
                      'java_sources': sum(entry['path'].endswith('.java') for entry in entries)}))


if __name__ == '__main__': main()
