#!/usr/bin/env python3
import importlib.util,copy,json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('talk_game',ROOT/'ai-game.py');game=importlib.util.module_from_spec(s);s.loader.exec_module(game)
def world(step=1,dialogue=True):
 state={'phase':'world','pid':123,'time':datetime.now(timezone.utc).isoformat(),'main_quest':{'chapter':5,'step':step}}
 if dialogue:state['dialogue']={'text':'first','can_advance':True,'page_index':0,'page_count':2}
 return state

class Window:
 def __init__(self,pid):self.pid=pid;self.focus_count=0;self.is_focused=True;self.closed=False
 def focus(self):self.focus_count+=1;self.is_focused=True
 def focused(self):return self.is_focused
 def screenshot(self,path):pass
 def close(self):self.closed=True

class TalkTests(unittest.TestCase):
 def test_waits_for_page_then_confirms_quest_progress(self):
  first=world();first['dialogue']['can_advance']=False
  ready=copy.deepcopy(first);ready['dialogue']['can_advance']=True
  done=world(2,False)
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=[first,ready]),patch.object(game,'_interact',return_value=done) as press,patch.object(game.time,'sleep'),patch('game_control.GameWindow',Window):
   result=game.talk(5,5)
  self.assertEqual(press.call_count,1);self.assertEqual(result['reason'],'quest_progressed')
 def test_missing_progress_after_interaction_is_not_advancement(self):
  after=world(dialogue=False);after.pop('main_quest')
  self.assert_talk_does_not_claim_progress(world(),after)
 def test_partial_progress_after_interaction_is_not_advancement(self):
  after=world(dialogue=False);after['main_quest']['step']=None
  self.assert_talk_does_not_claim_progress(world(),after)
 def test_missing_initial_progress_cannot_establish_advancement(self):
  before=world();before.pop('main_quest')
  self.assert_talk_does_not_claim_progress(before,world(2,False))
 def test_loading_state_is_not_advancement(self):
  after=world(dialogue=False);after.update(phase='loading_map',main_quest=None)
  self.assert_talk_does_not_claim_progress(world(),after)
 def test_stale_changed_progress_is_not_advancement(self):
  after=world(2,False);after['time']='2000-01-01T00:00:00Z'
  self.assert_talk_does_not_claim_progress(world(),after)
 def assert_talk_does_not_claim_progress(self,before,after):
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=before),patch.object(game,'_interact',return_value=after),patch('game_control.GameWindow',Window):
   result=game.talk(5,5)
  self.assertNotEqual(result['reason'],'quest_progressed')
 def test_automated_pages_focus_only_once(self):
  first=world();second=world();second['dialogue']['page_index']=1
  window=Window(123)
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=[first,first,second,second,world(2,False)]),patch.object(game,'press_game_key') as press,patch.object(game.time,'sleep'),patch('game_control.GameWindow',return_value=window):
   result=game.talk(5,5)
  self.assertEqual(press.call_count,2);self.assertEqual(window.focus_count,1);self.assertTrue(window.closed)
  self.assertEqual(result['reason'],'quest_progressed')
 def test_focus_loss_after_page_stops_without_reclaiming_focus(self):
  first=world();window=Window(123)
  def press(*args):window.is_focused=False
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=first),patch.object(game,'press_game_key',side_effect=press) as key,patch.object(game.time,'sleep'),patch('game_control.GameWindow',return_value=window):
   result=game.talk(5,2)
  self.assertEqual(key.call_count,1);self.assertEqual(window.focus_count,1);self.assertTrue(window.closed)
  self.assertEqual(result['reason'],'focus_lost')
 def test_public_interact_can_focus_once(self):
  state=world();window=Window(123)
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=state),patch.object(game,'press_game_key') as press,patch.object(game.time,'sleep'),patch('game_control.GameWindow',return_value=window):
   game.interact()
  self.assertEqual(window.focus_count,1);self.assertTrue(window.closed);press.assert_called_once_with(window,'space')
if __name__=='__main__':unittest.main(verbosity=2)
