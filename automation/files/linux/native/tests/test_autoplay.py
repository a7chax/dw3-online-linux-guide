#!/usr/bin/env python3
"""Supervisor policy and ownership fixtures; never start or control a game."""
from contextlib import contextmanager,redirect_stdout
import copy
import fcntl
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('autoplay_test_module',ROOT/'autoplay.py')
autoplay=importlib.util.module_from_spec(spec);spec.loader.exec_module(autoplay)

def world():
    return {'phase':'world','pid':123,'map':'s450','x':100.,'y':200.,'facing':6,'fresh':True,
            'movement_ready':True,'main_quest':{'chapter':5,'step':3,'target_map':'s375'},
            'trace':{'enabled':True,'route_type':1,'steps_remaining':50,'points':[[200,200],[400,200]]}}

class Clock:
    def __init__(self):self.now=0.
    def sleep(self,seconds):self.now+=seconds
    def monotonic(self):return self.now

class Windows:
    def __init__(self):self.focused=True;self.focus_calls=0
    def __call__(self,pid):
        owner=self
        class Window:
            def __init__(self):self.pid=pid
            def focus(self):owner.focus_calls+=1;owner.focused=True
            def focused(self):return owner.focused
            def close(self):pass
        return Window()

class Game:
    def __init__(self,state,session):
        self.state=state;self.LATEST=session;self.actions=[];self.after_action=lambda:None
    def request(self,operation):return copy.deepcopy(self.state)
    def fresh_state(self,state):return state.get('fresh',False)
    def _quest_step(self,state):
        progress=state.get('main_quest') or {}
        pair=(progress.get('chapter'),progress.get('step'))
        return pair if all(type(v) is int and v>0 for v in pair) else None
    def describe_quest(self,state):
        return {**state['main_quest'],'required_action':state.get('required_action','talk'),
                'on_target_map':state['map']==state['main_quest']['target_map'],
                'definition_matches_state':True}
    @contextmanager
    def navigation_lease(self):yield
    def follow_trace(self,**kwargs):
        self.actions.append(('follow',kwargs));self.after_action()
        return {'reason':'unable_to_advance' if self.state.get('blocked') else 'time_limit','current':copy.deepcopy(self.state)}
    def talk(self,**kwargs):
        self.actions.append(('talk',kwargs));self.after_action()
        return {'reason':'dialogue_closed','current':copy.deepcopy(self.state)}
    def move(self,direction,milliseconds,**kwargs):
        before=copy.deepcopy(self.state)
        self.actions.append(('move',{'direction':direction,'milliseconds':milliseconds,**kwargs}));self.after_action()
        return {'before':before,'after':copy.deepcopy(self.state),'moved':before!=self.state}
    def scene(self,**kwargs):
        self.actions.append(('scene',kwargs));self.after_action()
        return {'reason':'press_limit','current':copy.deepcopy(self.state)}
    def press_game_key(self,window,key):
        self.actions.append(('key',key))
        self.state['trace']['enabled']=not self.state['trace']['enabled']

class AutoplayTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='dw3-autoplay-test-');self.addCleanup(temp.cleanup)
        self.session=Path(temp.name);self.clock=Clock();self.windows=Windows();self.state=world()
        self.game=Game(self.state,self.session)
        self.supervisor=autoplay.Supervisor(self.game,self.session,window_factory=self.windows,
            clock=self.clock.monotonic,sleep=self.clock.sleep)
    def events(self):
        return [json.loads(line) for line in (self.session/'autoplay-events.jsonl').read_text().splitlines()]

    def test_default_policy_follows_only_a_usable_route(self):
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions[0][0],'follow')
        self.assertTrue(self.game.actions[0][1]['continuous'])
        report=json.loads((self.session/'autoplay-state.json').read_text())
        self.assertFalse(report['active']);self.assertEqual(report['reason'],'max_cycles')
        self.assertEqual(report['game_pid'],123)

    def test_default_automation_prioritizes_inn_for_fainted_reserve(self):
        from linux.native.tests.test_inn_recovery import state,Router
        health=state();self.state.update({k:health[k] for k in ('party','wallet','inn','native_inn_recovery')})
        router=Router();self.supervisor.inn_recovery.router_factory=lambda:router
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('follow',{'seconds':12,'destination':(50,60),'cross_map':True})])
        self.assertTrue(self.supervisor.inn_recovery.pending)

    def test_inn_offer_uses_normal_space_only_with_affordable_stay(self):
        from linux.native.tests.test_inn_recovery import state
        health=state();self.state.update({k:health[k] for k in ('party','wallet','native_inn_recovery')})
        self.state['movement_ready']=False
        self.state['inn']={'active':True,'telemetry_complete':True,'state':'offer','cost_bits':50,
                           'selected_option':0,'can_confirm':True,'submitted':False}
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('key','space')])
        self.assertTrue(self.supervisor.inn_recovery.report()['stay_sent'])

    def test_popup_closer_does_not_cancel_an_active_inn_offer(self):
        self.state['inn']={'active':True,'state':'offer'};self.supervisor.state=copy.deepcopy(self.state)
        self.game.ROOT=self.session;template=self.session/'linux/ui/popup-close.png'
        template.parent.mkdir(parents=True);template.write_bytes(b'fixture')
        with patch.object(self.game,'request',side_effect=AssertionError('An inn offer must not enter popup dismissal')):
            self.assertFalse(self.supervisor.close_known_popup())

    def test_unavailable_local_route_uses_recovery_backoff_without_repair(self):
        signature=self.supervisor.recovery_signature(self.state)
        self.supervisor.pending_recovery=signature
        def follow(**kwargs):
            self.game.actions.append(('follow',kwargs))
            return {'reason':'local_route_unavailable','current':copy.deepcopy(self.state)}
        self.game.follow_trace=follow
        with patch.object(self.supervisor,'maybe_repair',side_effect=AssertionError('No route is not a controller failure')):
            self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('follow',{'seconds':15,'destination':(400,200),'cross_map':True})])
        self.assertEqual(self.supervisor.failed_recoveries[signature],60)
        self.assertIsNone(self.supervisor.pending_recovery)
        self.assertTrue(any(event['reason']=='local_route_unavailable' for event in self.events()))
        self.assertFalse(any(event['reason']=='action_failed' for event in self.events()))

    def test_npc_local_recovery_uses_reachable_standoff_without_crossing_map(self):
        self.state['trace']['route_type']=2
        signature=self.supervisor.recovery_signature(self.state);self.supervisor.pending_recovery=signature
        class Atlas:
            def __init__(self,map_id):pass
            def interaction_destination(self,start,goal):return (388,200)
        self.supervisor.atlas_factory=Atlas
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('follow',{'seconds':15,'destination':(388,200),'cross_map':False,'interaction_target':(400,200)})])

    def test_close_npc_uses_actual_distance_when_gps_step_counter_is_stale(self):
        self.state.update(x=390.,y=200.,facing=6)
        self.state['trace'].update(route_type=2,steps_remaining=4)
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions[0][0],'talk')

    def test_missing_npc_approach_is_navigation_backoff_not_code_repair(self):
        from world_map import NoRouteError
        self.state['trace']['route_type']=2
        signature=self.supervisor.recovery_signature(self.state);self.supervisor.pending_recovery=signature
        class Atlas:
            def __init__(self,map_id):pass
            def interaction_destination(self,start,goal):raise NoRouteError('No reachable talking position')
        self.supervisor.atlas_factory=Atlas
        with patch.object(self.supervisor,'maybe_repair',side_effect=AssertionError('Expected navigation failure needs no code worker')):
            self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])
        self.assertEqual(self.supervisor.failed_recoveries[signature],60)
        self.assertTrue(any(event['reason']=='local_route_unavailable' for event in self.events()))

    def test_login_stale_and_unknown_action_pause_without_input(self):
        for changes in ({'phase':'login'},{'fresh':False},{'required_action':'unknown'}):
            with self.subTest(changes=changes):
                self.state.clear();self.state.update(world());self.state.update(changes)
                self.game.actions.clear();self.supervisor.run(max_cycles=2)
                self.assertEqual(self.game.actions,[])
        self.assertGreaterEqual(self.clock.now,3)

    def test_normal_dialogue_and_nearby_interaction_use_talk(self):
        for dialogue in (True,False):
            with self.subTest(dialogue=dialogue):
                self.state.clear();self.state.update(world());self.game.actions.clear()
                if dialogue:self.state['dialogue']={'can_advance':True,'page_index':0,'page_count':2}
                else:self.state['trace'].update(route_type=2,steps_remaining=1,points=[[110,200]])
                self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions[0][0],'talk')

    def test_focus_loss_pauses_without_reclaiming_it(self):
        self.game.after_action=lambda:setattr(self.windows,'focused',False)
        self.supervisor.run(max_cycles=3)
        self.assertEqual(len(self.game.actions),1);self.assertEqual(self.windows.focus_calls,1)
        self.assertTrue(any(event['reason']=='focus_lost' for event in self.events()))

    def test_background_controller_runs_unfocused_without_activating_window(self):
        self.state['native_background_input']=True;self.windows.focused=False
        self.game.after_action=lambda:self.state.update(x=self.state['x']+10)
        self.supervisor.run(max_cycles=3)
        self.assertEqual(len(self.game.actions),3)
        self.assertEqual(self.windows.focus_calls,0)
        self.assertFalse(self.windows.focused)
        self.assertFalse(any(event['reason']=='focus_lost' for event in self.events()))

    def test_background_mode_still_rejects_changed_pid(self):
        self.state['native_background_input']=True;self.windows.focused=False
        self.game.after_action=lambda:self.state.update(pid=456)
        self.supervisor.run(max_cycles=3)
        self.assertEqual(len(self.game.actions),1)
        self.assertEqual(self.windows.focus_calls,0)
        self.assertTrue(any(event['reason']=='session_changed' for event in self.events()))

    def test_changed_pid_never_receives_input(self):
        self.game.after_action=lambda:self.state.update(pid=456)
        self.supervisor.run(max_cycles=3)
        self.assertEqual(len(self.game.actions),1)
        self.assertTrue(any(event['reason']=='session_changed' for event in self.events()))

    def test_repeated_no_progress_backs_off(self):
        self.supervisor.run(max_cycles=6)
        self.assertLess(len(self.game.actions),6)
        self.assertGreaterEqual(self.clock.now,5)
        self.assertTrue(any(event['reason']=='no_progress_backoff' for event in self.events()))

    def test_stop_file_and_singleton_prevent_input(self):
        (self.session/'autoplay.stop').touch();self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])
        (self.session/'autoplay.stop').unlink()
        with (self.session/'autoplay.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,'already running'):self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])

    def test_empty_gps_waits_then_refreshes_with_cooldown_without_walking(self):
        self.state['trace'].update(route_type=0,points=[])
        self.supervisor.run(max_cycles=35)
        self.assertFalse(any(action[0]=='follow' for action in self.game.actions))
        self.assertEqual([action for action in self.game.actions if action[0]=='key'],[('key','g'),('key','g')])

    def test_refresh_second_g_requires_confirmed_disabled_state(self):
        self.state['trace'].update(route_type=0,points=[])
        def unchanged(window,key):self.game.actions.append(('key',key))
        self.game.press_game_key=unchanged
        self.supervisor.run(max_cycles=15)
        self.assertEqual(self.game.actions,[('key','g')])

    def test_navigation_failure_tries_full_atlas_route_to_endpoint(self):
        self.state['blocked']=True
        self.supervisor.run(max_cycles=6)
        local=[kwargs for action,kwargs in self.game.actions if action=='follow' and 'destination' in kwargs]
        self.assertEqual(len(local),1);self.assertEqual(local[0]['destination'],(400,200));self.assertTrue(local[0]['cross_map'])

    def test_story_choice_and_battle_pause_but_verified_ready_space_is_allowed(self):
        cases=[({'story':{'active':True,'telemetry_complete':False,'can_advance':False}},None),
               ({'story':{'active':True,'telemetry_complete':True,'awaiting_choice':True,'choice_count':2,'can_advance':False}},None),
               ({'story':{'active':True,'telemetry_complete':True,'can_advance':True}},'scene'),
               ({'battle':{'active':True,'result_ready':False}},None),
               ({'battle':{'active':True,'result_ready':True,'can_advance':True,'telemetry_complete':True}},'scene')]
        for changes,expected in cases:
            with self.subTest(changes=changes):
                self.state.clear();self.state.update(world());self.state.update(changes);self.game.actions.clear()
                self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions[0][0] if self.game.actions else None,expected)

    def test_enter_objective_does_not_blindly_press_scene(self):
        self.state.update(map='s375',required_action='enter',movement_ready=False)
        self.state['trace'].update(route_type=0,points=[])
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])

    def test_space_rechecks_modal_immediately_before_input(self):
        initial={'active':True,'can_advance':True,'telemetry_complete':True}
        for modal in ('battle','story'):
            for replacement in ({'active':True,'can_advance':False,'telemetry_complete':True},
                    {'active':True,'can_advance':True,'telemetry_complete':False},None):
                with self.subTest(modal=modal,replacement=replacement):
                    self.state.clear();self.state.update(world());self.state[modal]=dict(initial)
                    self.game.actions.clear()
                    def stale_scene(**kwargs):
                        self.state[modal]=replacement
                        self.game.press_game_key(self.supervisor.window,'space')
                        return {'reason':'press_limit','current':copy.deepcopy(self.state)}
                    self.game.scene=stale_scene
                    self.supervisor.run(max_cycles=1)
                    self.assertEqual(self.game.actions,[])
        self.assertTrue(any(event['reason']=='modal_changed' for event in self.events()))

    def test_talk_cannot_send_space_after_a_battle_starts(self):
        self.state['dialogue']={'can_advance':True,'page_index':0,'page_count':2}
        def interrupted_talk(**kwargs):
            self.state['battle']={'active':True,'can_advance':False,'telemetry_complete':True}
            self.game.press_game_key(self.supervisor.window,'space')
        self.game.talk=interrupted_talk
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])

    def test_action_window_focus_only_checks_and_never_reclaims_it(self):
        def lost_focus(**kwargs):
            import game_control
            self.windows.focused=False
            window=game_control.GameWindow(123)
            window.focus()
        self.game.follow_trace=lost_focus
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.windows.focus_calls,1);self.assertEqual(self.game.actions,[])

    def test_stop_request_interrupts_the_next_internal_status_poll(self):
        def stopped_action(**kwargs):
            (self.session/'autoplay.stop').touch()
            self.game.request('status')
        self.game.follow_trace=stopped_action
        report=self.supervisor.run(max_cycles=10)
        self.assertEqual(report['reason'],'stop_requested');self.assertEqual(self.game.actions,[])

    def test_paused_login_does_not_persist_credential_fields(self):
        self.state.update(phase='login',username='private-user',password='private-password')
        self.supervisor.run(max_cycles=1)
        output=(self.session/'autoplay-state.json').read_text()+(self.session/'autoplay-events.jsonl').read_text()
        self.assertNotIn('private-user',output);self.assertNotIn('private-password',output)

    def test_fresh_ready_modal_allows_exactly_one_space(self):
        for modal in ('battle','story'):
            with self.subTest(modal=modal):
                self.state.clear();self.state.update(world());self.game.actions.clear()
                self.state[modal]={'active':True,'telemetry_complete':True,'can_advance':True,'choice_count':0}
                def press(window,key):
                    self.game.actions.append(('key',key));self.state[modal]={'active':False}
                def ready_scene(**kwargs):
                    self.game.press_game_key(self.supervisor.window,'space')
                    return {'reason':'press_limit','current':copy.deepcopy(self.state)}
                self.game.press_game_key=press;self.game.scene=ready_scene
                self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions,[('key','space')])

    def test_status_and_stop_cli_never_load_game_controls(self):
        (self.session/'autoplay-state.json').write_text('{"active": true}\n')
        with patch.object(autoplay,'load_game',side_effect=AssertionError('Control loading is forbidden')):
            output=io.StringIO()
            with patch.object(sys,'argv',['autoplay.py','--session',str(self.session),'--status']),redirect_stdout(output):
                autoplay.main()
            self.assertTrue(json.loads(output.getvalue())['active'])
            output=io.StringIO()
            with patch.object(sys,'argv',['autoplay.py','--session',str(self.session),'--stop']),redirect_stdout(output):
                autoplay.main()
            self.assertTrue(json.loads(output.getvalue())['stop_requested'])
            self.assertTrue((self.session/'autoplay.stop').exists())

    def station_target(self):
        self.state.update(map='s440',x=447.629,y=289.56,facing=3)
        self.state['trace'].update(route_type=2,steps_remaining=1,points=[[463,280]])

    def test_station_interaction_aligns_up_right_once_then_talks(self):
        self.station_target()
        def aligned():
            if self.game.actions[-1][0]=='move':self.state.update(x=452.699,y=287.026,facing=5)
        self.game.after_action=aligned
        self.supervisor.run(max_cycles=2)
        self.assertEqual([name for name,_ in self.game.actions],['move','talk'])
        step=self.game.actions[0][1]
        self.assertEqual((step['direction'],step['milliseconds']),('up_right',50))
        self.assertFalse(step['focus']);self.assertEqual(step['expected_map'],'s440')

    def test_close_correctly_facing_interaction_does_not_push_into_target(self):
        self.state.update(x=456,y=280,facing=6)
        self.state['trace'].update(route_type=2,steps_remaining=1,points=[[463,280]])
        self.supervisor.run(max_cycles=1)
        self.assertEqual([name for name,_ in self.game.actions],['talk'])

    def test_collision_boundary_with_correct_facing_allows_talk_within_24(self):
        self.station_target();self.state['facing']=5
        self.supervisor.run(max_cycles=3)
        self.assertEqual([name for name,_ in self.game.actions],['move','talk'])

    def test_identical_failed_alignment_is_not_repeated_every_cycle(self):
        self.station_target()
        self.supervisor.run(max_cycles=6)
        self.assertEqual([name for name,_ in self.game.actions],['move'])

    def test_ready_story_pages_do_not_use_navigation_backoff(self):
        self.state['story']={'active':True,'can_advance':True,'telemetry_complete':True,
                             'choice_count':0,'submitted':False}
        # Text pages can change while the character, quest and map stay fixed.
        self.supervisor.run(max_cycles=6)
        self.assertEqual(len(self.game.actions),6)

    def test_alignment_rechecks_readiness_before_moving(self):
        self.station_target();request=self.game.request;polls=0
        def blocked(operation):
            nonlocal polls
            polls+=1
            if polls>1:self.state['movement_ready']=False
            return request(operation)
        self.game.request=blocked
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[])

    def test_battle_space_is_explicit_and_transition_still_waits(self):
        self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'can_advance':False,'submitted':False}
        quest=self.game.describe_quest(self.state)
        self.assertEqual(autoplay.policy(self.state,quest),(None,'battle_wait'))
        self.assertEqual(autoplay.policy(self.state,quest,battle_space=True),('space','battle_input_ready'))
        self.state['battle']['transitioning']=True
        self.assertEqual(autoplay.policy(self.state,quest,battle_space=True),(None,'battle_wait'))

    def test_enabled_combat_space_rechecks_modal_and_presses_once(self):
        self.supervisor.battle_space=True
        self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'can_advance':False,'submitted':False}
        def combat_space(**kwargs):
            self.assertEqual(kwargs,{'seconds':1,'max_presses':1})
            self.game.press_game_key(self.supervisor.window,'space')
            return {'reason':'press_limit','current':copy.deepcopy(self.state)}
        self.game.scene=combat_space
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('key','space')])
        saved=json.loads((self.session/'autoplay-state.json').read_text())
        self.assertTrue(saved['battle_space_enabled']);self.assertFalse(saved['codex_repair_enabled'])

    def test_completed_background_story_does_not_block_active_battle(self):
        self.supervisor.battle_space=True
        self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'can_advance':False,'submitted':False}
        self.state['story']={'active':True,'telemetry_complete':True,'script_complete':True,
                             'typing':False,'awaiting_choice':False,'choice_count':0,'submitted':False}
        def combat(**kwargs):
            self.game.press_game_key(self.supervisor.window,'space')
            return {'reason':'press_limit','current':copy.deepcopy(self.state)}
        self.game.scene=combat
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('key','space')])

    def test_battle_does_not_confirm_unfinished_or_choice_story(self):
        self.supervisor.battle_space=True
        for change in ({'script_complete':False},{'awaiting_choice':True},{'choice_count':2},{'telemetry_complete':False}):
            with self.subTest(change=change):
                self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'can_advance':False,'submitted':False}
                self.state['story']={'active':True,'telemetry_complete':True,'script_complete':True,
                                     'typing':False,'awaiting_choice':False,'choice_count':0,'submitted':False,**change}
                self.game.actions.clear()
                def combat(**kwargs):self.game.press_game_key(self.supervisor.window,'space')
                self.game.scene=combat;self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions,[])

    def test_battle_space_cannot_press_after_battle_closes_or_transitions(self):
        self.supervisor.battle_space=True
        for replacement in (None,{'active':True,'telemetry_complete':True,'transitioning':True,'can_advance':False}):
            with self.subTest(replacement=replacement):
                self.game.actions.clear();self.state.clear();self.state.update(world())
                self.state['battle']={'active':True,'telemetry_complete':True,'transitioning':False,'can_advance':False,'submitted':False}
                def changed_combat(**kwargs):
                    self.state['battle']=replacement
                    self.game.press_game_key(self.supervisor.window,'space')
                self.game.scene=changed_combat
                self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions,[])

    def test_unavailable_window_pauses_without_requesting_code_repair(self):
        from game_control import WindowUnavailable
        from unittest.mock import Mock
        self.supervisor.repair_manager=Mock()
        def unavailable(**kwargs):raise WindowUnavailable('Restore window')
        self.game.follow_trace=unavailable
        self.supervisor.run(max_cycles=3)
        self.supervisor.repair_manager.observe.assert_not_called()
        self.assertTrue(any(event['reason']=='window_unavailable' for event in self.events()))

    def test_known_popup_is_closed_before_navigation(self):
        from PIL import Image
        directory=self.session/'linux/ui';directory.mkdir(parents=True)
        Image.new('RGB',(20,20)).save(directory/'popup-close.png')
        self.game.ROOT=self.session
        self.state['native_click_input']=True
        matches=iter([(20,30),None])
        self.game.find_popup_close=lambda image:next(matches)
        self.game.click_game=lambda window,x,y:self.game.actions.append(('click',(x,y)))
        factory=self.supervisor.window_factory
        def window(pid):
            result=factory(pid)
            result.screenshot=lambda path:Image.new('RGB',(80,60)).save(path)
            return result
        self.supervisor.window_factory=window
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('click',(20,30))])
        self.assertTrue(any(event['reason']=='popup_closed' for event in self.events()))

    def test_slow_background_capture_revalidates_before_popup_click(self):
        from PIL import Image
        self.state.update(native_background_input=True,native_click_input=True)
        self.windows.focused=False
        self.game.ROOT=self.session;directory=self.session/'linux/ui';directory.mkdir(parents=True)
        Image.new('RGB',(20,20)).save(directory/'popup-close.png')
        self.game.request=lambda operation:{**copy.deepcopy(self.state),'observed_at':self.clock.now}
        self.game.fresh_state=lambda state:self.clock.now-state.get('observed_at',-100)<3
        self.game._quest_step=lambda state:Game._quest_step(self.game,state) if self.game.fresh_state(state) else None
        matches=iter([(20,30),None]);self.game.find_popup_close=lambda image:next(matches)
        def click(window,x,y):
            self.game.request('status')  # Exercise the guarded freshness/context poll.
            self.game.actions.append(('click',(x,y)))
        self.game.click_game=click
        factory=self.supervisor.window_factory
        def window(pid):
            result=factory(pid)
            def capture(path):
                self.clock.sleep(4);Image.new('RGB',(80,60)).save(path)
            result.screenshot=capture;return result
        self.supervisor.window_factory=window
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('click',(20,30))])
        self.assertEqual(self.windows.focus_calls,0)
        self.assertTrue(any(event['reason']=='popup_closed' for event in self.events()))

    def test_popup_click_rejects_modal_change_during_capture_or_final_poll(self):
        from PIL import Image
        self.game.ROOT=self.session;directory=self.session/'linux/ui';directory.mkdir(parents=True)
        Image.new('RGB',(20,20)).save(directory/'popup-close.png')
        factory=self.supervisor.window_factory
        for stage in ('capture','final_poll'):
            with self.subTest(stage=stage):
                self.state.clear();self.state.update(world());self.state.update(native_background_input=True,native_click_input=True)
                self.game.actions.clear();self.supervisor.last_popup_check=-100
                self.game.find_popup_close=lambda image:(20,30)
                def click(window,x,y):
                    if stage=='final_poll':self.state['battle']={'active':True}
                    self.game.request('status')
                    self.game.actions.append(('click',(x,y)))
                self.game.click_game=click
                def window(pid):
                    result=factory(pid)
                    def capture(path):
                        if stage=='capture':self.state['battle']={'active':True}
                        Image.new('RGB',(80,60)).save(path)
                    result.screenshot=capture;return result
                self.supervisor.window_factory=window
                self.supervisor.run(max_cycles=1)
                self.assertEqual(self.game.actions,[])

    def post_battle_without_gps(self,route_type=1,endpoint=(400,200)):
        self.state['trace'].update(route_type=route_type,points=[[200,200],list(endpoint)],steps_remaining=50)
        self.supervisor.run(max_cycles=1)
        self.state['battle']={'active':True,'telemetry_complete':True,'can_advance':False}
        self.supervisor.run(max_cycles=1)
        self.state.pop('battle')
        self.state['trace'].update(route_type=0,points=[],steps_remaining=0,has_reply=False)
        self.game.actions.clear()

    def test_post_battle_refreshes_immediately_then_uses_cached_atlas_destination(self):
        class Atlas:
            def __init__(self,map_id):pass
            def path(self,start,goal):return [list(start),list(goal)]
        self.supervisor.atlas_factory=Atlas
        self.post_battle_without_gps()
        started=self.clock.now
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('key','g'),('key','g')])
        self.assertLess(self.clock.now-started,3)
        self.supervisor.run(max_cycles=4)
        local=[kw for action,kw in self.game.actions if action=='follow' and 'destination' in kw]
        self.assertTrue(local);self.assertEqual(local[0]['destination'],(400,200));self.assertTrue(local[0]['cross_map'])

    def test_post_battle_npc_recovery_stops_short_and_then_talks(self):
        class Atlas:
            def __init__(self,map_id):pass
            def path(self,start,goal):return [list(start),list(goal)]
            def interaction_destination(self,start,goal):return (goal[0]-12,goal[1])
        self.supervisor.atlas_factory=Atlas
        self.post_battle_without_gps(route_type=2,endpoint=(240,200))
        def approach(**kwargs):
            self.game.actions.append(('follow',kwargs));self.state['x'],self.state['y']=kwargs['destination']
            return {'reason':'destination_reached','current':copy.deepcopy(self.state)}
        self.game.follow_trace=approach
        self.supervisor.run(max_cycles=7)
        local=[kw for action,kw in self.game.actions if action=='follow']
        self.assertTrue(local);self.assertFalse(local[0]['cross_map'])
        self.assertLess(local[0]['destination'][0],240)
        self.assertTrue(any(action=='talk' for action,_ in self.game.actions))

    def test_post_battle_cache_never_replays_other_map_or_quest_target(self):
        for change in ({'map':'different-map'},{'main_quest':{'chapter':5,'step':4,'target_map':'s375'}},
                       {'main_quest':{'chapter':5,'step':3,'target_map':'different-target'}},{'pid':456}):
            with self.subTest(change=change):
                self.state.clear();self.state.update(world());self.game.actions.clear()
                self.post_battle_without_gps();self.state.update(change)
                self.supervisor.run(max_cycles=5)
                self.assertFalse(any(action=='follow' for action,_ in self.game.actions))

    def test_post_battle_invalid_atlas_destination_never_sends_movement(self):
        class BlockedAtlas:
            def __init__(self,map_id):pass
            def path(self,start,goal):raise RuntimeError('Destination is blocked')
        self.supervisor.atlas_factory=BlockedAtlas
        self.post_battle_without_gps();self.supervisor.run(max_cycles=7)
        self.assertFalse(any(action=='follow' for action,_ in self.game.actions))
        self.assertTrue(any(event['reason']=='cached_route_blocked' for event in self.events()))

    def test_unreachable_cached_route_backs_off_instead_of_replanning_every_second(self):
        class BlockedAtlas:
            calls=0
            def __init__(self,map_id):pass
            def path(self,start,goal):
                BlockedAtlas.calls+=1;raise RuntimeError('No static route')
        self.supervisor.atlas_factory=BlockedAtlas
        self.post_battle_without_gps();self.supervisor.run(max_cycles=12)
        self.assertEqual(BlockedAtlas.calls,1)

    def test_known_route_survives_supervisor_restart_during_battle(self):
        self.state['trace'].update(route_type=1,points=[[200,200],[400,200]])
        self.supervisor.run(max_cycles=1)
        self.state['battle']={'active':True,'telemetry_complete':True,'can_advance':False}
        self.supervisor.run(max_cycles=1)
        self.supervisor=autoplay.Supervisor(self.game,self.session,window_factory=self.windows,
            clock=self.clock.monotonic,sleep=self.clock.sleep)
        self.state.pop('battle');self.state['trace'].update(route_type=0,points=[],steps_remaining=0,has_reply=False)
        self.game.actions.clear();self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions,[('key','g'),('key','g')])
        self.assertTrue(self.supervisor.cached_route)

    def test_cached_route_rechecks_map_after_atlas_planning(self):
        owner=self
        class ChangingAtlas:
            def __init__(self,map_id):pass
            def path(self,start,goal):
                owner.state['map']='other-map'
                return [list(start),list(goal)]
        self.supervisor.atlas_factory=ChangingAtlas
        self.post_battle_without_gps()
        def fresh_follow(**kwargs):
            self.game.request('status')
            self.game.actions.append(('follow',kwargs))
            return {'reason':'time_limit','current':copy.deepcopy(self.state)}
        self.game.follow_trace=fresh_follow
        self.supervisor.run(max_cycles=7)
        self.assertFalse(any(action=='follow' for action,_ in self.game.actions))

if __name__=='__main__':unittest.main(verbosity=2)
