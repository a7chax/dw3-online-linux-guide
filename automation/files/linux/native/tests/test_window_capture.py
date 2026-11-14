import ctypes as C
import base64
from contextlib import nullcontext,redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('capture_control',ROOT/'game-control.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)

class CaptureTests(unittest.TestCase):
    def native_game(self,**changes):
        from PIL import Image
        output=io.BytesIO();Image.new('RGB',(40,30),(20,40,60)).save(output,format='PNG')
        state={'pid':123,'native_background_input':True,'native_capture':True,'window_focused':False,'fresh':True}
        state.update(changes)
        result={'pid':123,'width':40,'height':30,'png_base64':base64.b64encode(output.getvalue()).decode('ascii')}
        def request(operation,**parameters):return dict(state) if operation=='status' else dict(result)
        game=SimpleNamespace(request=Mock(side_effect=request),fresh_state=lambda value:value.get('fresh',False))
        return game,state,result

    def test_native_constructor_and_capture_never_access_x11_or_focus(self):
        game,state,result=self.native_game()
        with patch.object(control,'_native_control',return_value=game,create=True),patch.object(control,'find_window',side_effect=AssertionError('X11 inventory forbidden')),patch.object(control.C,'CDLL',side_effect=AssertionError('X11 library forbidden')):
            window=control.GameWindow(123)
            self.assertFalse(window.focused());window.focus()
            with tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'capture.png';window.screenshot(output)
                from PIL import Image
                with Image.open(output) as image:self.assertEqual(image.size,(40,30))
            self.assertEqual((window.width,window.height),(40,30));window.close()
        game.request.assert_any_call('capture',expected_pid=123)

    def test_native_capture_rejects_changed_pid_without_x11_fallback(self):
        game,state,result=self.native_game()
        with patch.object(control,'_native_control',return_value=game,create=True),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')):
            window=control.GameWindow(123);state['pid']=456
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(RuntimeError):window.screenshot(Path(directory)/'capture.png')
        self.assertFalse(any(call.args[0]=='capture' for call in game.request.call_args_list))

    def test_native_capture_rejects_stale_state_or_lost_capability(self):
        for change in ({'fresh':False},{'native_capture':False},{'native_background_input':False}):
            with self.subTest(change=change):
                game,state,result=self.native_game()
                with patch.object(control,'_native_control',return_value=game,create=True),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')):
                    window=control.GameWindow(123);state.update(change)
                    with tempfile.TemporaryDirectory() as directory:
                        with self.assertRaises(RuntimeError):window.screenshot(Path(directory)/'capture.png')

    def test_native_capture_validates_reply_pid_dimensions_and_png(self):
        for change in ({'pid':456},{'width':41},{'png_base64':'invalid image'}):
            with self.subTest(change=change):
                game,state,result=self.native_game()
                with patch.object(control,'_native_control',return_value=game,create=True),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')):
                    window=control.GameWindow(123);result.update(change)
                    with tempfile.TemporaryDirectory() as directory:
                        path=Path(directory)/'capture.png'
                        with self.assertRaises(RuntimeError):window.screenshot(path)
                        self.assertFalse(path.exists())

    def test_legacy_constructor_keeps_x11_path_without_native_capability(self):
        game,state,result=self.native_game(native_capture=False)
        with patch.object(control,'_native_control',return_value=game,create=True),patch.object(control.GameWindow,'_init_x11',create=True) as initialize,patch.object(control,'find_window',side_effect=AssertionError('Unexpected live inventory')):
            window=control.GameWindow(123)
        initialize.assert_called_once();self.assertFalse(window.native_capture)

    def test_native_tap_uses_allowlisted_game_keys_without_x11(self):
        game,state,result=self.native_game();game.press_game_key=Mock(return_value={'ok':True})
        game.navigation_lease=Mock(side_effect=lambda:nullcontext())
        with patch.object(control,'_native_control',return_value=game),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')):
            window=control.GameWindow(123)
            window.tap('space');window.tap('Return')
            with self.assertRaises(RuntimeError):window.tap('ctrl+space')
        self.assertEqual(game.press_game_key.call_args_list[0].args,(window,'space'))
        self.assertEqual(game.press_game_key.call_args_list[1].args,(window,'enter'))
        self.assertEqual(game.navigation_lease.call_count,2)

    def test_native_raw_keys_and_credential_typing_fail_without_x11(self):
        game,state,result=self.native_game()
        with patch.object(control,'_native_control',return_value=game),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')):
            window=control.GameWindow(123)
            for operation in (lambda:window.key_event('space',True),lambda:window.code('space'),lambda:window.type_text('private-fixture')):
                with self.assertRaisesRegex(RuntimeError,'ai-game.py'):operation()

    def test_native_cli_move_uses_bounded_pid_map_guarded_ipc(self):
        game,state,result=self.native_game();game.navigation_lease=Mock(side_effect=lambda:nullcontext())
        game.move=Mock(return_value={'moved':True});world={'pid':123,'phase':'world','map':'s205'}
        with patch.object(control,'_native_control',return_value=game),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')),patch.object(control,'read_state',return_value=world),patch.object(sys,'argv',['game-control.py','move','right','--seconds','0.05']),redirect_stdout(io.StringIO()):
            control.main()
        game.move.assert_called_once_with('right',50,focus=False,quiet=True,expected_map='s205',expected_pid=123)
        game.navigation_lease.assert_called_once()

    def test_native_cli_typing_rejects_before_password_prompt(self):
        game,state,result=self.native_game()
        with patch.object(control,'_native_control',return_value=game),patch.object(control,'find_window',side_effect=AssertionError('X11 forbidden')),patch.object(control,'read_state',return_value={'pid':123,'phase':'login'}),patch.object(control.getpass,'getpass',side_effect=AssertionError('Do not request a secret')),patch.object(sys,'argv',['game-control.py','type','--secret']):
            with self.assertRaisesRegex(RuntimeError,'ai-game.py'):control.main()

    def fake_window(self,fail=False):
        self.assertTrue(hasattr(control,'XErrorEvent'),'Capture errors still terminate the process')
        class X:
            handler=0
            destroyed=0
            dimensions=None
            def XSetErrorHandler(self,handler):
                previous=self.handler;self.handler=handler.value if isinstance(handler,C.c_void_p) else handler
                return previous
            def XSync(self,*args):return 0
            def XGetGeometry(self,display,window,root,x,y,width,height,border,depth):
                C.cast(width,C.POINTER(C.c_uint)).contents.value=40
                C.cast(height,C.POINTER(C.c_uint)).contents.value=30
                return 1
            def XGetImage(self,display,window,x,y,width,height,*args):
                self.dimensions=(width,height)
                if fail:
                    event=control.XErrorEvent();event.error_code=8;event.request_code=73
                    callback=C.cast(C.c_void_p(self.handler),C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(control.XErrorEvent)))
                    callback(display,C.byref(event))
                    return C.POINTER(control.XImage)()
                self.pixels=C.create_string_buffer(b'\x10\x20\x30\x00'*(width*height))
                self.info=control.XImage();self.info.width=width;self.info.height=height
                self.info.bits_per_pixel=32;self.info.bytes_per_line=width*4
                self.info.data=C.cast(self.pixels,C.c_void_p)
                return C.pointer(self.info)
            def XDestroyImage(self,image):self.destroyed+=1
        window=control.GameWindow.__new__(control.GameWindow)
        window.x=X();window.display=1;window.window=2;window.width=1280;window.height=720
        return window

    def test_capture_refreshes_geometry_after_resize(self):
        window=self.fake_window()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'screen.png';window.screenshot(path)
            from PIL import Image
            with Image.open(path) as image:self.assertEqual(image.size,(40,30))
        self.assertEqual(window.x.dimensions,(40,30))
        self.assertEqual(window.x.destroyed,1)
        self.assertEqual(window.x.handler,0)

    def test_badmatch_is_a_recoverable_error_and_restores_handler(self):
        window=self.fake_window(fail=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):window.screenshot(Path(directory)/'screen.png')
        self.assertEqual(window.x.handler,0)
        self.assertEqual(window.x.destroyed,0)

if __name__=='__main__':unittest.main()
