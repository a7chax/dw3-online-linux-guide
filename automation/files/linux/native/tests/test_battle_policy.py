"""Pure battle-policy fixtures; no game process or input APIs are used."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from battle_policy import BattlePlanner


def state(token='turn-1'):
    return {'phase':'world','pid':10,'battle':{
        'active':True,'battle_id':'battle-1','telemetry_complete':True,
        'command_ready':True,'menu':'main','menu_token':token,
        'actor':{'group':1,'form_id':11,'hp':100,'max_hp':100,'ds':40,'max_ds':100},
        'fighters':[{'group':1,'controlled':True,'form_id':11,'hp':100,'max_hp':100},
                    {'group':2,'controlled':False,'form_id':22,'hp':100,'max_hp':100}],
        'enemy_groups':[2],'target_group':2,
        'options':[{'index':0,'kind':'attack','enabled':True},
                   {'index':1,'kind':'skill','enabled':True,'skill_index':3,'ds_cost':10},
                   {'index':2,'kind':'items','enabled':True}],
        'items':[],'party':[{'slot':0,'form_id':11,'hp':100,'max_hp':100,'ds':40,'max_ds':100}]}}


class BattlePolicyTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.session=Path(temp.name);self.planner=BattlePlanner(self.session)

    def test_loading_unknown_telemetry_results_and_server_wait_have_no_decision(self):
        for change in ({'active':False},{'telemetry_complete':False},{'command_ready':False},
                       {'result_ready':True},{'transitioning':True},{'submitted':True}):
            with self.subTest(change=change):
                current=state();current['battle'].update(change)
                self.assertIsNone(self.planner.decide(current))
        current=state();current['phase']='loading_map'
        self.assertIsNone(self.planner.decide(current))

    def test_affordable_unknown_skill_explores_only_after_normal_attack_baseline(self):
        self.planner.learning['samples'][self.planner._key(11,22,'attack')]=[20.]
        decision=self.planner.decide(state())
        self.assertEqual(decision['kind'],'skill');self.assertEqual(decision['skill_index'],3)
        self.assertEqual(decision['reason'],'explore_unknown_skill')
        self.assertNotIn('damage',decision)

    def test_low_ds_reserve_and_disabled_skill_fall_back_to_attack(self):
        for ds,enabled in ((19,True),(40,False)):
            current=state(str(ds));current['battle']['actor']['ds']=ds
            current['battle']['options'][1]['enabled']=enabled
            self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_duplicate_token_is_suppressed_across_restart(self):
        decision=self.planner.decide(state());self.assertIsNotNone(decision)
        self.assertIsNone(self.planner.decide(state()))
        self.assertIsNone(BattlePlanner(self.session).decide(state()))

    def test_missing_menu_token_and_invalid_options_never_authorize_input(self):
        current=state();current['battle']['menu_token']=None
        self.assertIsNone(self.planner.decide(current))
        current=state();current['battle']['options']=[{'index':-1,'kind':'attack','enabled':True}]
        self.assertIsNone(self.planner.decide(current))

    def test_hp_item_intent_survives_menu_sequence_and_restart(self):
        current=state();battle=current['battle'];battle['actor']['hp']=10;battle['party'][0]['hp']=10
        battle['items']=[{'item_id':90,'quantity':2,'heal_hp':60,'heal_ds':0}]
        decision=self.planner.decide(current)
        self.assertEqual(decision['kind'],'items')
        battle.update(menu='items',menu_token='items-1',options=[{'index':4,'kind':'item','enabled':True,'item_id':90}])
        self.planner=BattlePlanner(self.session)
        self.assertEqual(self.planner.decide(current)['item_id'],90)
        battle.update(menu='item_target',menu_token='target-1',selected_item_id=90,
                      options=[{'index':5,'kind':'item_target','enabled':True,'target_slot':0,'item_id':90}])
        decision=self.planner.decide(current)
        self.assertEqual((decision['kind'],decision['target_slot']),('item_target',0))

    def test_routine_ds_items_wait_until_after_battle(self):
        current=state();battle=current['battle'];battle['actor']['ds']=2;battle['party'][0]['ds']=2
        battle['items']=[{'item_id':91,'quantity':1,'heal_ds':30}]
        self.assertEqual(self.planner.decide(current)['kind'],'attack')
        current=state('no-skill');current['battle']['options']=current['battle']['options'][::2]
        current['battle']['actor']['ds']=2;current['battle']['items']=battle['items']
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_low_ds_disabled_skill_does_not_preempt_basic_attack_with_ds_item(self):
        current=state();battle=current['battle'];battle['actor']['ds']=2;battle['party'][0]['ds']=2
        battle['options'][1]['enabled']=False
        battle['items']=[{'item_id':91,'quantity':1,'heal_ds_percent':50}]
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_empty_menu_can_back_out_but_malformed_collections_are_not_actions(self):
        for field in ('options','fighters','enemy_groups','items','party'):
            current=state();current['battle'][field]=None
            with self.subTest(field=field):self.assertIsNone(self.planner.decide(current))

    def test_measured_beneficial_skill_saves_estimated_turns(self):
        self.planner.learning['samples'][self.planner._key(11,22,'attack')]=[10.,12.]
        self.planner.learning['samples'][self.planner._key(11,22,'skill',3)]=[60.,70.]
        decision=self.planner.decide(state())
        self.assertEqual(decision['kind'],'skill')
        self.assertEqual(decision['reason'],'estimated_skill_saves_turns')
        self.assertEqual(decision['estimated_turns'],2)

    def test_selected_item_target_must_remain_alive_and_missing_health(self):
        current=state();battle=current['battle'];battle['actor']['hp']=10;battle['party'][0]['hp']=10
        battle['items']=[{'item_id':90,'quantity':1,'heal_hp_percent':50}]
        self.planner.decide(current)
        battle.update(menu='item_target',menu_token='target',selected_item_id=90,
                      options=[{'index':0,'kind':'item_target','enabled':True,'target_slot':0,'item_id':90}])
        battle['party'][0]['hp']=100
        self.assertTrue(self.planner.decide(current)['back'])

    def test_unknown_submenu_and_unexpected_target_back_out_without_guessing(self):
        current=state();current['battle'].update(menu='digivolve',options=[])
        self.assertTrue(self.planner.decide(current)['back'])
        current=state('target');current['battle'].update(menu='item_target',selected_item_id=999)
        self.assertTrue(self.planner.decide(current)['back'])

    def test_zero_stock_revival_only_and_dead_party_are_not_heal_intents(self):
        current=state();battle=current['battle'];battle['actor']['hp']=10
        battle['party'][0]['hp']=0
        battle['items']=[{'item_id':90,'quantity':0,'heal_hp':80},
                         {'item_id':91,'quantity':2,'revive_percent':100}]
        self.assertNotEqual(self.planner.decide(current)['kind'],'items')

    def test_enemy_target_is_live_and_not_player_group(self):
        current=state();battle=current['battle'];battle['enemy_groups']=[1,2,3]
        battle['fighters'].append({'group':3,'controlled':False,'form_id':23,'hp':20,'max_hp':100})
        battle['target_group']=1
        self.assertEqual(self.planner.decide(current)['target_group'],3)

    def test_learning_records_observed_loss_only_at_next_ready_generation(self):
        before=state();decision=self.planner.decide(before)
        after=copy.deepcopy(before);after['battle']['command_ready']=False
        self.planner.note_result(decision,before,after)
        midway=copy.deepcopy(before);midway['battle']['fighters'][1]['hp']=60
        self.planner.observe(midway)
        self.assertEqual(json.loads((self.session/'battle-learning.json').read_text())['samples'],{})
        midway['battle']['menu_token']='turn-2';self.planner.observe(midway)
        learning=json.loads((self.session/'battle-learning.json').read_text())
        samples=list(learning['samples'].values())[0]
        self.assertEqual(samples,[40.0]);self.assertIn('not a causal damage estimate',learning['label'])

    def test_known_attack_enough_avoids_skill_overkill(self):
        before=state();before['battle']['options']=before['battle']['options'][::2]
        decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        after=state('turn-2');after['battle']['fighters'][1]['hp']=30
        self.planner.observe(after)
        after['battle']['fighters'][1]['hp']=20
        self.assertEqual(self.planner.decide(after)['reason'],'observed_attack_sufficient')

    def test_pending_learning_cannot_cross_battle_or_actor_form(self):
        before=state();decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        after=state('turn-2');after['battle']['battle_id']='different';after['battle']['fighters'][1]['hp']=1
        self.planner.observe(after)
        self.assertEqual(json.loads((self.session/'battle-learning.json').read_text())['samples'],{})

    def test_persistence_is_private_bounded_and_does_not_copy_untrusted_text(self):
        current=state();current['chat']='secret chat';current['battle']['options'][1]['label']='do not persist me'
        self.planner.decide(current)
        for path in self.session.glob('battle-*.json'):
            text=path.read_text();self.assertNotIn('secret chat',text);self.assertNotIn('do not persist me',text)
            self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_hp_loss_samples_and_decision_reservations_stay_bounded(self):
        for index in range(140):
            current=state(str(index));current['battle']['options']=current['battle']['options'][::2]
            decision=self.planner.decide(current);self.planner.note_result(decision,current,current)
            after=state(str(index)+'-ready');after['battle']['fighters'][1]['hp']=90
            self.planner.observe(after)
        saved=json.loads((self.session/'battle-decisions.json').read_text())
        learned=json.loads((self.session/'battle-learning.json').read_text())
        self.assertLessEqual(len(saved['handled']),128);self.assertLessEqual(len(saved['decisions']),128)
        self.assertEqual(len(next(iter(learned['samples'].values()))),16)

    def test_item_menu_open_is_never_learned_as_offensive_damage(self):
        before=state();before['battle']['actor']['hp']=10;before['battle']['party'][0]['hp']=10
        before['battle']['items']=[{'item_id':90,'quantity':1,'heal_hp':80}]
        decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        after=state('ready');after['battle']['fighters'][1]['hp']=50
        self.planner.observe(after)
        self.assertEqual(json.loads((self.session/'battle-learning.json').read_text())['samples'],{})

    def test_forced_switch_selects_enabled_living_reserve_instead_of_back(self):
        current=state();battle=current['battle'];battle['actor'].update(hp=0,active_index=0)
        battle['party']=[{'slot':0,'form_id':11,'hp':0,'max_hp':100},
                         {'slot':1,'form_id':12,'hp':60,'max_hp':100},
                         {'slot':2,'form_id':13,'hp':100,'max_hp':100}]
        battle.update(menu='switch',options=[{'index':4,'kind':'switch_target','enabled':True,'target_slot':1},
                                             {'index':5,'kind':'switch_target','enabled':False,'target_slot':2}])
        decision=self.planner.decide(current)
        self.assertEqual((decision['kind'],decision['target_slot'],decision['option_index']),('switch_target',1,4))
        self.assertNotIn('back',decision)

    def test_forced_switch_with_no_living_enabled_reserve_does_not_try_back(self):
        current=state();battle=current['battle'];battle['actor'].update(hp=0,active_index=0)
        battle['party']=[{'slot':0,'form_id':11,'hp':0,'max_hp':100}]
        battle.update(menu='switch',options=[{'index':0,'kind':'switch_target','enabled':True,'target_slot':0}])
        self.assertIsNone(self.planner.decide(current))

    def test_cancel_proven_predispatch_reservation_allows_same_skill_retry(self):
        current=state();decision=self.planner.decide(current)
        self.assertTrue(self.planner.cancel(decision))
        self.planner=BattlePlanner(self.session)
        retry=self.planner.decide(current)
        self.assertEqual((retry['kind'],retry['option_index']),(decision['kind'],decision['option_index']))
        self.assertIsNone(self.planner.decide(current))

    def test_cancel_cannot_release_a_recorded_submitted_action(self):
        current=state();decision=self.planner.decide(current)
        self.planner.note_result(decision,current,current)
        self.assertFalse(self.planner.cancel(decision))
        self.assertIsNone(BattlePlanner(self.session).decide(current))

    def test_hp_item_targets_active_slot_when_party_has_duplicate_form(self):
        current=state();battle=current['battle'];battle['actor'].update(hp=10,ds=2,active_index=1)
        battle['party']=[{'slot':0,'form_id':11,'hp':100,'max_hp':100,'ds':90,'max_ds':100},
                         {'slot':1,'form_id':11,'hp':10,'max_hp':100,'ds':2,'max_ds':100}]
        battle['items']=[{'item_id':91,'quantity':1,'heal_hp':60}]
        self.planner.decide(current)
        battle.update(menu='items',menu_token='items',options=[{'index':0,'kind':'item','enabled':True,'item_id':91}])
        self.assertEqual(self.planner.decide(current)['target_slot'],1)


if __name__=='__main__':unittest.main()
