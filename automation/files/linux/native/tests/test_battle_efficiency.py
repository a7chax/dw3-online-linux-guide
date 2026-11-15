"""Offense/recovery regressions; isolated telemetry only, no game input."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from battle_policy import BattlePlanner
from linux.native.tests.test_battle_policy import state


class BattleEfficiencyTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(prefix='dw3-battle-efficiency-')
        self.addCleanup(directory.cleanup);self.session=Path(directory.name)
        self.planner=BattlePlanner(self.session)

    @staticmethod
    def configured(token='start',hp=100,ds=40,enemy_hp=100):
        current=state(token);battle=current['battle']
        battle['actor'].update(hp=hp,ds=ds,active_index=0)
        battle['party'][0].update(hp=hp,ds=ds)
        battle['fighters'][0].update(hp=hp,ds=ds,max_ds=100)
        battle['fighters'][1]['hp']=enemy_hp
        battle['items']=[{'item_id':90,'quantity':20,'heal_hp':60},
                         {'item_id':91,'quantity':20,'heal_ds':50}]
        return current

    def samples(self,kind,values,skill=None):
        key=self.planner._key(11,22,kind,skill)
        self.planner.learning['samples'][key]=list(values);self.planner._save()
        return key

    def item_menu_sequence(self):
        """Return a selected target decision; do not yet submit the item."""
        before=self.configured(hp=10)
        opening=self.planner.decide(before)
        self.assertEqual(opening['kind'],'items')
        items=copy.deepcopy(before)
        items['battle'].update(menu='items',menu_token='items',
                              options=[{'index':0,'kind':'item','enabled':True,'item_id':90}])
        self.planner.note_result(opening,before,items)
        selected=self.planner.decide(items)
        self.assertEqual(selected['kind'],'item')
        target=copy.deepcopy(items)
        target['battle'].update(menu='item_target',menu_token='target',selected_item_id=90,
                               options=[{'index':0,'kind':'item_target','enabled':True,
                                         'item_id':90,'target_slot':0}])
        self.planner.note_result(selected,items,target)
        final=self.planner.decide(target)
        self.assertEqual(final['kind'],'item_target')
        return target,final

    def test_unknown_enemy_low_ds_probes_normal_attack_before_item_or_skill_exploration(self):
        current=self.configured(ds=2)
        current['battle']['options'][1]['enabled']=False
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_conservative_normal_finisher_precedes_hp_and_ds_items(self):
        self.samples('attack',[100,120])
        current=self.configured(hp=30,ds=2,enemy_hp=20)
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_healthy_active_fights_while_bench_recovery_waits_until_after_battle(self):
        current=self.configured()
        current['battle']['party'].append({'slot':1,'form_id':12,'hp':5,'max_hp':100,'ds':0,'max_ds':100})
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_active_noncritical_hp_defers_routine_healing_and_fights(self):
        current=self.configured(hp=30)
        self.assertEqual(self.planner.decide(current)['kind'],'attack')

    def test_critical_active_can_use_one_emergency_item_without_finisher(self):
        self.samples('attack',[5,6])
        decision=self.planner.decide(self.configured(hp=10))
        self.assertEqual(decision['kind'],'items')

    def test_item_submenu_opening_is_not_a_consumed_item_streak(self):
        self.item_menu_sequence()  # No item_target submission occurred.
        next_main=self.configured('back-to-main',hp=10)
        self.assertEqual(self.planner.decide(next_main)['kind'],'items')

    def test_accepted_item_target_blocks_second_item_across_restart_until_offense(self):
        target,decision=self.item_menu_sequence()
        after=self.configured('after-heal',hp=60)
        self.planner.note_result(decision,target,after)
        self.planner=BattlePlanner(self.session)
        next_turn=self.configured('next-turn',hp=10)
        offense=self.planner.decide(next_turn)
        self.assertIn(offense['kind'],('attack','skill'))
        following=self.configured('following-turn',hp=10)
        self.planner.note_result(offense,next_turn,following)
        self.planner.learning['incoming'].clear()  # Isolate the streak from forecast affordability.
        self.assertEqual(self.planner.decide(following)['kind'],'items')

    def test_early_result_packet_waits_for_final_hp_before_learning(self):
        before=self.configured(enemy_hp=20);before['battle']['options']=[before['battle']['options'][0]]
        decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        early=copy.deepcopy(before);early['battle'].update(command_ready=False,result='victory',result_ready=False,menu_token='early-result')
        self.planner.observe(early)
        self.assertIsNotNone(self.planner.data['pending'])
        self.assertFalse(self.planner.learning['samples'])
        early['battle'].update(result_ready=True,can_advance=True)
        early['battle']['fighters'][1]['hp']=0
        self.planner.observe(early)
        self.assertTrue(self.planner.learning['kill_bounds'].get(self.planner._key(11,22,'attack')))

    def test_terminal_zero_hp_records_kill_bound_once_without_exact_damage_sample(self):
        before=self.configured(enemy_hp=20)
        before['battle']['options']=[before['battle']['options'][0]]
        decision=self.planner.decide(before);self.assertEqual(decision['kind'],'attack')
        self.planner.note_result(decision,before,before)
        terminal=copy.deepcopy(before)
        terminal['battle'].update(command_ready=False,result_ready=True,can_advance=True,menu_token='victory')
        terminal['battle']['fighters'][1]['hp']=0
        self.planner.observe(terminal)
        key=self.planner._key(11,22,'attack')
        self.assertTrue(self.planner.learning.get('kill_bounds',{}).get(key))
        self.assertFalse(self.planner.learning['samples'].get(key))
        saved=copy.deepcopy(self.planner.learning)
        self.planner.observe(terminal)
        self.assertEqual(self.planner.learning,saved)

    def test_absent_enemy_or_changed_battle_does_not_fabricate_terminal_kill(self):
        for index,change in enumerate(('absent','changed-battle')):
            with self.subTest(change=change):
                before=self.configured('before-'+str(index),enemy_hp=20)
                before['battle']['options']=[before['battle']['options'][0]]
                decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
                terminal=copy.deepcopy(before)
                terminal['battle'].update(command_ready=False,result_ready=True,menu_token='result-'+str(index))
                if change=='absent':terminal['battle']['fighters']=[]
                else:
                    terminal['battle']['battle_id']='different-battle'
                    terminal['battle']['fighters'][1]['hp']=0
                self.planner.observe(terminal)
                key=self.planner._key(11,22,'attack')
                self.assertFalse(self.planner.learning.get('kill_bounds',{}).get(key))

    def test_next_actor_rotation_preserves_original_submitter_learning(self):
        before=self.configured();before['battle']['options']=[before['battle']['options'][0]]
        decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        ready=copy.deepcopy(before);ready['battle']['menu_token']='next-actor'
        ready['battle']['actor'].update(group=3,form_id=99)
        ready['battle']['party']=[{'slot':0,'form_id':99,'hp':100,'max_hp':100,'ds':40,'max_ds':100}]
        ready['battle']['fighters'].append({'group':3,'controlled':True,'form_id':99,
                                          'hp':100,'max_hp':100,'ds':40,'max_ds':100})
        ready['battle']['fighters'][1]['hp']=80
        self.planner.observe(ready)
        original=self.planner._key(11,22,'attack')
        wrong_actor=self.planner._key(99,22,'attack')
        self.assertEqual(self.planner.learning['samples'].get(original),[20.0])
        self.assertFalse(self.planner.learning['samples'].get(wrong_actor))

    def test_known_basic_baseline_does_not_spend_skill_on_weak_enemy(self):
        self.samples('attack',[100.]);self.samples('skill',[1000],3)
        self.assertEqual(self.planner.decide(self.configured(enemy_hp=20))['kind'],'attack')

    def test_ineffective_heal_that_leaves_actor_in_predicted_danger_is_skipped(self):
        key=self.planner._key(11,22,'incoming')
        self.planner.learning['incoming'][key]=[80.]
        self.assertEqual(self.planner.decide(self.configured(hp=10))['kind'],'attack')

    def test_known_finishing_skill_can_use_ds_reserve_to_end_emergency(self):
        self.samples('attack',[5.])
        self.samples('skill',[100.],3)
        current=self.configured(hp=10,ds=10,enemy_hp=50)
        decision=self.planner.decide(current)
        self.assertEqual((decision['kind'],decision['ds_cost']),('skill',10))
        self.assertEqual(decision['reason'],'estimated_skill_finisher')

    def test_critical_actor_uses_known_finisher_instead_of_unknown_basic_probe(self):
        self.samples('skill',[100.],3)
        self.assertEqual(self.planner.decide(self.configured(hp=10,enemy_hp=50))['kind'],'skill')

    def test_observed_zero_basic_damage_allows_affordable_skill_trial(self):
        self.samples('attack',[0.,0.])
        self.assertEqual(self.planner.decide(self.configured())['kind'],'skill')

    def test_kill_bound_does_not_hide_recorded_misses(self):
        key=self.samples('attack',[0.,0.,0.])
        self.planner.learning['kill_bounds'][key]=[100.]
        decision=self.planner.decide(self.configured(enemy_hp=90))
        self.assertNotEqual(decision['reason'],'observed_attack_sufficient')

    def test_partial_telemetry_keeps_accepted_item_streak(self):
        target,decision=self.item_menu_sequence()
        self.planner.note_result(decision,target,target)
        partial=self.configured('partial',hp=10)
        partial['battle'].update(menu_token=None,command_ready=False,command_telemetry_complete=False)
        self.planner.observe(partial)
        self.assertIn(self.planner.decide(self.configured('ready',hp=10))['kind'],('attack','skill'))

    def test_partial_telemetry_keeps_pending_attack_observation(self):
        before=self.configured();before['battle']['options']=[before['battle']['options'][0]]
        decision=self.planner.decide(before);self.planner.note_result(decision,before,before)
        partial=copy.deepcopy(before);partial['battle'].update(menu_token=None,command_ready=False,command_telemetry_complete=False)
        self.planner.observe(partial)
        self.assertIsNotNone(self.planner.data['pending'])
        ready=self.configured('ready');ready['battle']['fighters'][1]['hp']=80
        self.planner.observe(ready)
        self.assertEqual(self.planner.learning['samples'].get(self.planner._key(11,22,'attack')),[20.])

    def test_old_routine_item_intent_backs_out_after_upgrade(self):
        for index,reason in enumerate(('low_ds_enables_skill','low_hp_useful_item')):
            current=self.configured('old-'+str(index),hp=10,ds=2)
            current['battle'].update(menu='items',options=[{'index':0,'kind':'item','enabled':True,'item_id':90}])
            self.planner.data['intent']={'battle':self.planner._identity(current['battle'])[0],
                'reason':reason,'item_id':90,'target_slot':0}
            self.assertTrue(self.planner.decide(current)['back'])

    def test_two_normal_hit_enemy_allows_affordable_skill_trial(self):
        self.samples('attack',[100.])
        decision=self.planner.decide(self.configured(enemy_hp=170))
        self.assertEqual(decision['kind'],'skill')
        self.assertEqual(decision['reason'],'explore_unknown_skill')

    def test_healthy_actor_uses_known_skill_finisher_before_extra_basic_probe(self):
        self.samples('skill',[200.],3)
        decision=self.planner.decide(self.configured(hp=100,enemy_hp=150))
        self.assertEqual(decision['kind'],'skill')
        self.assertEqual(decision['reason'],'estimated_skill_finisher')

    def test_known_normal_finisher_still_beats_known_skill_finisher(self):
        self.samples('attack',[100.]);self.samples('skill',[200.],3)
        self.assertEqual(self.planner.decide(self.configured(enemy_hp=80))['kind'],'attack')

    def test_mean_of_inconsistent_attack_samples_is_not_a_finisher_guarantee(self):
        self.samples('attack',[5,100])
        decision=self.planner.decide(self.configured(enemy_hp=8))
        self.assertNotEqual(decision['reason'],'observed_attack_sufficient')
        self.assertNotIn('finisher',decision['reason'])


if __name__=='__main__':unittest.main()
