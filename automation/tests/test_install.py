import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('kit_install', Path(__file__).resolve().parents[1] / 'install.py')
installer = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.game = self.root / 'game'; self.payload = self.root / 'files'
        (self.game / 'app').mkdir(parents=True); (self.game / 'app/client.jar').write_bytes(b'original fixture')
        self.payload.mkdir(); self.manifest = self.root / 'manifest.json'
        self.files = {'game-control.py': b'# fixture control\n', 'ai-game.py': b'# new source\n',
                      '.gitignore': b'.env\nlinux/ai-sessions/\n', '.env.example': b'DW3_PASSWORD=placeholder\n'}
        self.write_manifest()
    def write_manifest(self):
        entries = []
        for name, content in self.files.items():
            source = self.payload / name; source.parent.mkdir(parents=True, exist_ok=True); source.write_bytes(content)
            entries.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest(), 'mode': 0o644})
        self.manifest.write_text(json.dumps({'version': 1, 'files': entries}))
    def install(self, apply=False):
        return installer.install(self.game, apply=apply, payload_dir=self.payload, manifest_path=self.manifest)
    def test_dry_run_changes_nothing(self):
        before = sorted(str(p.relative_to(self.game)) for p in self.game.rglob('*'))
        self.assertFalse(self.install()['applied'])
        self.assertEqual(before, sorted(str(p.relative_to(self.game)) for p in self.game.rglob('*')))
    def test_apply_creates_source_relative_alias_and_preserves_environment(self):
        (self.game / '.env').write_text('private fixture secret')
        self.install(True)
        self.assertEqual((self.game / 'ai-game.py').read_bytes(), self.files['ai-game.py'])
        self.assertTrue((self.game / 'game_control.py').is_symlink())
        self.assertEqual((self.game / 'game_control.py').readlink(), Path('game-control.py'))
        self.assertEqual((self.game / '.env').read_text(), 'private fixture secret')
        self.assertFalse(any(p.name == '.env' for p in (self.game / 'linux').rglob('*')))
    def test_changed_sources_are_backed_up_and_gitignore_is_merged(self):
        (self.game / 'ai-game.py').write_text('# old source\n')
        (self.game / '.gitignore').write_text('my-local-file\n')
        result = self.install(True); backups = Path(result['backup_dir'])
        self.assertEqual((backups / 'ai-game.py').read_text(), '# old source\n')
        self.assertEqual((backups / '.gitignore').read_text(), 'my-local-file\n')
        self.assertIn('my-local-file', (self.game / '.gitignore').read_text())
        self.assertIn('linux/ai-sessions/', (self.game / '.gitignore').read_text())
        self.assertFalse(self.install(True)['backups'])
    def test_absolute_traversal_and_secret_payloads_are_refused_before_writes(self):
        for name in ('/tmp/escape.py', '../escape.py', 'linux/native/../../.env', '.env', '.env.production'):
            with self.subTest(name=name):
                data = json.loads(self.manifest.read_text()); data['files'].append({'path': name, 'sha256': '0' * 64})
                self.manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError): self.install(True)
                self.assertFalse((self.game / 'ai-game.py').exists())
                self.write_manifest()
    def test_outside_parent_symlink_is_refused(self):
        outside = self.root / 'outside'; outside.mkdir(); (self.game / 'scripts').symlink_to(outside)
        self.files['scripts/export-quest-text.py'] = b'# exporter\n'; self.write_manifest()
        with self.assertRaises(ValueError): self.install(True)
        self.assertFalse((outside / 'export-quest-text.py').exists())
    def test_source_checksum_mismatch_is_refused(self):
        (self.payload / 'ai-game.py').write_bytes(b'changed after manifest')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.install(True)
        self.assertFalse((self.game / 'ai-game.py').exists())
    def test_environment_symlink_is_never_read_or_backed_up(self):
        (self.game / '.env').write_text('private fixture secret')
        (self.game / '.env.example').symlink_to('.env')
        with self.assertRaises(ValueError): self.install(True)
        self.assertFalse((self.game / 'linux/automation-backups').exists())
    def test_original_client_is_required(self):
        (self.game / 'app/client.jar').unlink()
        with self.assertRaisesRegex(ValueError, 'app/client.jar'): self.install(True)


if __name__ == '__main__': unittest.main()
