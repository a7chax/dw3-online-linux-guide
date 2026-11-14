#!/usr/bin/env python3
from pathlib import Path
import copy,fcntl,importlib.util,json,sys,tempfile,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('mode_game',ROOT/'ai-game.py');game=importlib.util.module_from_spec(s);s.loader.exec_module(game)
class Window:
 def __init__(self,pid):pass
 def focus(self):pass
 def focused(self):return True
 def close(self):pass
class ModeTests(unittest.TestCase):
 def test_continuous_mode_follows_map_changes_until_interaction(self):
  results=[dict(reason='map_changed',before=dict(map='a'),current=dict(map='b')),dict(reason='map_changed',before=dict(map='b'),current=dict(map='c')),dict(reason='interaction_required',before=dict(map='c'),current=dict(map='c'))]
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'_follow_trace',side_effect=results) as run:
   report=game.follow_trace(10,continuous=True)
  self.assertEqual(run.call_count,3);self.assertEqual(len(report['map_transitions']),2);self.assertEqual(report['reason'],'interaction_required')
  self.assertEqual([call.kwargs['focus_on_start'] for call in run.call_args_list],[True,False,False])
 def test_another_controller_cannot_take_the_same_session(self):
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)):
   with (Path(td)/'navigation.lock').open('a+') as lease:
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaisesRegex(RuntimeError,'already running'):game.follow_trace(5)
 def test_standalone_move_refuses_while_navigation_owns_the_session(self):
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=AssertionError('Locked movement must not reach game control')) as request:
   with (Path(td)/'navigation.lock').open('a+') as lease:
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaisesRegex(RuntimeError,'already running'):game.move('right',100)
   request.assert_not_called()
 def test_dismiss_refuses_while_navigation_owns_the_session(self):
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=AssertionError('Locked dismissal must not reach game control')) as request:
   with (Path(td)/'navigation.lock').open('a+') as lease:
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaisesRegex(RuntimeError,'already running'):game.dismiss_popup()
   request.assert_not_called()
 def test_later_map_segment_stops_on_lost_focus_without_forcing_it_back(self):
  state=dict(phase='world',map='next-map',x=12.0,y=12.0,pid=1,facing=6,time=datetime.now(timezone.utc).isoformat(),trace=dict(enabled=False,route_type=0,steps_remaining=0,points=[]))
  class UnfocusedWindow(Window):
   def focus(self):raise AssertionError('A later map segment must not force focus')
   def focused(self):return False
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=state),patch.object(game,'move') as move,patch('game_control.GameWindow',UnfocusedWindow):
   report=game._follow_trace(5,focus_on_start=False)
  move.assert_not_called();self.assertEqual(report['reason'],'focus_lost')
 def test_npc_target_stops_without_walking_into_it(self):
  state=dict(phase='world',map='s470',x=304.0,y=342.0,pid=1,facing=2,time=datetime.now(timezone.utc).isoformat(),trace=dict(enabled=True,route_type=2,steps_remaining=2,points=[[296,342],[289,338]]))
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=state),patch.object(game,'move') as move,patch('game_control.GameWindow',Window):
   report=game.follow_trace(5)
  move.assert_not_called();self.assertEqual(report['reason'],'interaction_required')
 def test_local_navigation_works_with_no_gps_route(self):
  import world_map
  original=world_map.WorldMap
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);atlas=root/'atlas';atlas.mkdir();Image.new('L',(64,64),255).save(atlas/'mask.png')
   (atlas/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',name='Test',width=64,height=64,collision='mask.png')]}))
   state=dict(phase='world',map='test',x=12.0,y=12.0,pid=1,facing=6,time=datetime.now(timezone.utc).isoformat(),trace=dict(enabled=False,route_type=0,steps_remaining=0,points=[]))
   calls=[]
   def movement(direction,milliseconds,**kwargs):
    before=copy.deepcopy(state);calls.append(direction);state['x']+=12
    return dict(before=before,after=copy.deepcopy(state),moved=True)
   with patch.object(game,'LATEST',root),patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window),patch.object(world_map,'WorldMap',side_effect=lambda id:original(id,atlas)):
    report=game.follow_trace(5,destination=(52,12))
   self.assertTrue(calls);self.assertEqual(set(calls),{'right'});self.assertEqual(report['reason'],'destination_reached');self.assertEqual(report['navigation_source'],'local_collision_atlas')
if __name__=='__main__':unittest.main(verbosity=2)
