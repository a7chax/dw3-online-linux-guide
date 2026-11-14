import ctypes as C
import importlib.util
from pathlib import Path
import sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('capture_control',ROOT/'game-control.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)

class CaptureTests(unittest.TestCase):
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
