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
  sup=self.supervisor(combat());sup.run(max_cycles=1)
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
 def test_battle_choice_rejects_map_change_before_native_dispatch(self):
  sup=self.supervisor(combat());sup.state=copy.deepcopy(self.state);sup.expected_pid=123;sup.ensure_window()
  decision={'option_index':1,'expected_token':'menu1','battle_id':'b7','kind':'skill','target_group':1}
  self.state['map']='s455'
  with self.assertRaises(autoplay.InputPaused):sup.perform_battle_action(decision)
  self.assertEqual(self.game.actions,[])
