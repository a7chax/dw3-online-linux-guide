"""Replay the filtered s655 NPC-route stall without any game connection."""
import copy
from contextlib import contextmanager,ExitStack
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


class RejectedNpcGpsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-rejected-npc-');self.addCleanup(temporary.cleanup)
        self.session=Path(temporary.name);self.clock=Clock();self.windows=Windows()
        self.recording=json.loads((Path(__file__).parent/'fixtures/s655-rejected-npc-gps.json').read_text())
        self.state=copy.deepcopy(self.recording['state']);self.state['fresh']=True
        self.state['movement_directions']=['down_right']
        self.game=Game(self.state,self.session)
        self.supervisor=autoplay.Supervisor(self.game,self.session,window_factory=self.windows,
            clock=self.clock.monotonic,sleep=self.clock.sleep)
        # Model the recorded disconnected GPS prefix at its original coordinates.
        # Keep both the filtered prefix's end and the reported NPC endpoint on
        # another island, more than the interaction range from this region.
        atlas=self.session/'atlas';atlas.mkdir();image=Image.new('L',(640,512),0)
        image.paste(255,(190,400,219,445));image.paste(255,(180,80,450,280))
        image.save(atlas/'mask.png')
        (atlas/'atlas.json').write_text(json.dumps({'maps':[dict(id='s655',width=640,height=512,collision='mask.png')]}))
        self.atlas=WorldMap('s655',atlas);self.supervisor.atlas_factory=lambda map_id:self.atlas
        self.follows=[]
        self.real_game=autoplay.load_game()
        def follow(**kwargs):
            self.follows.append(kwargs)
            return self.real_game.follow_trace(**kwargs)
        self.game.follow_trace=follow

    @contextmanager
    def isolated_follow(self):
        """Stub every game boundary while retaining real planning and guards."""
        stack=ExitStack()
        stack.enter_context(patch.object(self.real_game,'LATEST',self.session))
        stack.enter_context(patch.object(self.real_game,'request',side_effect=self.game.request))
        stack.enter_context(patch.object(self.real_game,'fresh_state',return_value=True))
        stack.enter_context(patch.object(self.real_game,'time',SimpleNamespace(
            monotonic=self.clock.monotonic,sleep=self.clock.sleep,perf_counter=self.clock.monotonic)))
        stack.enter_context(patch.object(self.real_game,'move',side_effect=AssertionError('Blocked route must send no movement')))
        stack.enter_context(patch('game_control.GameWindow',self.windows))
        stack.enter_context(patch('world_map.WorldMap',return_value=self.atlas))
        with stack:yield

    def reject_route(self):
        self.supervisor.run(max_cycles=1)
        self.assertEqual(self.follows,[{'seconds':12,'continuous':True}])
        self.assertEqual(self.supervisor.pending_recovery,self.supervisor.recovery_signature(self.state))
        self.clock.now=self.supervisor.cooldown
        self.supervisor.run(max_cycles=1)
        events=[json.loads(row) for row in (self.session/'autoplay-events.jsonl').read_text().splitlines()]
        self.assertTrue(any(row['reason']=='local_route_unavailable' for row in events))
        self.clock.now=self.supervisor.cooldown

    def test_recorded_failures_in_actual_follow_loop_send_no_movement(self):
        with self.isolated_follow():
            for failure in self.recording['failed_actions']:
                self.assertEqual(self.real_game.follow_trace(2)['reason'],failure['reason'])
        start=(self.state['x'],self.state['y'])
        for target in (self.state['trace']['points'][-1],self.state['trace']['endpoint']):
            with self.assertRaises(NoRouteError):self.atlas.interaction_destination(start,target)

    def test_rejected_npc_route_refreshes_then_resumes_following(self):
        def press(window,key):
            self.game.actions.append(('key',key));trace=self.state['trace']
            trace['enabled']=not trace['enabled']
            if trace['enabled']:
                trace['points']=[[213,420],[213,435]]
                trace['endpoint']=[213,435]
        self.game.press_game_key=press
        # A fresh reply is no longer rejected; use a movement stub to verify
        # collision-clear progress on the replacement route in the real loop.
        start=(self.state['x'],self.state['y'])
        def move(direction,milliseconds,**kwargs):
            before=copy.deepcopy(self.state);vx,vy=self.atlas._velocities()[direction]
            guard=(self.state['x']+vx*(milliseconds+17)/1000,self.state['y']+vy*(milliseconds+17)/1000)
            self.assertTrue(self.atlas.clear((before['x'],before['y']),guard))
            self.state['x']+=vx*milliseconds/1000;self.state['y']+=vy*milliseconds/1000
            return dict(before=before,after=copy.deepcopy(self.state),moved=True)
        with self.isolated_follow():
            self.reject_route();self.supervisor.run(max_cycles=1)
            self.assertEqual(self.game.actions,[('key','g'),('key','g')])
            self.assertEqual(len(self.follows),1)
            with patch.object(self.real_game,'move',side_effect=move):
                self.clock.now=self.supervisor.cooldown;self.supervisor.run(max_cycles=1)
        self.assertNotEqual((self.state['x'],self.state['y']),start)
        self.assertEqual(self.windows.focus_calls,0)

    def test_npc_route_requires_static_rejection_before_refresh(self):
        self.supervisor.state=copy.deepcopy(self.state);self.supervisor.expected_pid=self.state['pid']
        self.supervisor.ensure_window()
        with self.supervisor.guarded_actions('gps_refresh'):
            self.supervisor.gps_refresh()
        self.assertEqual(self.game.actions,[])

    def test_rejected_npc_refresh_rechecks_context_before_input(self):
        for change in ('pid','map','quest','target_map','position','route','route_type','battle','story','inn',
                       'dialogue','movement_ready','fresh'):
            with self.subTest(change=change):
                # Each variant has separate temporary state and patched boundaries.
                self.setUp()
                with self.isolated_follow():
                    self.reject_route()
                    original=self.game.request;polls=0
                    def request(operation):
                        nonlocal polls
                        polls+=1;state=original(operation)
                        if polls>=3:
                            if change=='pid':state['pid']+=1
                            elif change=='map':state['map']='s660'
                            elif change=='quest':state['main_quest']['step']+=1
                            elif change=='target_map':state['main_quest']['target_map']='s660'
                            elif change=='position':state['x']+=12
                            elif change=='route':state['trace']['points'][0][0]+=1
                            elif change=='route_type':state['trace']['route_type']=1
                            elif change in ('battle','story','inn','dialogue'):state[change]={'active':True}
                            elif change=='movement_ready':state['movement_ready']=False
                            else:state['fresh']=False
                        return state
                    self.game.request=request;self.supervisor.run(max_cycles=1)
                    self.assertFalse(any(action=='key' for action,_ in self.game.actions))

    def test_unresponsive_npc_refresh_keeps_rate_limit_and_watchdog(self):
        with self.isolated_follow():
            self.reject_route()
            self.game.press_game_key=lambda window,key:self.game.actions.append(('key',key))
            self.supervisor.run(max_cycles=15)
            self.assertEqual(self.game.actions,[('key','g')])
            self.supervisor.run(max_cycles=100)
        self.assertEqual(self.supervisor.stall_trigger['reason'],'navigation_stalled')


if __name__=='__main__':unittest.main()
