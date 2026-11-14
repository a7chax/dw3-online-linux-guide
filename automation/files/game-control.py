#!/usr/bin/env python3
"""Read game state and send bounded input to one verified Linux game window."""
import argparse
import ctypes as C
import ctypes.util
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import threading
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / 'linux/ai-sessions/latest/state.json'


def read_state(path, fresh=True):
    state = json.loads(path.read_text())
    stamp = datetime.fromisoformat(state['time'].replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if fresh and not -2 <= age <= 3:
        raise RuntimeError('State file is stale. Start a monitored window with ./start-ai-game.sh.')
    if fresh:
        os.kill(int(state['pid']), 0)
    return state


def find_window(pid):
    listing = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
    pattern = r'(0x[0-9a-f]+) "DW3 Online": \("DW3 Online" "DW3 Online"\)\s+(\d+)x(\d+)'
    for match in re.finditer(pattern, listing):
        prop = subprocess.run(['xprop', '-id', match[1], '_NET_WM_PID'], capture_output=True, text=True).stdout
        if re.search(r'=\s*' + str(pid) + r'\s*$', prop):
            return int(match[1], 16), int(match[2]), int(match[3])
    raise RuntimeError(f'No DW3 Online window belongs to monitored process {pid}.')


class ClientData(C.Union):
    _fields_ = [('b', C.c_char * 20), ('s', C.c_short * 10), ('l', C.c_long * 5)]


class ClientMessage(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('message_type', C.c_ulong),
                ('format', C.c_int), ('data', ClientData)]


class KeyEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong), ('x', C.c_int), ('y', C.c_int),
                ('x_root', C.c_int), ('y_root', C.c_int), ('state', C.c_uint),
                ('code', C.c_uint), ('same_screen', C.c_int)]


class MotionEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong), ('x', C.c_int), ('y', C.c_int),
                ('x_root', C.c_int), ('y_root', C.c_int), ('state', C.c_uint),
                ('is_hint', C.c_char), ('same_screen', C.c_int)]


class XEvent(C.Union):
    _fields_ = [('client', ClientMessage), ('key', KeyEvent), ('motion', MotionEvent), ('pad', C.c_long * 24)]


class XImage(C.Structure):
    _fields_ = [('width', C.c_int), ('height', C.c_int), ('xoffset', C.c_int),
                ('format', C.c_int), ('data', C.c_void_p), ('byte_order', C.c_int),
                ('bitmap_unit', C.c_int), ('bitmap_bit_order', C.c_int), ('bitmap_pad', C.c_int),
                ('depth', C.c_int), ('bytes_per_line', C.c_int), ('bits_per_pixel', C.c_int),
                ('red_mask', C.c_ulong), ('green_mask', C.c_ulong), ('blue_mask', C.c_ulong)]


class XErrorEvent(C.Structure):
    _fields_=[('type',C.c_int),('display',C.c_void_p),('resourceid',C.c_ulong),
              ('serial',C.c_ulong),('error_code',C.c_ubyte),
              ('request_code',C.c_ubyte),('minor_code',C.c_ubyte)]


XErrorHandler=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(XErrorEvent))
_X_ERROR_LOCK=threading.RLock()


class WindowUnavailable(RuntimeError):
    """The game window must be restored or refreshed before UI operations."""


