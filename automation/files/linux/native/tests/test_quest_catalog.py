#!/usr/bin/env python3
"""Offline catalog coverage and conservative enrichment tests."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[3]


class QuestCatalogTests(unittest.TestCase):
    def load_module(self):
        source = ROOT / 'quest_catalog.py'
        self.assertTrue(source.exists(), 'Offline quest catalog is missing')
        spec = importlib.util.spec_from_file_location('quest_catalog', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_every_bundled_chapter_and_step_is_preserved(self):
        module = self.load_module()
        with zipfile.ZipFile(ROOT / 'app/client.jar') as jar:
            original = json.loads(jar.read('quests/steps.json'))['chapters']
            places = json.loads(jar.read('quests/places.json'))['chapters']
        catalog = module.build_catalog(ROOT / 'app/client.jar', ROOT / 'linux/world')
        self.assertEqual(catalog['summary']['chapter_count'], 36)
        self.assertEqual(catalog['summary']['step_count'], sum(map(len, original)))
        for index, chapter in enumerate(catalog['chapters']):
            self.assertEqual(chapter['number'], index + 1)
            self.assertEqual(chapter['place_ids'], places[index])
            self.assertEqual([step['definition'] for step in chapter['steps']], original[index])
            self.assertEqual([step['number'] for step in chapter['steps']], list(range(1, len(original[index]) + 1)))
        self.assertEqual(catalog['summary']['action_counts'], {'drop': 1, 'enter': 17, 'talk': 55, 'zone': 40})
        step = catalog['chapters'][4]['steps'][0]
        self.assertEqual(step['npc']['logical_id'], 121)
        self.assertEqual(step['map']['id'], 's470')
        self.assertTrue(step['npc']['records'])
        self.assertIsNone(step['npc']['position'])

    def test_missing_sources_and_unknown_actions_do_not_invent_names(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar_path = root / 'client.jar'
            with zipfile.ZipFile(jar_path, 'w') as jar:
                jar.writestr('quests/steps.json', json.dumps({'chapters': [[{'stage': 'missing', 'how': 'server_action', 'npc': 999}]]}))
                jar.writestr('quests/places.json', json.dumps({'chapters': [['missing']]}))
            catalog = module.build_catalog(jar_path, root / 'absent-world')
            chapter = catalog['chapters'][0]
            step = chapter['steps'][0]
            self.assertIsNone(chapter['title'])
            self.assertIsNone(step['map']['name'])
            self.assertIsNone(step['map']['width'])
            self.assertEqual(step['action'], 'server_action')
            self.assertIsNone(step['npc']['name'])
            self.assertEqual(step['npc']['records'], [])
            self.assertIsNone(step['npc']['position'])

    def test_map_ids_are_not_human_place_names_and_npcs_match_map(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); world = root / 'world'; (world / 'auxiliary').mkdir(parents=True)
            with zipfile.ZipFile(root / 'client.jar', 'w') as jar:
                jar.writestr('quests/steps.json', json.dumps({'chapters': [[{'stage': 's211', 'how': 'talk', 'npc': 121}]]}))
                jar.writestr('quests/places.json', json.dumps({'chapters': [['s211']]}))
            (world / 'atlas.json').write_text(json.dumps({'maps': [{'id': 's211', 'name': 's210', 'width': 64, 'height': 32, 'place': 3}]}))
            (world / 'auxiliary/npcs.json').write_text(json.dumps([{'stage': 's210', 'npc': 121, 'character': 'other-map', 'file': 0, 'texts': [1]}]))
            step = module.build_catalog(root / 'client.jar', world)['chapters'][0]['steps'][0]
            self.assertIsNone(step['map']['name'])
            self.assertEqual(step['map']['width'], 64)
            self.assertEqual(step['map']['place_id'], 3)
            self.assertEqual(step['npc']['records'], [])

    def test_actual_text_arrays_enrich_only_valid_references(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); world = root / 'world'; texts = world / 'auxiliary/text/en'
            texts.mkdir(parents=True)
            with zipfile.ZipFile(root / 'client.jar', 'w') as jar:
                jar.writestr('quests/steps.json', json.dumps({'chapters': [[{'stage': 's211', 'how': 'talk', 'npc': 121}, {'stage': 's212', 'how': 'zone'}]]}))
                jar.writestr('quests/places.json', json.dumps({'chapters': [['s211', 's212']]}))
            (world / 'atlas.json').write_text(json.dumps({'maps': [{'id': 's211', 'name': 's210', 'width': 64, 'height': 32, 'place': 1}, {'id': 's212', 'name': 's212', 'place': 999}]}))
            (world / 'auxiliary/npcs.json').write_text(json.dumps([{'stage': 's211', 'npc': 121, 'character': 'guide', 'file': 0, 'texts': [0, 1, 2, 999, -1]}]))
            (texts / 'places.json').write_text(json.dumps(['', 'Known place']))
            (texts / 'talk0.json').write_text(json.dumps(['[name]?Unknown[name]?', '[name][color]Invalid[name]Hi', '[name]Guide[name]Welcome[pause]Next']))
            catalog = module.build_catalog(root / 'client.jar', world)
            step, other = catalog['chapters'][0]['steps']
            self.assertEqual(step['map']['place_name'], 'Known place')
            self.assertEqual(step['npc']['name'], 'Guide')
            self.assertEqual(step['npc']['records'][0]['dialogue_candidates'][2]['text'], '[name]Guide[name]Welcome[pause]Next')
            self.assertIsNone(step['npc']['records'][0]['dialogue_candidates'][3]['text'])
            self.assertIsNone(step['npc']['records'][0]['dialogue_candidates'][4]['text'])
            self.assertIsNone(other['map']['place_name'])
            self.assertIsNone(catalog['chapters'][0]['title'])

    def test_export_is_deterministic_and_contains_every_step(self):
        module = self.load_module()
        catalog = module.build_catalog(ROOT / 'app/client.jar', ROOT / 'linux/world')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.export_catalog(catalog, root)
            first = {p.name: p.read_bytes() for p in root.iterdir()}
            module.export_catalog(catalog, root)
            self.assertEqual(first, {p.name: p.read_bytes() for p in root.iterdir()})
            markdown = (root / 'main-quests.md').read_text()
            for chapter in catalog['chapters']:
                for step in chapter['steps']:
                    self.assertIn(f"| {chapter['number']}.{step['number']} |", markdown)
            self.assertEqual(json.loads((root / 'main-quests.json').read_text()), catalog)

    def test_cli_chapter_works_outside_game_directory(self):
        self.load_module()
        result = subprocess.run([sys.executable, str(ROOT / 'quest_catalog.py'), 'chapter', '5', '--json'], cwd='/tmp', capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        chapter = json.loads(result.stdout)
        self.assertEqual(chapter['number'], 5)
        self.assertEqual(len(chapter['steps']), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
