#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile,copy,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ai_game',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

def world(points,x=0,y=0,route_type=1):
 return dict(phase='world',map='test',x=x,y=y,trace=dict(enabled=True,route_type=route_type,points=points,steps_remaining=20))

class TraceControlTests(unittest.TestCase):
 def test_diagonal_route_holds_both_axes_when_backend_supports_it(self):
  self.assertEqual(game.trace_step(world([[14,7],[28,14]]),diagonal=True)[0],'down_right')
  self.assertEqual(game.forward_step({'facing':3},diagonal=True),('up_left',100))
 def test_blocked_major_axis_uses_other_axis_toward_route(self):
  state=world([[10,-10],[20,-20]])
  self.assertEqual(game.trace_step(state,blocked_direction='up')[0],'right')
 def test_forward_uses_inspected_facing_codes(self):
  self.assertEqual(game.forward_step({'facing':2},0),('left',100))
  self.assertEqual(game.forward_step({'facing':3},0),('up',100))
  self.assertEqual(game.forward_step({'facing':3},1),('left',100))
 def test_missing_trace_waits_then_tries_bounded_forward_as_requested(self):
  state=world([],route_type=0);state.update(facing=6,pid=123,time=datetime.now(timezone.utc).isoformat())
  calls=[];clock=[0.0]
  def now():clock[0]+=.1;return clock[0]
  def movement(direction,milliseconds,**kwargs):
   before=copy.deepcopy(state);calls.append((direction,clock[0]));state['x']+=24
   return {'before':before,'after':copy.deepcopy(state),'moved':True}
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window),patch.object(game.time,'monotonic',side_effect=now),patch.object(game.time,'sleep'):
   report=game.follow_trace(20)
  self.assertTrue(calls)
  self.assertTrue(all(direction=='right' for direction,stamp in calls))
  self.assertGreaterEqual(calls[0][1],2.5)
  self.assertEqual(report['reason'],'no_map_exit_detected')
 def test_endpoint_moves_forward_and_confirms_new_map(self):
  state=world([[5,0]]);state.update(facing=6,pid=123,time=datetime.now(timezone.utc).isoformat())
  calls=[]
  def movement(direction,milliseconds,**kwargs):
   calls.append(direction);after=copy.deepcopy(state);after.update(map='next-map',x=1)
   return {'before':copy.deepcopy(state),'after':after,'moved':False}
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td, patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=state),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window):
   report=game.follow_trace(5)
  self.assertEqual(calls,['right'])
  self.assertEqual(report['reason'],'map_changed')
  self.assertEqual(report['current']['map'],'next-map')
 def test_near_exit_aims_at_gps_endpoint_instead_of_stale_facing(self):
  state=world([[894,362]],x=887.9946,y=363.91492)
  state.update(facing=0,pid=123,time=datetime.now(timezone.utc).isoformat())
  calls=[]
  def movement(direction,milliseconds,**kwargs):
   calls.append(direction);after=copy.deepcopy(state);after.update(map='next-map',x=1)
   return {'before':copy.deepcopy(state),'after':after,'moved':False}
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',return_value=state),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window):
   report=game.follow_trace(5)
  self.assertEqual(calls,['right'])
  self.assertEqual(report['reason'],'map_changed')
 def test_tiny_wall_bump_recovers_sideways_instead_of_retrying_up(self):
  state=world([[10,-10],[20,-20]]);state.update(facing=4,pid=123,time=datetime.now(timezone.utc).isoformat())
  calls=[]
  def movement(direction,milliseconds,**kwargs):
   before=copy.deepcopy(state);calls.append(direction)
   if direction=='right':state['x']+=12
   elif direction=='up' and state['x']<8:state['y']-=.1
   else:state['map']='next-map'
   return {'before':before,'after':copy.deepcopy(state),'moved':True}
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window):
   report=game.follow_trace(5)
  self.assertEqual(calls,['up','right','up'])
  self.assertEqual(report['reason'],'map_changed')
 def test_map_transition_race_is_confirmed_by_new_state(self):
  state=world([[21,0]]);state.update(facing=6,pid=123,time=datetime.now(timezone.utc).isoformat())
  destination=copy.deepcopy(state);destination['map']='next-map'
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=[state,state,destination]),patch.object(game,'move',side_effect=RuntimeError('IllegalStateException: Map changed before movement')),patch('game_control.GameWindow',Window):
   report=game.follow_trace(5)
  self.assertEqual(report['reason'],'map_changed')
 def test_refreshed_route_can_retry_same_direction_after_failure(self):
  state=world([[0,-14],[0,-21]]);state.update(facing=4,pid=123,time=datetime.now(timezone.utc).isoformat())
  calls=[];ticks=iter(i*.1 for i in range(1000))
  def movement(direction,milliseconds,**kwargs):
   before=copy.deepcopy(state);calls.append(direction)
   if len(calls)==1:state['trace']['points']=[[0,-21],[0,-28]]
   else:state['map']='next-map'
   return {'before':before,'after':copy.deepcopy(state),'moved':False}
  class Window:
   def __init__(self,pid):pass
   def focus(self):pass
   def focused(self):return True
   def close(self):pass
  with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window),patch.object(game.time,'monotonic',side_effect=lambda:next(ticks)),patch.object(game.time,'sleep'):
   report=game.follow_trace(20)
  self.assertEqual(calls,['up','up'])
  self.assertEqual(report['reason'],'map_changed')
 def test_straight_route_uses_bounded_forward_movement(self):
  self.assertEqual(game.trace_step(world([[7,0],[14,0],[21,0],[28,0]])),('right',88))
 def test_turn_does_not_skip_the_corner(self):
  self.assertEqual(game.trace_step(world([[7,0],[14,0],[14,7],[14,14]])),('right',58))
  self.assertEqual(game.trace_step(world([[14,7],[14,14],[14,21]],14,0)),('down',175))
 def test_unusable_route_and_endpoint_stop(self):
  for state in [world([]),world([[0,0]]),world([[5,0]]),world([[7,0]],route_type=0),world([[7,0]],route_type=4),dict(phase='login')]:
   self.assertIsNone(game.trace_step(state))
 def test_near_corner_continues_along_next_segment(self):
  self.assertEqual(game.trace_step(world([[5,0],[5,7],[5,14]]))[0],'down')
 def test_stale_state_is_rejected(self):
  self.assertFalse(game.fresh_state({'time':'2000-01-01T00:00:00Z'}))
 def test_restart_starts_new_process_even_while_old_snapshot_is_fresh(self):
  with tempfile.TemporaryDirectory() as td, patch.object(game,'LATEST',Path(td)/'latest'), patch.object(game,'monitored_alive',return_value=True), patch.object(game,'request',return_value={'phase':'world'}), patch.object(game.subprocess,'Popen',side_effect=RuntimeError('new process requested')):
   with self.assertRaisesRegex(RuntimeError,'new process requested'):game.start(restart=True)
if __name__=='__main__':unittest.main(verbosity=2)