class GameWindow:
    def __init__(self, pid):
        self.window, self.width, self.height = find_window(pid)
        self.pid = pid
        self.modifiers = 0
        self.x = C.CDLL(ctypes.util.find_library('X11'))
        signatures = {
            'XOpenDisplay': ([C.c_char_p], C.c_void_p),
            'XCloseDisplay': ([C.c_void_p], C.c_int),
            'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
            'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
            'XSendEvent': ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(XEvent)], C.c_int),
            'XSetInputFocus': ([C.c_void_p, C.c_ulong, C.c_int, C.c_ulong], C.c_int),
            'XGetInputFocus': ([C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_int)], C.c_int),
            'XFlush': ([C.c_void_p], C.c_int),
            'XSync': ([C.c_void_p, C.c_int], C.c_int),
            'XRaiseWindow': ([C.c_void_p, C.c_ulong], C.c_int),
            'XResizeWindow': ([C.c_void_p, C.c_ulong, C.c_uint, C.c_uint], C.c_int),
            'XStringToKeysym': ([C.c_char_p], C.c_ulong),
            'XKeysymToKeycode': ([C.c_void_p, C.c_ulong], C.c_uint),
            'XTranslateCoordinates': ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_int, C.c_int,
                                      C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_ulong)], C.c_int),
            'XGetImage': ([C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_ulong, C.c_int], C.POINTER(XImage)),
            'XGetGeometry': ([C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint)],C.c_int),
            'XSetErrorHandler': ([C.c_void_p],C.c_void_p),
            'XDestroyImage': ([C.POINTER(XImage)], C.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.x, name)
            function.argtypes, function.restype = arguments, result
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Cannot access the graphical X11 session.')
        self.root = self.x.XDefaultRootWindow(self.display)

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None

    def focused(self):
        window, revert = C.c_ulong(), C.c_int()
        self.x.XGetInputFocus(self.display, C.byref(window), C.byref(revert))
        return window.value == self.window

    def focus(self):
        with self._checked_x('Focus'):
            self._focus_window()

    @contextmanager
    def _checked_x(self,operation):
        # Xlib's default handler exits the whole controller on BadMatch. Keep
        # errors local to this operation, including asynchronous server replies.
        with _X_ERROR_LOCK:
            errors=[]
            @XErrorHandler
            def error(display,event):
                errors.append(event.contents.error_code);return 0
            previous=self.x.XSetErrorHandler(C.cast(error,C.c_void_p))
            try:
                yield
            finally:
                self.x.XSync(self.display,0)
                self.x.XSetErrorHandler(previous)
            if errors:
                raise WindowUnavailable(f'{operation} could not access the game window (X11 error {errors[-1]}). Restore the window and retry.')

    def _focus_window(self):
        event = XEvent()
        event.client.type = 33
        event.client.display = self.display
        event.client.window = self.window
        event.client.message_type = self.x.XInternAtom(self.display, b'_NET_ACTIVE_WINDOW', 0)
        event.client.format = 32
        event.client.data.l[0] = 2
        self.x.XSendEvent(self.display, self.root, 0, (1 << 20) | (1 << 19), C.byref(event))
        self.x.XRaiseWindow(self.display, self.window)
        self.x.XFlush(self.display)
        time.sleep(.15)
        self.x.XSetInputFocus(self.display, self.window, 2, 0)
        self.x.XSync(self.display, 0)
        if not self.focused():
            raise RuntimeError('The selected game window did not receive focus. No input was sent.')

    def code(self, key):
        sym = self.x.XStringToKeysym(key.encode('ascii'))
        code = self.x.XKeysymToKeycode(self.display, sym)
        if not code:
            raise ValueError('Unsupported key name')
        return code

    def key_event(self, key, down):
        event = XEvent()
        event.key.type = 2 if down else 3
        event.key.display = self.display
        event.key.window = self.window
        event.key.root = self.root
        event.key.same_screen = 1
        event.key.state = self.modifiers
        event.key.code = self.code(key)
        self.x.XSendEvent(self.display, self.window, 0, 1 if down else 2, C.byref(event))
        modifier = {'Shift_L': 1, 'Control_L': 4, 'Alt_L': 8}.get(key, 0)
        if down: self.modifiers |= modifier
        else: self.modifiers &= ~modifier
        self.x.XSync(self.display, 0)

    def tap(self, name):
        modifiers = {'ctrl': 'Control_L', 'shift': 'Shift_L', 'alt': 'Alt_L'}
        parts = name.split('+')
        keys = [modifiers.get(part.lower(), part) for part in parts]
        held = []
        try:
            for key in keys:
                self.key_event(key, True)
                held.append(key)
            time.sleep(.025)
        finally:
            for key in reversed(held):
                self.key_event(key, False)

    def type_text(self, text):
        if any(not (character.isascii() and character.isalnum()) for character in text):
            raise ValueError('This credential input helper accepts ASCII letters and digits only.')
        for character in text:
            self.tap(('shift+' if character.isupper() else '') + character.lower())
            time.sleep(.025)

    def native_click(self, x, y):
        # Compatibility entry point: target this game's input processor, not
        # the desktop pointer or GNOME's XTEST/Remote Desktop portal.
        import importlib.util
        spec=importlib.util.spec_from_file_location('dw3_click_control',ROOT/'ai-game.py')
        game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)
        return game.click_game(self,x,y)

    def click(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError('Click lies outside the verified game window.')
        root_x, root_y, child = C.c_int(), C.c_int(), C.c_ulong()
        self.x.XTranslateCoordinates(self.display, self.window, self.root, x, y,
                                     C.byref(root_x), C.byref(root_y), C.byref(child))
        event = XEvent()
        event.motion.type = 6
        event.motion.display = self.display
        event.motion.window = self.window
        event.motion.root = self.root
        event.motion.same_screen = 1
        event.motion.x, event.motion.y = x, y
        event.motion.x_root, event.motion.y_root = root_x.value, root_y.value
        self.x.XSendEvent(self.display, self.window, 0, 1 << 6, C.byref(event))
        self.x.XSync(self.display, 0)
        time.sleep(.04)
        for down in (True, False):
            event = XEvent()
            event.key.type = 4 if down else 5
            event.key.display = self.display
            event.key.window = self.window
            event.key.root = self.root
            event.key.same_screen = 1
            event.key.x, event.key.y = x, y
            event.key.x_root, event.key.y_root = root_x.value, root_y.value
            event.key.code = 1
            self.x.XSendEvent(self.display, self.window, 0, 1 << (2 if down else 3), C.byref(event))
            self.x.XSync(self.display, 0)
            time.sleep(.04)

    def screenshot(self, path):
        from PIL import Image
        with self._checked_x('Capture'):
            root,x,y=C.c_ulong(),C.c_int(),C.c_int()
            width,height,border,depth=C.c_uint(),C.c_uint(),C.c_uint(),C.c_uint()
            if not self.x.XGetGeometry(self.display,self.window,C.byref(root),C.byref(x),C.byref(y),C.byref(width),C.byref(height),C.byref(border),C.byref(depth)):
                raise WindowUnavailable('The game window is unavailable. Restore it and retry.')
            if not width.value or not height.value:raise WindowUnavailable('The game window has no drawable area.')
            self.width,self.height=width.value,height.value
            image=self.x.XGetImage(self.display,self.window,0,0,self.width,self.height,C.c_ulong(-1).value,2)
            if not image:raise WindowUnavailable('The game window could not be captured. Restore it and retry.')
            try:
                info=image.contents
                if info.bits_per_pixel!=32:raise RuntimeError('Unsupported capture pixel format.')
                pixels=C.string_at(info.data,info.height*info.bytes_per_line)
                result=Image.frombytes('RGB',(info.width,info.height),pixels,'raw','BGRX',info.bytes_per_line)
            finally:self.x.XDestroyImage(image)
        path.parent.mkdir(parents=True,exist_ok=True);result.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', type=Path, default=DEFAULT_STATE)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('state')
    screenshot = commands.add_parser('screenshot'); screenshot.add_argument('path', type=Path)
    click = commands.add_parser('click'); click.add_argument('x', type=int); click.add_argument('y', type=int)
    key = commands.add_parser('key'); key.add_argument('name')
    typing = commands.add_parser('type'); group = typing.add_mutually_exclusive_group(required=True)
    group.add_argument('--text'); group.add_argument('--secret', action='store_true')
    resize = commands.add_parser('resize'); resize.add_argument('width', type=int); resize.add_argument('height', type=int)
    move = commands.add_parser('move'); move.add_argument('direction', choices=['up', 'down', 'left', 'right'])
    move.add_argument('--seconds', type=float, default=.25)
    args = parser.parse_args()
    state = read_state(args.state_file)
    if args.command == 'state':
        print(json.dumps(state)); return
    if args.command == 'type' and state['phase'] != 'login':
        raise RuntimeError('Credential input is allowed only on the verified login screen.')
    text = getpass.getpass('Text (not saved): ') if args.command == 'type' and args.secret else getattr(args, 'text', None)
    state = read_state(args.state_file)
    window = GameWindow(state['pid'])
    try:
        if args.command == 'screenshot':
            window.focus()
            time.sleep(.2)
            window.screenshot(args.path);print(json.dumps({'image': str(args.path), 'pid': state['pid']}))
        elif args.command == 'resize':
            if not (640 <= args.width <= 1920 and 360 <= args.height <= 1080): raise ValueError('Unsupported test window size.')
            window.x.XResizeWindow(window.display, window.window, args.width, args.height)
            window.x.XSync(window.display, 0)
        elif args.command == 'click': window.click(args.x, args.y)
        elif args.command == 'key': window.tap(args.name)
        elif args.command == 'type': window.type_text(text)
        elif args.command == 'move':
            if state['phase'] != 'world': raise RuntimeError('Movement is allowed only after entering the game world.')
            if not .05 <= args.seconds <= .75: raise ValueError('Use a movement duration from 0.05 to 0.75 seconds.')
            key = {'up':'Up','down':'Down','left':'Left','right':'Right'}[args.direction]
            history = args.state_file.with_name('state-events.jsonl')
            offset = history.stat().st_size if history.exists() else 0
            try:
                window.key_event(key, True)
                deadline = time.monotonic() + args.seconds
                while time.monotonic() < deadline:
                    time.sleep(.015)
            finally:
                window.key_event(key, False)
            time.sleep(.4)
            after = read_state(args.state_file)
            with history.open() as file:
                file.seek(offset)
                events = [json.loads(line) for line in file if line.strip()]
            fields = ['pid','phase','map','x','y','tile_x','tile_y','moving','facing']
            result = {'direction':args.direction,'seconds':args.seconds,
                      'before':{key:state[key] for key in fields},'after':{key:after[key] for key in fields},
                      'observed_movement':any(event.get('moving') is True for event in events)}
            output = args.state_file.with_name('last-move.json')
            output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result))
    finally:
        window.close()


def interrupt(signum, frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupt)
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error))
