#!/usr/bin/env python3
import importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('quest_game',ROOT/'ai-game.py');game=importlib.util.module_from_spec(s);s.loader.exec_module(game)
class QuestTests(unittest.TestCase):
 def test_resolves_talk_requirement_from_progress_and_shipped_steps(self):
  state={'map':'s470','x':304,'y':342,'main_quest':{'chapter':5,'chapter_count':36,'step':1,'step_count':6,'target_map':'s470','target_npc_id':121,'objective_text':'Step 1 of 6: Go to Swamp Inn.'}}
  quest=game.describe_quest(state)
  self.assertEqual(quest['required_action'],'talk')
  self.assertEqual(quest['next_action'],'talk_to_npc')
  self.assertEqual(quest['target_npc_id'],121)
 def test_unknown_definition_stays_unknown(self):
  state={'map':'s450','main_quest':{'chapter':5,'step':1,'target_map':'new-map','target_npc_id':8}}
  quest=game.describe_quest(state)
  self.assertEqual(quest['required_action'],'unknown')
  self.assertFalse(quest['definition_matches_state'])
if __name__=='__main__':unittest.main(verbosity=2)
