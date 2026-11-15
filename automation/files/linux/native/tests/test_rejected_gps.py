"""Replay the filtered s650 stall with isolated state, masks and input stubs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from linux.native.tests.test_autoplay import autoplay,Clock,Game,Windows
from world_map import WorldMap,NoRouteError


class RejectedGpsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-rejected-gps-');self.addCleanup(temporary.cleanup)
        self.session=Path(temporary.name);self.clock=Clock();self.windows=Windows();self.windows.focused=False
        self.recording=json.loads((Path(__file__).parent/'fixtures/s650-rejected-gps.json').read_text())
        self.state=copy.deepcopy(self.recording['state']);self.state['fresh']=True
        self.game=Game(self.state,self.session)
        self.supervisor=autoplay.Supervisor(self.game,self.session,window_factory=self.windows,
            clock=self.clock.monotonic,sleep=self.clock.sleep)
        # Minimal disconnected regions at the recorded coordinates. The GPS
        # prefix crosses blocked terrain; its endpoint is on another island.
        atlas=self.session/'atlas';atlas.mkdir();image=Image.new('L',(768,768),0)
        image.paste(255,(293,326,421,368));image.paste(255,(280,130,340,215));image.save(atlas/'mask.png')
        (atlas/'atlas.json').write_text(json.dumps({'maps':[dict(id='s650',width=768,height=768,collision='mask.png')]}))
        self.atlas=WorldMap('s650',atlas)
        self.failed=[]
        def follow(**kwargs):
            self.game.actions.append(('follow',kwargs))
            if 'destination' in kwargs:
                try:self.atlas.path((self.state['x'],self.state['y']),kwargs['destination'])
                except NoRouteError:return dict(reason='local_route_unavailable',current=copy.deepcopy(self.state))
            step=self.atlas.steering_step((self.state['x'],self.state['y']),self.state['trace']['points'][-1],
                self.state['trace']['points'])
            if step is None:
                self.failed.append('unable_to_advance')
                return dict(reason='unable_to_advance',current=copy.deepcopy(self.state))
            vx,vy=self.atlas._velocities()[step[0]];ms=step[1]
            guard=(self.state['x']+vx*(ms+17)/1000,self.state['y']+vy*(ms+17)/1000)
            self.assertTrue(self.atlas.clear((self.state['x'],self.state['y']),guard))
            self.state['x']+=vx*ms/1000;self.state['y']+=vy*ms/1000
            return dict(reason='time_limit',current=copy.deepcopy(self.state))
        self.game.follow_trace=follow

    def reject_route(self):
        self.supervisor.run(max_cycles=1)
        self.clock.now=self.supervisor.cooldown
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.game.actions[-1][1]['destination'],(310.,150.))
        self.assertEqual(self.supervisor.reason,'max_cycles')
        self.clock.now=self.supervisor.cooldown

    def test_recorded_nonempty_unreachable_route_refreshes_then_makes_clear_progress(self):
        self.assertEqual([r['reason'] for r in self.recording['failed_actions']],['unable_to_advance']*3)
        position=(self.state['x'],self.state['y']);self.reject_route()
        def press(window,key):
            self.game.actions.append(('key',key));trace=self.state['trace']
            trace['enabled']=not trace['enabled']
            if trace['enabled']:trace['points']=[[370,340],[390,340]]
        self.game.press_game_key=press
        self.supervisor.run(max_cycles=1)
        self.assertEqual([a for a in self.game.actions if a[0]=='key'],[('key','g'),('key','g')])
        self.clock.now=self.supervisor.cooldown
        self.supervisor.run(max_cycles=1)
        self.assertNotEqual((self.state['x'],self.state['y']),position)
        self.assertEqual(self.failed,['unable_to_advance'])
        self.assertEqual(self.windows.focus_calls,0)

    def test_saturated_movement_backoff_does_not_starve_rejected_route_refresh(self):
        self.supervisor.no_progress=6
        self.reject_route()
        self.game.press_game_key=lambda window,key:self.game.actions.append(('key',key))
        self.supervisor.run(max_cycles=1)
        self.assertEqual([a for a in self.game.actions if a[0]=='key'],[('key','g')])

    def test_saturated_backoff_preserves_refresh_rate_and_local_recovery_exclusion(self):
        self.supervisor.no_progress=6
        self.supervisor.run(max_cycles=1)
        self.clock.now=self.supervisor.cooldown
        rejected_at=self.clock.now;self.supervisor.last_refresh=rejected_at-5
        self.supervisor.run(max_cycles=1)
        signature=self.supervisor.recovery_signature(self.state)
        self.assertEqual(self.supervisor.failed_recoveries[signature],rejected_at+60)
        self.assertEqual(self.supervisor.cooldown,rejected_at+25)
        self.game.press_game_key=lambda window,key:self.game.actions.append(('key',key))
        self.clock.now=rejected_at+24;self.supervisor.run(max_cycles=1)
        self.assertFalse(any(a[0]=='key' for a in self.game.actions))
        self.supervisor.run(max_cycles=1)
        self.assertEqual([a for a in self.game.actions if a[0]=='key'],[('key','g')])
        self.assertEqual(self.supervisor.failed_recoveries[signature],rejected_at+60)

    def test_recorded_stall_in_actual_follow_loop_sends_no_unsafe_movement(self):
        game=autoplay.load_game();self.state['movement_directions']=['down_right']
        with patch.object(game,'LATEST',self.session),patch.object(game,'request',side_effect=self.game.request),\
             patch.object(game,'fresh_state',return_value=True),\
             patch.object(game,'time',SimpleNamespace(monotonic=self.clock.monotonic,sleep=self.clock.sleep,perf_counter=self.clock.monotonic)),\
             patch.object(game,'move',side_effect=AssertionError('Blocked route must send no movement')) as move,\
             patch('game_control.GameWindow',self.windows),patch('world_map.WorldMap',return_value=self.atlas):
            for failure in self.recording['failed_actions']:
                self.assertEqual(game.follow_trace(2)['reason'],failure['reason'])
            self.assertEqual(game.follow_trace(2,destination=(310,150),cross_map=True)['reason'],'local_route_unavailable')
        move.assert_not_called();self.assertEqual(self.windows.focus_calls,0)

    def test_nonempty_route_without_static_rejection_cannot_be_refreshed(self):
        self.supervisor.state=copy.deepcopy(self.state);self.supervisor.expected_pid=self.state['pid']
        self.supervisor.ensure_window()
        with self.supervisor.guarded_actions('gps_refresh'):
            self.supervisor.gps_refresh()
            with self.assertRaises(autoplay.InputPaused):self.game.press_game_key(self.supervisor.window,'g')
        self.assertEqual(self.game.actions,[])

    def test_rejected_route_refresh_rechecks_context_before_first_key(self):
        for change in ('pid','map','quest','target_map','position','route','battle','story','inn','dialogue',
                       'movement_ready','background_capability','fresh'):
            with self.subTest(change=change):
                self.setUp();self.reject_route()
                original=self.game.request;polls=0
                def request(operation):
                    nonlocal polls
                    polls+=1
                    # Cycle policy and gps_refresh see the rejected route;
                    # the final key guard must reject a changed snapshot.
                    state=original(operation)
                    if polls>=3:
                        if change=='pid':state['pid']+=1
                        elif change=='map':state['map']='s655'
                        elif change=='quest':state['main_quest']['step']+=1
                        elif change=='target_map':state['main_quest']['target_map']='s660'
                        elif change=='position':state['x']+=12
                        elif change=='route':state['trace']['points'][0][0]+=1
                        elif change in ('battle','story','inn','dialogue'):state[change]={'active':True}
                        elif change=='movement_ready':state['movement_ready']=False
                        elif change=='background_capability':state['native_background_input']=False
                        else:state['fresh']=False
                    return state
                self.game.request=request
                self.supervisor.run(max_cycles=1)
                self.assertFalse(any(a[0]=='key' for a in self.game.actions))

    def test_unresponsive_refresh_keeps_existing_thirty_second_rate_limit(self):
        self.reject_route()
        self.game.press_game_key=lambda window,key:self.game.actions.append(('key',key))
        self.supervisor.run(max_cycles=15)
        self.assertEqual([a for a in self.game.actions if a[0]=='key'],[('key','g')])

    def test_persistent_failure_still_revalidates_atlas_and_triggers_watchdog(self):
        self.reject_route()
        self.game.press_game_key=lambda window,key:self.game.actions.append(('key',key))
        self.supervisor.run(max_cycles=100)
        local=[options for action,options in self.game.actions if action=='follow' and 'destination' in options]
        self.assertGreaterEqual(len(local),2)
        self.assertEqual(self.supervisor.stall_trigger['reason'],'navigation_stalled')


if __name__=='__main__':unittest.main()
