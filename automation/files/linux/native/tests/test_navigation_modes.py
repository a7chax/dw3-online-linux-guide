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
 def test_inn_approach_stops_when_original_interaction_check_is_ready(self):
  import world_map
  state=dict(phase='world',pid=123,map='fixture',x=357.35846,y=338.4521,facing=5,
             time=datetime.now(timezone.utc).isoformat(),movement_ready=True,
             nearby_inns=[dict(map='fixture',x=345,y=308,can_interact=True,interaction_facings=[5])],
             trace=dict(enabled=True,route_type=1,steps_remaining=7,points=[[400,350]]))
  class Atlas:
   def __init__(self,map_id):pass
   def path(self,start,goal):return [list(start),list(goal)]
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),\
       patch.object(game,'request',return_value=state),patch.object(game,'move',side_effect=AssertionError('Inn is already in interaction range')) as move,\
       patch('game_control.GameWindow',Window),patch.object(world_map,'WorldMap',Atlas):
   report=game.follow_trace(5,destination=(350,327),interaction_target=(345,308))
  move.assert_not_called();self.assertEqual(report['reason'],'interaction_required')
 def test_npc_approach_does_not_claim_arrival_outside_talking_range(self):
  import world_map
  state=dict(phase='world',pid=123,map='fixture',x=100.,y=100.,facing=6,
             time=datetime.now(timezone.utc).isoformat(),movement_ready=True,
             trace=dict(enabled=True,route_type=2,steps_remaining=4,points=[[126,100]]))
  class Atlas:
   def __init__(self,map_id):pass
   def path(self,start,goal):return [list(start),list(goal)]
  def movement(*args,**kwargs):
   before=copy.deepcopy(state);state['x']=106.
   return dict(before=before,after=copy.deepcopy(state),moved=True)
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),\
       patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),\
       patch.object(game,'move',side_effect=movement) as move,patch('game_control.GameWindow',Window),\
       patch.object(world_map,'WorldMap',Atlas):
   report=game.follow_trace(5,destination=(104,100),interaction_target=(126,100))
  move.assert_called_once();self.assertEqual(report['reason'],'interaction_required')
  self.assertEqual(report['current']['x'],106.)
 def test_blocked_npc_destination_stops_before_window_or_input(self):
  import world_map
  original=world_map.WorldMap
  for goal in ((300,278),(297.5,278)):
   with self.subTest(goal=goal),tempfile.TemporaryDirectory() as td:
    root=Path(td);atlas=root/'atlas';atlas.mkdir()
    image=Image.new('L',(384,384),255)
    image.paste(0,(300,270,310,290));image.save(atlas/'mask.png')
    (atlas/'atlas.json').write_text(json.dumps({'maps':[dict(id='s255',width=384,height=384,collision='mask.png')]}))
    state=dict(phase='world',map='s255',x=259.8908,y=277.5358,pid=118127,facing=7,
               movement_ready=True,time=datetime.now(timezone.utc).isoformat(),
               main_quest=dict(chapter=9,step=1,target_map='s255'),
               trace=dict(enabled=True,route_type=2,steps_remaining=4,points=[list(goal)]))
    # Cover both a blocked foot and a clear foot clipped by body clearance.
    terrain=original('s255',atlas)
    self.assertTrue(terrain.walkable(state['x'],state['y']))
    self.assertFalse(terrain.walkable(*goal))
    with patch.object(game,'LATEST',root),patch.object(game,'request',return_value=state),\
         patch.object(game,'move',side_effect=AssertionError('Blocked destination must send no input')) as move,\
         patch('game_control.GameWindow',side_effect=AssertionError('Blocked destination must not open a window')) as window,\
         patch.object(world_map,'WorldMap',side_effect=lambda id:original(id,atlas)):
     report=game.follow_trace(5,destination=goal,cross_map=True)
    move.assert_not_called();window.assert_not_called()
    self.assertEqual(report['reason'],'local_route_unavailable')
    self.assertEqual(report['bursts'],0);self.assertFalse(report['active'])
    self.assertEqual(report['current'],state)
    self.assertEqual(report['destination'],list(goal))
    self.assertEqual(json.loads((root/'follow-state.json').read_text()),report)
 def test_unreachable_local_route_stops_before_window_or_input(self):
  import world_map
  original=world_map.WorldMap
  for blocked_start in (True,False):
   with self.subTest(blocked_start=blocked_start),tempfile.TemporaryDirectory() as td:
    root=Path(td);atlas=root/'atlas';atlas.mkdir()
    image=Image.new('L',(832,384),255)
    if blocked_start:
     # A blocked foot pixel cannot use the bounded margin escape.
     image.paste(0,(0,297,832,384));goal=(700,280)
    else:
     image.paste(0,(740,0,746,384));goal=(700,297)
    image.save(atlas/'mask.png')
    (atlas/'atlas.json').write_text(json.dumps({'maps':[dict(id='s205',width=832,height=384,collision='mask.png')]}))
    state=dict(phase='world',map='s205',x=776.5,y=297.6646,pid=98094,facing=0,
               movement_ready=True,time=datetime.now(timezone.utc).isoformat(),
               main_quest=dict(chapter=5,step=6,target_map='s380'),
               trace=dict(enabled=True,route_type=1,steps_remaining=52,points=[list(goal)]))
    with patch.object(game,'LATEST',root),patch.object(game,'request',return_value=state),\
         patch.object(game,'move',side_effect=AssertionError('No route must send no input')) as move,\
         patch('game_control.GameWindow',side_effect=AssertionError('No route must not open a window')) as window,\
         patch.object(world_map,'WorldMap',side_effect=lambda id:original(id,atlas)):
     report=game.follow_trace(5,destination=goal,cross_map=True)
    move.assert_not_called();window.assert_not_called()
    self.assertEqual(report['reason'],'local_route_unavailable')
    self.assertEqual(report['bursts'],0);self.assertFalse(report['active'])
    self.assertEqual(report['current'],state)
    self.assertEqual(report['navigation_source'],'local_collision_atlas')
    self.assertEqual(json.loads((root/'follow-state.json').read_text()),report)
 def test_unexpected_planner_error_is_not_an_unavailable_route(self):
  state=dict(phase='world',map='fixture',x=12.,y=12.,pid=1,
             time=datetime.now(timezone.utc).isoformat(),trace={})
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),\
       patch.object(game,'request',return_value=state),patch('world_map.WorldMap') as atlas,\
       patch('game_control.GameWindow',side_effect=AssertionError('Planning failed before window access')):
   atlas.return_value.path.side_effect=RuntimeError('Local route search exceeded its node limit.')
   with self.assertRaisesRegex(RuntimeError,'node limit'):game.follow_trace(5,destination=(52,12))
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
