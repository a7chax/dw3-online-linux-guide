#!/usr/bin/env python3
"""Prepare, log in, and run the existing local automation with one command."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import autoplay

ROOT=Path(__file__).resolve().parent


def native_input(state):
    return bool(state and {'space','enter','g','x'}<=set(state.get('native_key_input') or ())
                and state.get('native_click_input') is True
                and state.get('native_background_input') is True and state.get('native_capture') is True
                and state.get('native_inn_recovery') is True
                and state.get('native_battle_control') is True and state.get('native_supplies_control') is True)


def controller_running(session):
    lock=session/'autoplay.lock'
    if not lock.exists():return False
    with lock.open('a+') as lease:
        try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
    return False


def run(max_cycles=None,*,battle_space=True,repair_with_codex=True,root=ROOT,game=None,
        supervisor_factory=None,runner=None,which=None,window_factory=None):
    root=Path(root)
    if not (root/'app/client.jar').is_file():
        raise RuntimeError('Run automation.py from your installed game folder containing app/client.jar.')
    if max_cycles is not None and (type(max_cycles) is not int or max_cycles<1):
        raise ValueError('--max-cycles must be positive.')
    game=game or autoplay.load_game();runner=runner or subprocess.run;which=which or shutil.which
    supervisor_factory=supervisor_factory or autoplay.Supervisor
    try:
        before=game.request('status')
        if not game.fresh_state(before):before=None
    except (OSError,ValueError,RuntimeError):before=None
    session=Path(game.LATEST).resolve()
    if controller_running(session):
        if before and before.get('phase')=='world' and before.get('native_background_input') is not True:
            try:
                with game.navigation_lease():
                    if window_factory is None:
                        from game_control import GameWindow
                        window_factory=GameWindow
                    window=window_factory(before['pid'])
                    try:window.focus()
                    finally:window.close()
            except RuntimeError:pass  # An existing action can own the input lease.
        result={'already_running':True,'session':str(session),'pid':(before or {}).get('pid')}
        print(json.dumps(result),flush=True);return result

    def identity_required():
        settings=game.login_settings()
        if (not settings.get('username') or not settings.get('character')
                or settings.get('username')=='your_username' or settings.get('character')=='your_character'
                or settings.get('password')=='replace_with_your_password'):
            raise RuntimeError('Configure DW3_USERNAME and DW3_CHARACTER in private .env; replace .env.example placeholders. The password can use the hidden prompt.')

    def build(command,tools):
        paths={name:which(name) for name in tools}
        if any(not path for path in paths.values()):
            missing=', '.join(name for name,path in paths.items() if not path)
            raise RuntimeError('Install the required JDK 21/build tools on PATH; missing: '+missing)
        executable=paths[command[0]]
        environment={key:value for key,value in os.environ.items() if not key.startswith('DW3_')}
        runner([executable,*command[1:]],cwd=root,check=True,env=environment)

    def build_bridge():
        if not (root/'DW3-Online.apk').is_file():
            raise RuntimeError('Place the matching original DW3-Online.apk in the game directory to rebuild the bridge; Android SDK apksigner is also required.')
        build(['uv','run','--locked','python','linux/native/build.py'],('uv','java','javac','jar'))

    bridge=root/'linux/lib/dw3-android-bridge.jar'
    sources=[root/'linux/native/build.py',*(root/'linux/native/src').rglob('*.java')]
    rebuild=(not bridge.is_file() or any(source.stat().st_mtime_ns>bridge.stat().st_mtime_ns for source in sources if source.is_file())
             or (before is not None and not native_input(before)))
    if rebuild or not (before and before.get('phase')=='world'):identity_required()
    if rebuild:build_bridge()
    if not (root/'DW3-Online-Linux').is_file() or not (root/'linux/runtime/bin/java').is_file():
        build(['bash','linux/native/build-executable.sh'],('bash','gcc','jlink','uv'))
    state=game.login(restart=rebuild)
    if not native_input(state) and not rebuild:
        identity_required();build_bridge();state=game.login(restart=True)
    if not game.fresh_state(state) or state.get('phase')!='world' or not native_input(state):
        raise RuntimeError('The monitored game needs the updated native input bridge. Rebuild it and restart the client before automation.')
    session=Path(game.LATEST).resolve();(session/'autoplay.stop').unlink(missing_ok=True)
    supervisor=supervisor_factory(game,session,expected_pid=state['pid'],battle_space=battle_space,
        repair_with_codex=repair_with_codex,close_popups=True)
    result=supervisor.run(max_cycles)
    if supervisor.restart_requested and not (session/'autoplay.stop').exists():
        os.execv(sys.executable,[sys.executable,str(root/'automation.py'),*sys.argv[1:]])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--status',action='store_true');modes.add_argument('--stop',action='store_true')
    parser.add_argument('--max-cycles',type=int)
    parser.add_argument('--no-codex-repair',action='store_true')
    parser.add_argument('--no-battle-space',action='store_true')
    args=parser.parse_args()
    if args.status or args.stop:
        previous=sys.argv
        try:
            sys.argv=[str(ROOT/'autoplay.py'),'--status' if args.status else '--stop'];autoplay.main()
        finally:sys.argv=previous
        return
    run(args.max_cycles,battle_space=not args.no_battle_space,repair_with_codex=not args.no_codex_repair)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as error:raise SystemExit(str(error))
