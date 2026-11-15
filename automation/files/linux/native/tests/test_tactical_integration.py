"""Persistent entry uses guarded native choices, not blind combat Space."""
import copy
from pathlib import Path
import tempfile,unittest
from linux.native.tests.test_autoplay import autoplay,Clock,Game,Windows,world
from linux.native.tests.test_supplies_recovery import state as supplies_state

def combat():
 s=world();s['native_battle_control']=True;s['movement_ready']=False;s['native_background_input']=True
 s['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'submitted':False,'can_advance':False,
  'command_ready':True,'battle_id':'b7','menu_token':'menu1','menu':'main','target_group':1,'enemy_groups':[1],
  'actor':{'group':0,'form_id':7,'hp':100,'max_hp':100,'ds':50,'max_ds':50},
  'fighters':[{'group':0,'form_id':7,'hp':100,'max_hp':100,'ds':50,'max_ds':50,'controlled':True},
              {'group':1,'form_id':9,'hp':100,'max_hp':100,'ds':10,'max_ds':10,'controlled':False}],
  'party':[],'items':[],
  'options':[{'index':0,'kind':'attack','enabled':True}, {'index':1,'kind':'skill','skill_index':0,'ds_cost':5,'enabled':True}]}
 return s
class TacticalIntegrationTests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.session=Path(temp.name);self.clock=Clock();self.windows=Windows()
 def supervisor(self,state):
  self.state=state;self.game=Game(state,self.session)
  original=self.game.request
  def request(op,**kwargs):
   if op in ('battle_choose','battle_back'):
    self.game.actions.append((op,kwargs));before=copy.deepcopy(state);state['battle']['command_ready']=False
    return {'before':before,'after':copy.deepcopy(state)}
   if op=='supplies_step':
    self.game.actions.append((op,kwargs));return {'plan':{'key':'i','submit':False},'after':copy.deepcopy(state)}
   return original(op)
  self.game.request=request
  return autoplay.Supervisor(self.game,self.session,clock=self.clock.monotonic,sleep=self.clock.sleep,window_factory=self.windows,battle_space=True)
 def test_complete_battle_uses_affordable_skill_native_choice(self):
  sup=self.supervisor(combat())
  sup.battle_planner.learning['samples'][sup.battle_planner._key(7,9,'attack')]=[20.]
  sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'battle_choose');self.assertEqual(self.game.actions[0][1]['option_index'],1)
  self.assertEqual(self.game.actions[0][1]['expected_token'],'menu1');self.assertFalse(any(a[0]=='scene' for a in self.game.actions))
 def test_blocking_story_does_not_consume_battle_menu_token(self):
  s=combat();s['story']={'active':True,'telemetry_complete':True,'script_complete':False,'typing':True}
  sup=self.supervisor(s);sup.run(max_cycles=1);self.assertEqual(self.game.actions,[])
  s.pop('story');sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'battle_choose')
 def test_server_wait_does_not_fall_back_to_attack_space(self):
  s=combat();s['battle']['command_ready']=False
  sup=self.supervisor(s);sup.run(max_cycles=2);self.assertEqual(self.game.actions,[])
 def test_supplies_item_steps_run_inside_full_automation(self):
  s=world();s.update(supplies_state());s['main_quest']={'chapter':5,'step':3,'target_map':'s375'}
  sup=self.supervisor(s);sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'supplies_step');self.assertEqual(self.game.actions[0][1]['mode'],'use')
  self.assertEqual(self.game.actions[0][1]['item_id'],10)
 def test_routine_heal_runs_after_battle_then_navigation_resumes(self):
  s=world();s.update(supplies_state());s['main_quest']={'chapter':5,'step':3,'target_map':'s375'}
  s['supplies']['party'][0].update(hp=50,ds=50)
  for item in s['supplies']['inventory']:item['quantity']=5
  sup=self.supervisor(s);original=self.game.request
  def request(op,**kwargs):
   if op!='supplies_step':return original(op,**kwargs)
   self.game.actions.append((op,kwargs))
   if kwargs['mode']=='close':
    s['supplies']['inventory_open']=False;plan={'key':'i','submit':False}
   elif not s['supplies']['inventory_open']:
    s['supplies']['inventory_open']=True;plan={'key':'i','submit':False}
   else:
    s['supplies']['party'][0]['hp']=100;s['supplies']['inventory'][0]['quantity']-=1
    plan={'key':'space','submit':True}
   return {'plan':plan,'after':copy.deepcopy(s)}
  self.game.request=request;sup.run(max_cycles=5)
  self.assertEqual([a[0] for a in self.game.actions[:4]],['supplies_step']*3+['follow'])
  self.assertEqual(s['supplies']['party'][0]['hp'],100)
  self.assertIsNone(sup.supplies_recovery.use)

 def test_unreachable_inn_resumes_main_quest_with_living_party(self):
  from world_map import NoRouteError
  class Missing:
   def plan(self,*args,**kwargs):raise NoRouteError('No link')
  current=world();current.update(native_inn_recovery=True,inn={'active':False},nearby_inns=[],
   party={'telemetry_complete':True,'count':2,'members':[{'id':1,'hp':100,'max_hp':100},{'id':2,'hp':0,'max_hp':100}]})
  sup=self.supervisor(current);sup.inn_recovery.router_factory=Missing
  sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'follow')
  self.assertTrue(sup.inn_recovery.report()['deferred'])

 def test_confirmed_defeat_is_saved_before_result_acknowledgement(self):
  s=combat();s['battle'].update(result='defeat',result_ready=True,can_advance=True,command_ready=False)
  sup=self.supervisor(s);sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'scene')
  self.assertEqual(sup.fishing_goal.report()['losses'],1)
  self.assertEqual(sup.fishing_goal.report()['mode'],'diverlake_fishing')

 def test_fishing_goal_overrides_main_quest_and_inn_travel(self):
  s=world();sup=self.supervisor(s)
  sup.fishing_goal.saved.update(mode='diverlake_fishing',losses=1)
  sup.fishing_goal.decide=lambda state:{'action':None,'reason':'fishing_route_unavailable'}
  sup.inn_recovery.decide=lambda state:{'action':'inn_travel','reason':'travel_to_closest_inn'}
  sup.run(max_cycles=1)
  self.assertEqual(self.game.actions,[])
  import json
  events=[json.loads(line) for line in (self.session/'autoplay-events.jsonl').read_text().splitlines()]
  self.assertTrue(any(e['reason']=='fishing_route_unavailable' for e in events))

 def test_fishing_travel_uses_bounded_guarded_local_destination(self):
  s=world();sup=self.supervisor(s);sup.fishing_goal.saved.update(mode='diverlake_fishing',losses=1)
  sup.fishing_goal.decide=lambda state:{'action':'fishing_travel','reason':'travel_to_diverlake',
   'map':state['map'],'destination':(80,90),'cross_map':True}
  sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0],('follow',{'seconds':12,'destination':(80,90),'cross_map':True}))

 def test_lake_uses_guarded_fishing_rpc_without_battle_space(self):
  s=world();s.update(map='s380',x=590.,y=519.,native_fishing_control=True)
  s['fishing']={'telemetry_complete':True,'can_cast':True,'state_token':'cast-1'}
  sup=self.supervisor(s);sup.fishing_goal.saved.update(mode='diverlake_fishing',losses=1)
  original=self.game.request
  def request(op,**kwargs):
   if op=='fishing_step':
    self.game.actions.append((op,kwargs));s['fishing']['can_cast']=False
    return {'plan':{'key':'space','reason':'fishing_cast'},'after':copy.deepcopy(s)}
   return original(op,**kwargs)
  self.game.request=request;sup.run(max_cycles=1)
  self.assertEqual(self.game.actions[0][0],'fishing_step')
  args=self.game.actions[0][1]
  self.assertEqual(args['mode'],'cast');self.assertEqual(args['expected_state_token'],'cast-1')
  self.assertEqual(args['expected_map'],'s380');self.assertEqual(args['expected_pid'],123)
  self.assertEqual(args['expected_quest'],{'chapter':5,'step':3})

 def test_changed_fishing_readiness_blocks_dispatch(self):
  s=world();s.update(map='s380',x=590.,y=519.,native_fishing_control=True)
  s['fishing']={'telemetry_complete':True,'can_cast':True,'state_token':'cast-1'}
  sup=self.supervisor(s);sup.fishing_goal.saved.update(mode='diverlake_fishing',losses=1)
  sup.state=copy.deepcopy(s);sup.expected_pid=123;sup.ensure_window()
  s['fishing']['can_cast']=False
  with self.assertRaises(autoplay.InputPaused):sup.perform_fishing_action('fishing_cast')
  self.assertEqual(self.game.actions,[])

 def test_fishing_travel_stops_on_server_fishing_spot(self):
  s=world();s.update(map='s380',native_fishing_control=True)
  s['fishing']={'telemetry_complete':True,'at_spot':True}
  sup=self.supervisor(s);sup.fishing_goal.saved.update(mode='diverlake_fishing',losses=1)
  sup.state=copy.deepcopy(s);sup.expected_pid=123;sup.ensure_window()
  with self.assertRaisesRegex(autoplay.InputPaused,'fishing_spot_detected'):
   with sup.guarded_actions('fishing_travel'):self.game.request('status')
  self.assertEqual(self.game.actions,[])

 def test_battle_choice_rejects_map_change_before_native_dispatch(self):
  sup=self.supervisor(combat());sup.state=copy.deepcopy(self.state);sup.expected_pid=123;sup.ensure_window()
  decision={'option_index':1,'expected_token':'menu1','battle_id':'b7','kind':'skill','target_group':1}
  self.state['map']='s455'
  with self.assertRaises(autoplay.InputPaused):sup.perform_battle_action(decision)
  self.assertEqual(self.game.actions,[])
