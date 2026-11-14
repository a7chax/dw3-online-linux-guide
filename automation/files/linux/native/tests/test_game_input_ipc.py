from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import sys,unittest
from unittest.mock import patch,call

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ipc_game',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

class Window:
    pid=123
    def focused(self):return True
    def __getattr__(self,name):raise AssertionError('Desktop input API must not be accessed: '+name)

def world():
    return {'phase':'world','pid':123,'map':'s370','time':datetime.now(timezone.utc).isoformat(),
            'native_key_input':['space','enter','g','x'],'native_click_input':True}

class InputTests(unittest.TestCase):
    def test_space_and_enter_use_game_ipc_without_desktop_injection(self):
        for key,native in [('space','space'),('Return','enter'),('g','g'),('x','x')]:
            with self.subTest(key=key),patch.object(game,'request',side_effect=[world(),{}]) as request:
                game.press_game_key(Window(),key)
                self.assertEqual(request.call_args_list,[call('status'),call('press_key',key=native,milliseconds=120,expected_map='s370',expected_pid=123)])

    def test_old_bridge_requires_restart_without_host_fallback(self):
        state=world();state.pop('native_key_input')
        with patch.object(game,'request',return_value=state) as request:
            with self.assertRaisesRegex(RuntimeError,'[Rr]ebuild|[Rr]estart'):game.press_game_key(Window(),'space')
        self.assertEqual(request.call_args_list,[call('status')])

    def test_changed_process_or_stale_state_sends_no_key(self):
        for changed in [{'pid':456},{'time':'2000-01-01T00:00:00Z'},{'phase':'login'}]:
            state=world();state.update(changed)
            with self.subTest(changed=changed),patch.object(game,'request',return_value=state) as request:
                with self.assertRaises(RuntimeError):game.press_game_key(Window(),'space')
                self.assertEqual(request.call_args_list,[call('status')])

    def test_popup_click_uses_game_ipc(self):
        self.assertTrue(hasattr(game,'click_game'),'Game-only popup click is missing')
        with patch.object(game,'request',side_effect=[world(),{}]) as request:
            game.click_game(Window(),20,30)
            self.assertEqual(request.call_args_list,[call('status'),call('click',x=20,y=30,expected_map='s370',expected_pid=123)])

    def test_legacy_login_uses_the_bridge_instead_of_typing_credentials(self):
        spec=importlib.util.spec_from_file_location('legacy_login',ROOT/'login-ai-game.py')
        legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
        self.assertTrue(hasattr(legacy,'game'),'Legacy login still uses desktop keyboard input')
        with patch.object(sys,'argv',['login-ai-game.py','--username','fixture-user','--character','fixture-character']),patch.object(legacy.game,'login') as login:
            legacy.main()
        login.assert_called_once_with(username='fixture-user',server=None,character='fixture-character',use_filled=False)

if __name__=='__main__':unittest.main()
