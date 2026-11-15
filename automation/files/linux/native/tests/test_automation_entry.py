"""One-command setup uses fixture files and fake actions only."""
from contextlib import contextmanager
import fcntl
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('automation_entry_test',ROOT/'automation.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)

def world():
    return {'phase':'world','pid':123,'map':'fixture','native_key_input':['space','enter','g','x'],
            'native_click_input':True,'native_background_input':True,'native_capture':True,'native_inn_recovery':True,'native_battle_control':True,'native_supplies_control':True}

class EntryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-entry-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        for name in ('app/client.jar','DW3-Online.apk','linux/native/build.py',
                     'linux/native/build-executable.sh','linux/native/src/Fixture.java',
                     'linux/lib/dw3-android-bridge.jar','linux/runtime/bin/java','DW3-Online-Linux'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            os.utime(path,(10,10))
        self.session=self.root/'linux/ai-sessions/session.fixture';self.session.mkdir(parents=True)
        self.game=Mock();self.game.LATEST=self.session
        self.game.request.return_value=world();self.game.login.return_value=world()
        self.game.fresh_state.side_effect=lambda state:state.get('phase')=='world'
        self.game.login_settings.return_value={'username':'fixture-user','character':'fixture-character','password':'fixture-secret'}
        @contextmanager
        def lease():yield
        self.game.navigation_lease=lease
        self.supervisor=Mock();self.supervisor.restart_requested=False;self.supervisor.run.return_value={'reason':'max_cycles'}
        self.factory=Mock(return_value=self.supervisor);self.runner=Mock()
        self.window=Mock();self.window_factory=Mock(return_value=self.window)
    def run_entry(self,**kwargs):
        return entry.run(root=self.root,game=self.game,supervisor_factory=self.factory,
                         runner=self.runner,which=lambda name:'/tools/'+name,window_factory=self.window_factory,**kwargs)
    def test_existing_world_needs_no_build_and_starts_all_approved_features(self):
        self.run_entry(max_cycles=3)
        self.runner.assert_not_called();self.game.login_settings.assert_not_called()
        self.game.login.assert_called_once_with(restart=False)
        options=self.factory.call_args.kwargs
        self.assertTrue(options['battle_space']);self.assertTrue(options['repair_with_codex']);self.assertTrue(options['close_popups'])
        self.assertEqual(options['expected_pid'],123);self.supervisor.run.assert_called_once_with(3)
    def test_missing_or_newer_bridge_rebuilds_and_restarts_once(self):
        for missing in (True,False):
            with self.subTest(missing=missing):
                bridge=self.root/'linux/lib/dw3-android-bridge.jar'
                if missing:bridge.unlink()
                else:
                    bridge.write_bytes(b'fixture');os.utime(bridge,(10,10))
                    os.utime(self.root/'linux/native/src/Fixture.java',(20,20))
                self.runner.reset_mock();self.game.login.reset_mock()
                self.run_entry(max_cycles=1)
                self.assertEqual(self.runner.call_args.args[0],['/tools/uv','run','--locked','python','linux/native/build.py'])
                self.game.login.assert_called_once_with(restart=True)
    def test_old_loaded_input_capability_triggers_bridge_restart(self):
        self.game.request.return_value={'phase':'world','pid':123,'map':'fixture'}
        self.run_entry(max_cycles=1)
        self.assertEqual(self.runner.call_count,1);self.game.login.assert_called_once_with(restart=True)
    def test_foreground_only_bridge_is_upgraded_for_minimized_operation(self):
        self.game.request.return_value={**world(),'native_background_input':False}
        self.run_entry(max_cycles=1)
        self.assertEqual(self.runner.call_count,1);self.game.login.assert_called_once_with(restart=True)
    def test_missing_party_inn_capability_is_upgraded_automatically(self):
        self.game.request.return_value={**world(),'native_inn_recovery':False}
        self.run_entry(max_cycles=1)
        self.assertEqual(self.runner.call_count,1);self.game.login.assert_called_once_with(restart=True)
    def test_missing_tactical_capability_upgrades_loaded_bridge(self):
        self.game.request.return_value={**world(),'native_battle_control':False}
        self.run_entry(max_cycles=1)
        self.assertEqual(self.runner.call_count,1);self.game.login.assert_called_once_with(restart=True)

    def test_missing_executable_or_runtime_builds_native_launcher(self):
        (self.root/'linux/runtime/bin/java').unlink()
        self.run_entry(max_cycles=1)
        self.assertEqual(self.runner.call_args.args[0],['/tools/bash','linux/native/build-executable.sh'])
    def test_existing_controller_is_focused_without_build_or_second_supervisor(self):
        self.game.request.return_value={**world(),'native_background_input':False}
        with (self.session/'autoplay.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=self.run_entry(max_cycles=1)
        self.assertTrue(result['already_running']);self.window.focus.assert_called_once();self.window.close.assert_called_once()
        self.runner.assert_not_called();self.game.login.assert_not_called();self.factory.assert_not_called()
    def test_background_existing_controller_does_not_restore_or_focus_window(self):
        self.game.request.return_value={**world(),'native_background_input':True,'native_capture':True}
        with (self.session/'autoplay.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=self.run_entry()
        self.assertTrue(result['already_running']);self.window_factory.assert_not_called()
        self.factory.assert_not_called();self.runner.assert_not_called()
    def test_missing_identity_stops_before_build_or_login(self):
        self.game.request.side_effect=OSError('No monitored client')
        self.game.login_settings.return_value={'username':'','character':'','password':None}
        with self.assertRaisesRegex(RuntimeError,'DW3_USERNAME.*DW3_CHARACTER'):self.run_entry()
        self.runner.assert_not_called();self.game.login.assert_not_called()
    def test_opt_out_flags_reach_supervisor(self):
        self.run_entry(max_cycles=1,battle_space=False,repair_with_codex=False)
        self.assertFalse(self.factory.call_args.kwargs['battle_space']);self.assertFalse(self.factory.call_args.kwargs['repair_with_codex'])
    def test_status_and_stop_delegate_without_setup_or_login(self):
        for option in ('--status','--stop'):
            with self.subTest(option=option),patch.object(sys,'argv',['automation.py',option]),patch.object(entry,'run',side_effect=AssertionError('Setup is forbidden')),patch.object(entry.autoplay,'main') as control:
                entry.main();control.assert_called_once()

if __name__=='__main__':unittest.main()
