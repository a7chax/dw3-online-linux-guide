#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
class QuestTextExportTests(unittest.TestCase):
 def test_exact_english_resource_allowlist_and_no_credential_loading(self):
  source=ROOT/'scripts/export-quest-text.py'
  self.assertTrue(source.exists(),'Standalone English quest-text exporter is missing')
  spec=importlib.util.spec_from_file_location('export_quest_text',source)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  self.assertEqual(module.resource_paths(),['text/en/places.json',*[f'text/en/talk{i}.json' for i in range(11)]])
  self.assertEqual(module.child_environment({'DW3_PASSWORD':'fixture-secret','PATH':'/bin'}),{'PATH':'/bin'})
if __name__=='__main__':unittest.main(verbosity=2)
