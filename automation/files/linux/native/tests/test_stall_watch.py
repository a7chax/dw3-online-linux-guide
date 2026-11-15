import copy
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from stall_watch import StallWatch,sanitize_state


def world():
    return {'pid':123,'phase':'world','map':'s450','x':100.,'y':200.,'fresh':True,
            'movement_ready':True,'main_quest':{'chapter':5,'step':3,'target_map':'s375'}}


class StallTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.session=Path(temp.name);self.now=0.;self.state=world()
        self.watch=StallWatch(self.session,clock=lambda:self.now)

    def observe(self,at,reason='poll',action=None):
        self.now=at;return self.watch.observe(self.state,reason,action)

    def test_navigation_requires_three_failed_actions_and_sixty_seconds(self):
        self.observe(0)
        for at in (10,30,59):self.assertIsNone(self.observe(at,'unable_to_advance','follow'))
        self.assertEqual(self.observe(60,'unable_to_advance','follow'),'navigation_stalled')
        self.assertIsNone(self.observe(61,'unable_to_advance','follow'))

    def test_pauses_do_not_count_as_failed_navigation_actions(self):
        self.observe(0)
        for at in (20,40,60,80):
            self.assertIsNone(self.observe(at,'no_progress_backoff'))
            self.assertIsNone(self.observe(at,'unable_to_advance'))

    def test_inactive_modal_objects_do_not_hide_navigation_stall(self):
        self.state['inn']={'active':False,'telemetry_complete':True}
        self.state['story']={'active':False}
        self.observe(0)
        for at in (20,40):self.observe(at,'unable_to_advance','follow')
        self.assertEqual(self.observe(60,'unable_to_advance','follow'),'navigation_stalled')

    def test_facing_does_not_count_as_progress_but_new_cell_does(self):
        self.observe(0)
        for at in (20,40):
            self.state['facing']=at//20
            self.observe(at,'unable_to_advance','follow')
        self.state['x']=124
        self.assertIsNone(self.observe(60,'unable_to_advance','follow'))
        self.assertIsNone(self.observe(100,'unable_to_advance','follow'))
        self.assertEqual(self.observe(120,'unable_to_advance','follow'),'navigation_stalled')

    def test_repeated_spatial_loop_eventually_stalls(self):
        self.observe(0)
        self.state['x']=116;self.observe(10)
        for at in (20,40):
            self.state['x']=100 if at==20 else 116
            self.assertIsNone(self.observe(at,'unable_to_advance','navigate'))
        self.state['x']=100
        self.assertEqual(self.observe(70,'local_route_unavailable','navigate'),'navigation_stalled')

    def test_session_and_quest_changes_restart_detection(self):
        self.observe(0)
        for at in (20,40):self.observe(at,'unable_to_advance','follow')
        self.state['pid']=456
        self.assertIsNone(self.observe(70,'unable_to_advance','follow'))
        self.state['main_quest']['step']=4
        self.assertIsNone(self.observe(140,'unable_to_advance','follow'))

    def test_ineligible_conditions_never_trigger(self):
        for reason in ('focus_lost','stale_state','loading_map','session_changed','stop_requested','inn_insufficient_bit'):
            with self.subTest(reason=reason):
                self.observe(0);self.observe(30,'unable_to_advance','follow')
                self.assertIsNone(self.observe(500,reason,'follow'))
        self.state['fresh']=False
        self.assertIsNone(self.observe(1000,'unable_to_advance','follow'))

    def test_battle_space_does_not_trigger_stall(self):
        self.state['battle']={'active':True,'telemetry_complete':True,'can_advance':True}
        self.observe(0)
        for at in (60,180,400):self.assertIsNone(self.observe(at,'battle_space','space'))

    def test_repeated_battle_guard_with_completed_background_story_triggers(self):
        self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,
                              'submitted':False,'can_advance':False}
        self.state['story']={'active':True,'telemetry_complete':True,'typing':False,'can_advance':False,
                             'choice_count':0,'awaiting_choice':False,'submitted':False,'script_complete':True}
        self.observe(0)
        for at in (20,40):self.assertIsNone(self.observe(at,'modal_changed','battle_space'))
        self.assertEqual(self.observe(60,'modal_changed','battle_space'),'input_guard_stalled')

    def test_battle_transition_and_story_typing_are_not_guard_stalls(self):
        for key,modal in [('battle',{'active':True,'telemetry_complete':True,'transitioning':True,'submitted':False}),
                          ('story',{'active':True,'telemetry_complete':True,'typing':True,'choice_count':0,'can_advance':False})]:
            self.state=world();self.state[key]=modal
            self.observe(0)
            for at in (20,40,180,300):self.assertIsNone(self.observe(at,'modal_changed','space'))

    def test_complete_idle_story_requires_three_minutes(self):
        self.state['story']={'active':True,'telemetry_complete':True,'typing':False,'can_advance':True,
                             'choice_count':0,'awaiting_choice':False,'submitted':False}
        self.observe(0)
        self.assertIsNone(self.observe(179))
        self.assertEqual(self.observe(180),'story_stalled')

    def test_story_choices_typing_and_missing_metadata_wait(self):
        for changes in ({'choice_count':2},{'typing':True},{'telemetry_complete':False}):
            self.state['story']={'active':True,'telemetry_complete':True,'typing':False,'can_advance':True,
                                 'choice_count':0,'awaiting_choice':False,'submitted':False,**changes}
            self.observe(0);self.assertIsNone(self.observe(600))

    def test_story_idle_wait_without_can_advance_also_has_deadline(self):
        self.state['story']={'active':True,'telemetry_complete':True,'typing':False,'can_advance':False,
                             'choice_count':0,'awaiting_choice':False,'submitted':False,'script_complete':True}
        self.observe(0)
        self.assertEqual(self.observe(180),'story_stalled')

    def test_local_and_cached_recovery_failures_count(self):
        self.observe(0)
        self.observe(20,'local_route_unavailable','local_recovery')
        self.observe(40,'unable_to_advance','cached_recovery')
        self.assertEqual(self.observe(60,'unable_to_advance','local_recovery'),'navigation_stalled')

    def test_repeated_modal_guard_needs_ready_complete_modal(self):
        self.state['dialogue']={'typing':False,'can_advance':True,'page_index':0,'page_count':2,
                                'entity_id':4,'text_file':6,'text_index':363}
        self.observe(0)
        for at in (20,40):self.assertIsNone(self.observe(at,'modal_changed','talk'))
        self.assertEqual(self.observe(60,'modal_changed','talk'),'input_guard_stalled')

    def test_history_is_bounded_atomic_private_and_throttled(self):
        self.observe(0);self.observe(.01)
        self.assertEqual(len(self.watch.history()),1)
        for at in range(1,105):self.observe(at)
        history=self.watch.history();self.assertEqual(len(history),96)
        path=self.session/'repair-game-state.json'
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.assertEqual(json.loads(path.read_text()),history)
        history[-1]['state']['pid']=999
        self.assertEqual(self.watch.history()[-1]['state']['pid'],123)

    def test_sanitizer_keeps_only_safe_numeric_flags_and_bounded_route(self):
        state=world();state.update({'username':'SECRET','profile':'SECRET','exception':'SECRET',
            'dialogue':{'text':'SECRET','text_file':6,'text_index':363,'typing':False},
            'party':{'telemetry_complete':True,'members':[{'id':1,'hp':0,'max_hp':100,'name':'SECRET'}]},
            'trace':{'points':[[i,i] for i in range(100)],'enabled':True,'message':'SECRET'},
            'inn':{'active':True,'state':'offer','cost_bits':10,'name':'SECRET'}})
        safe=sanitize_state(state)
        self.assertNotIn('SECRET',json.dumps(safe));self.assertEqual(len(safe['trace']['points']),32)
        self.assertEqual(safe['trace']['endpoint'],[99,99])
        self.assertEqual(sanitize_state(safe),safe)
        self.state=state;self.observe(0,'SECRET','SECRET')
        self.assertNotIn('SECRET',(self.session/'repair-game-state.json').read_text())

    def test_numeric_wallet_and_facing_are_safe_history_fields(self):
        state=world();state['facing']=5;state['wallet']={'bits':50915,'cash':0,'telemetry_complete':True,'name':'SECRET'}
        safe=sanitize_state(state)
        self.assertEqual(safe['facing'],5);self.assertEqual(safe['wallet']['bits'],50915)
        self.assertNotIn('SECRET',json.dumps(safe))

    def test_malformed_untrusted_state_is_sanitized_without_errors(self):
        safe=sanitize_state({'phase':['SECRET'],'inn':{'state':['SECRET']},'pid':10**500})
        self.assertNotIn('SECRET',json.dumps(safe))
        self.assertNotIn('pid',safe)


if __name__=='__main__':unittest.main()
