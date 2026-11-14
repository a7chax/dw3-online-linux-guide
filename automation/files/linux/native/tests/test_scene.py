#!/usr/bin/env python3
"""Bounded scene input using fixtures only; no game or desktop interaction."""
import copy
from datetime import datetime,timezone
import fcntl
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('scene_game',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

def world():
    return {'phase':'world','pid':123,'map':'s475','time':datetime.now(timezone.utc).isoformat(),
            'main_quest':{'chapter':5,'step':2}}

class Clock:
    def __init__(self):self.now=0
    def sleep(self,seconds):self.now+=seconds

class Window:
    def __init__(self):
        self.pid=123;self.focus_count=0;self.is_focused=True;self.closed=False;self.screenshots=[]
    def focus(self):self.focus_count+=1;self.is_focused=True
    def focused(self):return self.is_focused
    def screenshot(self,path):self.screenshots.append(path.name);path.write_bytes(b'fixture screenshot')
    def close(self):self.closed=True

class SceneTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-scene-test-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.state=world();self.clock=Clock();self.window=Window()
        self.presses=[];self.after_press=lambda:None
        def press(window,key):
            self.assertIs(window,self.window);self.assertEqual(key,'space')
            self.presses.append(self.clock.now);self.after_press()
        patches=[patch.object(game,'LATEST',self.root),
                 patch.object(game,'request',side_effect=lambda op:copy.deepcopy(self.state)),
                 patch.object(game,'press_game_key',side_effect=press),
                 patch.object(game.time,'monotonic',side_effect=lambda:self.clock.now),
                 patch.object(game.time,'sleep',side_effect=self.clock.sleep),
                 patch('game_control.GameWindow',return_value=self.window)]
        for replacement in patches:
            replacement.start();self.addCleanup(replacement.stop)

    def test_valid_quest_change_stops_after_one_press_and_saves_evidence(self):
        self.after_press=lambda:self.state['main_quest'].update(step=3)
        report=game.scene(5,5)
        self.assertEqual(report['reason'],'quest_progressed');self.assertEqual(report['presses'],1)
        self.assertEqual(report['before']['main_quest']['step'],2)
        self.assertEqual(report['current']['main_quest']['step'],3)
        self.assertEqual(json.loads((self.root/'scene-state.json').read_text()),report)
        self.assertEqual(self.window.screenshots,['before-scene.png','after-scene.png'])
        self.assertEqual(self.window.focus_count,1);self.assertTrue(self.window.closed)

    def test_initial_state_requires_fresh_world_and_valid_quest_baseline(self):
        for replacement in ({'main_quest':None},{'main_quest':{'chapter':5,'step':None}},
                            {'phase':'loading_map'},{'time':'2000-01-01T00:00:00Z'},
                            {'pid':None},{'map':None}):
            with self.subTest(replacement=replacement):
                self.state=world();self.state.update(replacement)
                with self.assertRaises(RuntimeError):game.scene(5,5)
        self.assertEqual(self.presses,[]);self.assertEqual(self.window.focus_count,0)

    def test_invalid_or_stale_progress_never_reports_advancement(self):
        for replacement,reason in (({'main_quest':None},'invalid_quest_state'),
                ({'main_quest':{'chapter':5,'step':None}},'invalid_quest_state'),
                ({'time':'2000-01-01T00:00:00Z','main_quest':{'chapter':5,'step':3}},'stale_state'),
                ({'phase':'loading_map','main_quest':None},'screen_changed')):
            with self.subTest(reason=reason,replacement=replacement):
                self.state=world();self.presses.clear()
                self.after_press=lambda:self.state.update(replacement)
                report=game.scene(5,5)
                self.assertEqual(report['reason'],reason);self.assertEqual(len(self.presses),1)

    def test_map_change_stops_before_another_press(self):
        self.after_press=lambda:self.state.update(map='s465')
        report=game.scene(5,5)
        self.assertEqual(report['reason'],'map_changed');self.assertEqual(len(self.presses),1)

    def test_session_change_stops_before_another_press(self):
        self.after_press=lambda:self.state.update(pid=456)
        report=game.scene(5,5)
        self.assertEqual(report['reason'],'session_changed');self.assertEqual(len(self.presses),1)

    def test_focus_loss_stops_without_refocusing(self):
        self.after_press=lambda:setattr(self.window,'is_focused',False)
        report=game.scene(5,5)
        self.assertEqual(report['reason'],'focus_lost');self.assertEqual(len(self.presses),1)
        self.assertEqual(self.window.focus_count,1);self.assertTrue(self.window.closed)

    def test_press_limit_and_one_second_spacing_are_enforced(self):
        report=game.scene(5,2)
        self.assertEqual(report['reason'],'press_limit');self.assertEqual(len(self.presses),2)
        self.assertGreaterEqual(self.presses[1]-self.presses[0],1)

    def test_time_limit_stops_even_when_press_budget_remains(self):
        report=game.scene(.5,30)
        self.assertEqual(report['reason'],'time_limit');self.assertEqual(len(self.presses),1)
        self.assertLessEqual(self.clock.now,.5)

    def test_navigation_lease_prevents_concurrent_scene_input(self):
        with (self.root/'navigation.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,'already running'):game.scene(5,5)
        self.assertEqual(self.presses,[]);self.assertEqual(self.window.focus_count,0)

    def test_scene_cli_uses_explicit_bounds(self):
        with patch.object(sys,'argv',['ai-game.py','scene','--seconds','8','--max-presses','3']),patch.object(game,'scene',create=True) as scene:
            game.main()
        scene.assert_called_once_with(8,3)

if __name__=='__main__':unittest.main(verbosity=2)
