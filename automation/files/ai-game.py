#!/usr/bin/env python3
"""Start/reuse a monitored game, sign in securely, and perform bounded movements."""
import argparse
from datetime import datetime,timezone
import getpass
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import unicodedata
import zipfile
import fcntl
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent
LATEST=ROOT/'linux/ai-sessions/latest'


def read_dotenv(path):
    """Read four literal credential assignments; never evaluate or expand them."""
    keys={'DW3_USERNAME','DW3_PASSWORD','DW3_SERVER','DW3_CHARACTER'}
    try:lines=Path(path).read_text(encoding='utf-8-sig').splitlines()
    except FileNotFoundError:return {}
    values={}
    for number,line in enumerate(lines,1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:].lstrip()
        key,separator,value=line.partition('=');key=key.strip()
        if key not in keys:continue
        if not separator:raise ValueError(f'Invalid .env assignment on line {number}.')
        value=value.strip()
        if value[:1] in ('"',"'"):
            if len(value)<2 or value[-1]!=value[0]:raise ValueError(f'Unclosed .env quote on line {number}.')
            value=value[1:-1]
        values[key]=value
    return values


def login_settings(username=None,server=None,character=None,*,environ=None,dotenv_path=None):
    """Explicit CLI values > process environment > project .env > defaults."""
    environment=os.environ if environ is None else environ
    values=read_dotenv(ROOT/'.env' if dotenv_path is None else dotenv_path)
    def select(key,explicit,default):
        if explicit is not None:return explicit
        return environment[key] if key in environment else values.get(key,default)
    return {'username':select('DW3_USERNAME',username,''),
            'password':select('DW3_PASSWORD',None,None) or None,
            'server':select('DW3_SERVER',server,'asia'),
            'character':select('DW3_CHARACTER',character,'')}


def request(operation,**parameters):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(180 if operation=='export_world' else 12)
        connection.connect(str(LATEST/'control.sock'))
        payload={'op':operation,**parameters}
        connection.sendall(json.dumps(payload).encode()+b'\n')
        response=bytearray()
        while not response.endswith(b'\n'):
            part=connection.recv(65536)
            if not part:break
            response.extend(part)
        reply=json.loads(response)
        if not reply.get('ok'):raise RuntimeError(reply.get('error','Game control failed'))
        return reply['result']


def monitored_alive():
    try:
        state=json.loads((LATEST/'state.json').read_text())
        stamp=datetime.fromisoformat(state['time'].replace('Z','+00:00'))
        return (datetime.now(timezone.utc)-stamp).total_seconds()<4 and (LATEST/'control.sock').exists()
    except (OSError,ValueError,KeyError):return False


def start(restart=False):
    if restart:
        try:
            state=json.loads((LATEST/'state.json').read_text());pid=int(state['pid'])
            process=Path(f'/proc/{pid}')
            args=(process/'cmdline').read_bytes().split(b'\0')
            if (process/'exe').resolve()==(ROOT/'linux/runtime/bin/java').resolve() and b'dw3.linux.DesktopLauncher' in args:
                os.kill(pid,signal.SIGTERM)
                deadline=time.monotonic()+5
                while process.exists() and time.monotonic()<deadline:time.sleep(.05)
        except (OSError,ValueError,KeyError):pass
    if restart or not monitored_alive():
        previous=LATEST.resolve() if LATEST.exists() else None
        subprocess.Popen([str(ROOT/'start-ai-game.sh')],cwd=ROOT,stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,
                         env={key:value for key,value in os.environ.items() if key!='DW3_PASSWORD'})
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            if LATEST.exists() and LATEST.resolve()!=previous and monitored_alive():break
            time.sleep(.1)
        else:raise RuntimeError('The monitored game did not start. Check ./start-ai-game.sh.')
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            status=request('status')
            if status['phase']!='starting':return status
        except (OSError,RuntimeError,ValueError):pass
        time.sleep(.1)
    raise RuntimeError('The game has not reached a usable screen.')


def wait_for(phases,seconds=35):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        status=request('status')
        if status['phase'] in phases:return status
        if status['phase']=='login' and not status.get('connecting') and status.get('message'):
            raise RuntimeError('Game login: '+status['message'])
        time.sleep(.15)
    raise RuntimeError('Timed out waiting for '+', '.join(phases))


def login(username=None,server=None,character=None,restart=False,use_filled=False):
    status=start(restart)
    if status['phase']=='world':
        print('Using the existing monitored game world.',flush=True)
        return status
    settings=login_settings(username,server,character)
    username,server,character=(settings[key] for key in ('username','server','character'))
    if not username or not character:
        raise RuntimeError('Set DW3_USERNAME and DW3_CHARACTER in .env or pass --username and --character.')
    if status['phase']=='login':
        if not use_filled:
            secret=settings['password'] or getpass.getpass('Password (hidden): ')
            try:status=request('fill_login',username=username,password=secret)
            finally:secret=None;settings['password']=None
        elif status.get('username')!=username or not status.get('password_length'):
            raise RuntimeError('The current login fields are not filled for the requested user.')
        print('Login fields set once; password storage disabled.',flush=True)
        if not status.get('server_selection'):status=request('submit_login')
        servers=status.get('servers',[])
        fold=lambda text: ''.join(character for character in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(character))
        selected=next((name for name in servers if fold(server) in fold(name)),None)
        if selected is None:raise RuntimeError('Requested server not found: '+', '.join(servers))
        request('select_server',server=selected)
        print('Selected server: '+selected,flush=True)
        status=wait_for({'character_selection','world'})
    if status['phase']=='character_selection':
        names=status.get('characters',[])
        chosen=next((name for name in names if name.lower()==character.lower()),None)
        if chosen is None:raise RuntimeError('Requested character not found. Available: '+', '.join(names))
        request('select_character',character=character)
        print('Selected character: '+chosen,flush=True)
        status=wait_for({'world'})
    if status['phase']!='world':raise RuntimeError('The game did not enter the world.')
    print('State file: '+str(LATEST/'state.json'),flush=True)
    print(json.dumps({key:status.get(key) for key in ['phase','map','x','y','tile_x','tile_y']}),flush=True)
    return status


def fresh_state(state):
    try:
        stamp=datetime.fromisoformat(state['time'].replace('Z','+00:00'))
        return -2 <= (datetime.now(timezone.utc)-stamp).total_seconds() < 3
    except (ValueError,KeyError,TypeError):return False


def trace_step(state,blocked_direction=None,diagonal=False):
    trace=state.get('trace') or {}
    if state.get('phase')!='world' or not trace.get('enabled') or trace.get('route_type') in (0,4):return None
    x,y=state['x'],state['y']
    target=None;previous=(x,y);heading=None
    for point in trace.get('points',[]):
        # At 50 ms the client can move about 12 horizontal units. Treat
        # points within eight units as reached rather than bounce over them.
        if math.hypot(point[0]-x,point[1]-y)<8:continue
        dx,dy=point[0]-previous[0],point[1]-previous[1]
        length=math.hypot(dx,dy)
        if length<.01:continue
        unit=(dx/length,dy/length)
        # Stop the look-ahead at a bend, so a key burst cannot cut a corner.
        if heading and unit[0]*heading[0]+unit[1]*heading[1]<.94:break
        target=point;previous=point;heading=unit
        if math.hypot(point[0]-x,point[1]-y)>=21:break
    if target is None:return None
    dx,dy=target[0]-x,target[1]-y
    if math.hypot(dx,dy)<3:return None
    if abs(dx)>=abs(dy)*2:direction='right' if dx>0 else 'left';duration=abs(dx)/240
    else:direction='down' if dy>0 else 'up';duration=abs(dy)/120
    if diagonal and abs(dx)>=4 and abs(dy)>=2 and .25<=abs(dy/dx)<=1:
        direction=('down' if dy>0 else 'up')+'_'+('right' if dx>0 else 'left')
        duration=min(abs(dx)/(240/math.sqrt(2)),abs(dy)/(120/math.sqrt(2)))
    if direction==blocked_direction:
        if direction in ('up','down') and abs(dx)>=4:
            direction='right' if dx>0 else 'left';duration=abs(dx)/240
        elif direction in ('left','right') and abs(dy)>=4:
            direction='down' if dy>0 else 'up';duration=abs(dy)/120
        else:return None
    return direction,max(50,min(175,round(duration*1000)))


def forward_step(state,index=0,diagonal=False):
    # aj.b(dx,dy), inspected in the original 0.1.95 client. Diagonal
    # headings use alternating cardinal bursts supported by the live bridge.
    directions={0:('down',),1:('down','left'),2:('left',),3:('up','left'),
                4:('up',),5:('up','right'),6:('right',),7:('down','right')}
    heading=directions.get(state.get('facing'))
    if heading is None:return None
    if diagonal and len(heading)==2:return '_'.join(heading),100
    return heading[index%len(heading)],100


@contextmanager
def navigation_lease():
    with (LATEST/'navigation.lock').open('a+') as lease:
        try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another navigation controller is already running for this game.')
        yield


def move(direction,milliseconds,focus=True,quiet=False,expected_map=None):
    if not focus:return _move(direction,milliseconds,focus,quiet,expected_map)
    with navigation_lease():return _move(direction,milliseconds,focus,quiet,expected_map)


def _move(direction,milliseconds,focus=True,quiet=False,expected_map=None):
    window=None
    try:
        if focus:
            from game_control import GameWindow
            status=request('status');expected_map=status.get('map')
            window=GameWindow(status['pid']);window.focus()
        parameters={'direction':direction,'milliseconds':milliseconds}
        if expected_map is not None:parameters['expected_map']=expected_map
        result=request('move',**parameters)
    finally:
        if window:window.close()
    before,after=result['before'],result['after']
    result['direction']=direction
    result['moved']=before.get('map')==after.get('map') and (before.get('x'),before.get('y'))!=(after.get('x'),after.get('y'))
    (LATEST/'last-move.json').write_text(json.dumps(result,indent=2)+'\n')
    if not quiet:print(json.dumps(result),flush=True)
    return result


def describe_quest(state):
    progress=state.get('main_quest')
    if not progress:raise RuntimeError('Main quest progress is not available. Load the updated bridge and enter the world.')
    quest=dict(progress)
    with zipfile.ZipFile(ROOT/'app/client.jar') as archive:
        chapters=json.loads(archive.read('quests/steps.json'))['chapters']
    chapter,step=quest.get('chapter',0)-1,quest.get('step',0)-1
    definition=chapters[chapter][step] if 0<=chapter<len(chapters) and 0<=step<len(chapters[chapter]) else None
    matches=bool(definition and definition.get('stage')==quest.get('target_map'))
    quest['definition_matches_state']=matches
    quest['required_action']=definition.get('how','unknown') if matches else 'unknown'
    if matches and 'npc' in definition:
        quest['target_npc_id']=definition['npc']
        quest['target_npc_source']='bundled_quest_steps'
    quest['action_source']='bundled quests/steps.json matched to live progress' if matches else 'unresolved'
    quest['on_target_map']=state.get('map')==quest.get('target_map')
    action=quest['required_action']
    quest['next_action']=('travel_to_map' if not quest['on_target_map'] else
                          {'talk':'talk_to_npc','enter':'enter_target','zone':'reach_target_map','drop':'win_battles_in_target_map'}.get(action,'inspect_objective'))
    return quest


def follow_trace(seconds=10,destination=None,cross_map=False,continuous=False):
    # All movement commands for one monitored session share this lease.
    # A second script must not steal focus or interleave its movement bursts.
    if not 0<seconds<=300:raise ValueError('Follow duration must be between 0 and 300 seconds.')
    with navigation_lease():
        deadline=time.monotonic()+seconds;transitions=[]
        first_segment=True
        while True:
            result=_follow_trace(max(.01,deadline-time.monotonic()),destination,cross_map,focus_on_start=first_segment)
            first_segment=False
            if result['reason']=='map_changed':
                transitions.append({'from':result['before'].get('map'),'to':result['current'].get('map')})
            result['map_transitions']=transitions
            temporary=LATEST/'follow-state-final.tmp';temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(LATEST/'follow-state.json')
            if not continuous or destination is not None or result['reason']!='map_changed' or time.monotonic()>=deadline:return result
            print('Continuing on map '+str(result['current'].get('map')),flush=True)


def _follow_trace(seconds=10,destination=None,cross_map=False,focus_on_start=True):
    from game_control import GameWindow
    from motion_watch import MotionWatch
    if not 0<seconds<=300:raise ValueError('Follow duration must be between 0 and 300 seconds.')
    state=request('status')
    if not fresh_state(state) or state.get('phase')!='world':raise RuntimeError('No fresh game world state.')
    if 'trace' not in state:raise RuntimeError('Restart the monitored game once to load GPS telemetry.')
    local_map=None;local_path=None;terrain_map=None
    diagonal='down_right' in state.get('movement_directions',[])
    if destination is not None:
        from world_map import WorldMap
        destination=tuple(map(float,destination))
        if not all(math.isfinite(value) for value in destination):raise ValueError('Destination must be finite coordinates.')
        local_map=WorldMap(state['map'])
        planned_at=time.perf_counter()
        local_path=local_map.path((state['x'],state['y']),destination)
        planning={'source':'local_collision_atlas','map':state['map'],'start':[state['x'],state['y']],
                  'goal':destination,'points':local_path,'planned_ms':round((time.perf_counter()-planned_at)*1000,2)}
        (LATEST/'local-path.json').write_text(json.dumps(planning,indent=2)+'\n')
        print(json.dumps({'navigation_source':planning['source'],'planned_ms':planning['planned_ms'],
                          'waypoints':len(local_path),'goal':destination}),flush=True)
    if local_map:terrain_map=local_map
    elif diagonal:
        from world_map import WorldMap
        try:terrain_map=WorldMap(state['map'])
        except (OSError,RuntimeError):pass
    initial=state;window=GameWindow(state['pid']);reason='time_limit';bursts=0;stalls=0
    blocked_direction=None;pause_until=0;missing_since=None;forward_since=None
    motion=MotionWatch(time.monotonic());blocked_directions=set();redirects=0;planner_ms=0
    blocked_route=None;blocked_at=0
    forward_heading=None;forward_bursts=0;mode='trace';no_progress_since=motion.last_progress;replans=0
    deadline=time.monotonic()+seconds
    report=LATEST/'follow-state.json'
    def record(active):
        output={'active':active,'reason':None if active else reason,'bursts':bursts,
                'mode':mode,'navigation_source':'local_collision_atlas' if local_map else 'server_gps',
                'destination':destination,'replans':replans,'before':initial,'current':state,
                'blocked_directions':sorted(blocked_directions),'redirects':redirects,'planner_ms':round(planner_ms,3)}
        temporary=report.with_suffix('.tmp');temporary.write_text(json.dumps(output,indent=2)+'\n');temporary.replace(report)
    try:
        if focus_on_start:window.focus()
        elif not window.focused():
            reason='focus_lost'
            record(False)
            return json.loads(report.read_text())
        while time.monotonic()<deadline:
            # Poll even while idle: the server can replace a blocked route.
            state=request('status')
            if not fresh_state(state):reason='stale_state';break
            if state.get('pid')!=initial.get('pid'):reason='session_changed';break
            if state.get('phase')=='world' and state.get('map')!=initial.get('map'):reason='map_changed';break
            if not window.focused():reason='focus_lost';break
            if state.get('phase') in ('loading_map','starting'):
                mode='waiting_for_map';record(True);time.sleep(.1);continue
            if state.get('phase')!='world':reason='screen_changed';break
            if (state.get('battle') or {}).get('active'):reason='battle_active';break
            if (state.get('story') or {}).get('active'):reason='story_active';break
            if state.get('dialogue'):reason='interaction_required';break
            if state.get('movement_ready') is False:reason='world_input_blocked';break
            planning_state=state
            if local_map:
                if math.dist((state['x'],state['y']),destination)<8 and not cross_map:
                    reason='destination_reached';break
                from world_map import remaining_path
                dots=remaining_path(local_path,(state['x'],state['y']))
                planning_state={**state,'trace':{'enabled':True,'route_type':1,'points':dots,
                                                'steps_remaining':math.ceil(len(dots)*7/16)}}
            now=time.monotonic()
            if now<pause_until:
                mode='waiting_for_route_refresh';record(True);time.sleep(.1);continue
            trace=planning_state.get('trace') or {}
            route_signature=(trace.get('route_type'),tuple(tuple(round(value) for value in point)
                             for point in (trace.get('points') or [])[:3]))
            blocked_directions=motion.blocked((state['x'],state['y']),now)
            if blocked_direction not in blocked_directions:blocked_direction=None
            if (blocked_direction and terrain_map is None and
                    (route_signature!=blocked_route or now-blocked_at>=1.2)):
                blocked_direction=None
            normal=trace_step(planning_state,diagonal=diagonal)
            if not local_map and trace.get('route_type')==2 and (trace.get('steps_remaining') or 0)<=2:
                points=trace.get('points') or []
                if points and math.dist((state['x'],state['y']),points[-1])<24:
                    reason='interaction_required';mode='at_interaction_target';break
            step=trace_step(planning_state,blocked_direction,diagonal=diagonal) if blocked_direction else normal
            if normal is not None:
                missing_since=None;forward_since=None;forward_heading=None;forward_bursts=0
                mode='recovering' if blocked_direction else ('local_path' if local_map else 'trace')
                if terrain_map and diagonal:
                    route=local_path if local_map else trace.get('points',[])
                    goal=destination if local_map else (route[-1] if route else None)
                    if goal is not None:
                        planned_at=time.perf_counter()
                        checked=terrain_map.steering_step((state['x'],state['y']),goal,route,
                                                          preferred_step=step,blocked=blocked_directions,allow_diagonal=True)
                        planner_ms=(time.perf_counter()-planned_at)*1000
                        if checked!=step:mode='collision_recovery'
                        if blocked_directions and checked is not None and checked!=normal:redirects+=1
                        step=checked
                if step is None:
                    stalls+=1
                    # Hand a genuinely blocked GPS segment to the supervisor's
                    # full atlas planner without waiting out six seconds.
                    if terrain_map and not local_map and stalls>=2:reason='unable_to_advance';break
                    # Do not hammer a failed key while waiting for a new route.
                    if now-no_progress_since>6:reason='unable_to_advance';break
                    record(True);time.sleep(.15);continue
            else:
                trace=planning_state.get('trace') or {};points=trace.get('points') or []
                at_end=bool(points) and trace.get('enabled') and trace.get('route_type') not in (0,4)
                if missing_since is None:missing_since=now
                if not at_end and now-missing_since<2.5:
                    mode='waiting_for_route';record(True);time.sleep(.1);continue
                if forward_since is None:
                    forward_since=now;forward_heading=state.copy();forward_bursts=0
                    if at_end:
                        dx,dy=points[-1][0]-state['x'],points[-1][1]-state['y']
                        if math.hypot(dx,dy)<1 and len(points)>1:
                            dx,dy=points[-1][0]-points[-2][0],points[-1][1]-points[-2][1]
                        if math.hypot(dx,dy)>=1:
                            # Collision corrections can leave the character facing
                            # away from an exit. Keep the endpoint heading for the
                            # entire bounded crossing attempt, including overshoot.
                            forward_heading['facing']=(6+round(math.atan2(dy,dx)/(math.pi/4)))%8
                if now-forward_since>2:reason='no_map_exit_detected';break
                mode='forward_to_exit';step=forward_step(forward_heading,forward_bursts,diagonal=diagonal)
                if step is None:reason='unknown_facing';break
                forward_bursts+=1
            record(True)
            try:
                result=move(*step,focus=False,quiet=True,expected_map=initial['map'])
            except RuntimeError:
                # A transfer may complete between polling and key-down. The
                # bridge correctly refuses that old-map input; confirm state.
                state=request('status')
                if fresh_state(state) and state.get('phase')=='world' and state.get('map')!=initial['map']:
                    reason='map_changed';break
                if fresh_state(state) and state.get('phase')=='loading_map':continue
                raise
            bursts+=1;state=result['after']
            if state.get('pid')!=initial.get('pid'):reason='session_changed';break
            if state.get('phase')=='world' and state.get('map')!=initial.get('map'):
                reason='map_changed';break
            if state.get('phase')!='world':continue
            before=result['before']
            useful=motion.observe((before['x'],before['y']),(state['x'],state['y']),*step,time.monotonic())
            no_progress_since=motion.last_progress
            if useful:
                stalls=0
                if terrain_map is None:blocked_direction=None
            else:
                stalls+=1;blocked_direction=step[0]
                blocked_route=route_signature;blocked_at=time.monotonic()
                if stalls%2==0:pause_until=time.monotonic()+(.05 if terrain_map and diagonal else .8)
                if local_map and stalls%2==0:
                    try:
                        local_path=local_map.path((state['x'],state['y']),destination);replans+=1
                        (LATEST/'local-path.json').write_text(json.dumps({'source':'local_collision_atlas',
                            'map':state['map'],'start':[state['x'],state['y']],'goal':destination,
                            'points':local_path,'replanned':True},indent=2)+'\n')
                        mode='replanning'
                    except RuntimeError:pass
            print(json.dumps({'map':state.get('map'),'x':state.get('x'),'y':state.get('y'),
                              'steps_remaining':trace.get('steps_remaining'),
                              'direction':step[0],'moved':result['moved'],'mode':mode}),flush=True)
            if terrain_map and not local_map and stalls>=4:reason='unable_to_advance';break
            if time.monotonic()-no_progress_since>6:reason='unable_to_advance';break
    except KeyboardInterrupt:reason='interrupted'
    except Exception:
        reason='control_error';raise
    finally:
        window.close();record(False)
        print('Follow stopped: '+reason+'. State: '+str(report),flush=True)
    return json.loads(report.read_text())


def dismiss_popup():
    with navigation_lease():return _dismiss_popup()


def find_popup_close(screen):
    from PIL import Image
    template_path=ROOT/'linux/ui/popup-close.png'
    if not template_path.exists():return None
    with Image.open(template_path) as source:template=source.convert('RGB')
    screen=screen.convert('RGB');width,height=template.size;screen_width,screen_height=screen.size
    raw=screen.tobytes();needle=template.tobytes();row=needle[:width*3];stride=screen_width*3
    offset=0
    while True:
        offset=raw.find(row,offset)
        if offset<0:return None
        y,x=divmod(offset,stride)
        if x%3==0 and x//3+width<=screen_width and y+height<=screen_height:
            if all(raw[offset+i*stride:offset+i*stride+len(row)]==needle[i*len(row):(i+1)*len(row)] for i in range(height)):
                return x//3+width//2,y+height//2
        offset+=1


def _game_input_state(window):
    state=request('status')
    if not fresh_state(state) or state.get('phase')!='world':raise RuntimeError('No fresh game world state for input.')
    if state.get('pid')!=window.pid:raise RuntimeError('The monitored game session changed.')
    if not window.focused():raise _InteractionFocusLost('Game window lost focus.')
    return state


def press_game_key(window,key):
    key='enter' if key=='Return' else key.lower()
    if key not in {'space','enter','g','x'}:raise ValueError('Unsupported game key.')
    state=_game_input_state(window)
    if key not in (state.get('native_key_input') or []):
        raise RuntimeError('Rebuild the native bridge and restart the monitored game to enable game-only keys.')
    return request('press_key',key=key,milliseconds=120,expected_map=state['map'],expected_pid=window.pid)


def click_game(window,x,y):
    state=_game_input_state(window)
    if state.get('native_click_input') is not True:
        raise RuntimeError('Rebuild the native bridge and restart the monitored game to enable game-only clicks.')
    return request('click',x=x,y=y,expected_map=state['map'],expected_pid=window.pid)


def interact():
    with navigation_lease():return _interact()


class _InteractionFocusLost(RuntimeError):
    pass


def _interact(emit=True,window=None,focus_on_start=True):
    from game_control import GameWindow
    state=request('status')
    if state.get('phase')!='world':raise RuntimeError('Enter the game world before interacting.')
    if not fresh_state(state):raise RuntimeError('No fresh game world state.')
    owns_window=window is None
    if owns_window:window=GameWindow(state['pid'])
    try:
        if window.pid!=state['pid']:raise RuntimeError('The monitored game session changed.')
        if focus_on_start:window.focus()
        if not window.focused():raise _InteractionFocusLost('Game window lost focus.')
        press_game_key(window,'space');time.sleep(.25)
        window.screenshot(LATEST/'after-interact.png')
    finally:
        if owns_window:window.close()
    result=request('status')
    (LATEST/'interaction-state.json').write_text(json.dumps(result,indent=2)+'\n')
    if emit:print(json.dumps(result,indent=2))
    return result


def _quest_step(state):
    if state.get('phase')!='world' or not fresh_state(state):return None
    progress=state.get('main_quest')
    if not isinstance(progress,dict):return None
    values=tuple(progress.get(key) for key in ('chapter','step'))
    return values if all(type(value) is int and value>0 for value in values) else None


def talk(seconds=30,max_pages=12):
    from game_control import GameWindow
    if not 0<seconds<=120 or not 1<=max_pages<=30:raise ValueError('Use 1 to 120 seconds and 1 to 30 pages.')
    with navigation_lease():
        state=request('status');initial=state
        if state.get('phase')!='world':raise RuntimeError('Enter the world before talking.')
        if not fresh_state(state):raise RuntimeError('No fresh game world state.')
        original=_quest_step(initial)
        deadline=time.monotonic()+seconds;pages=0;reason='dialogue_timeout'
        window=GameWindow(state['pid'])
        try:
            window.focus()
            if not state.get('dialogue'):state=_interact(emit=False,window=window,focus_on_start=False)
            while time.monotonic()<deadline:
                if not fresh_state(state):reason='stale_state';break
                if state.get('phase')!='world':reason='screen_changed';break
                if state.get('pid')!=initial['pid']:reason='session_changed';break
                if not window.focused():reason='focus_lost';break
                current=_quest_step(state)
                if original is not None and current is not None and current!=original:
                    reason='quest_progressed';break
                dialogue=state.get('dialogue')
                if not dialogue:reason='dialogue_closed';break
                (LATEST/'dialogue-state.json').write_text(json.dumps(dialogue,indent=2)+'\n')
                if dialogue.get('can_advance'):
                    if pages>=max_pages:reason='page_limit';break
                    print(json.dumps({'page':dialogue.get('page_index'),'pages':dialogue.get('page_count'),'text':dialogue.get('text')}),flush=True)
                    state=_interact(emit=False,window=window,focus_on_start=False);pages+=1
                else:
                    time.sleep(.1);state=request('status')
        except _InteractionFocusLost:
            reason='focus_lost'
        finally:window.close()
        result={'reason':reason,'pages_advanced':pages,'before':initial,'current':state}
        (LATEST/'talk-state.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'reason':reason,'pages_advanced':pages,'main_quest':state.get('main_quest')}),flush=True)
        return result


def scene(seconds=60,max_presses=30):
    """Explicit bounded Space input; scenes and choices are not detected."""
    from game_control import GameWindow
    if not 0<seconds<=120 or type(max_presses) is not int or not 1<=max_presses<=120:
        raise ValueError('Use 1 to 120 seconds and 1 to 120 presses.')
    with navigation_lease():
        state=request('status');initial=state
        original=_quest_step(state)
        if (original is None or type(state.get('pid')) is not int or state['pid']<=0
                or not isinstance(state.get('map'),str) or not state['map']):
            raise RuntimeError('Scene input requires a fresh game world, PID, map, and main-quest progress.')
        deadline=time.monotonic()+seconds;next_press=0;presses=0;reason='time_limit'
        window=GameWindow(state['pid'])
        print('Scene mode sends normal Space presses; Space can confirm choices. No scene or choice detection.',flush=True)
        try:
            window.focus()
            window.screenshot(LATEST/'before-scene.png')
            while time.monotonic()<deadline:
                state=request('status')
                if not fresh_state(state):reason='stale_state';break
                if state.get('phase')!='world':reason='screen_changed';break
                if state.get('pid')!=initial['pid']:reason='session_changed';break
                if state.get('map')!=initial['map']:reason='map_changed';break
                current=_quest_step(state)
                if current is None:reason='invalid_quest_state';break
                if not window.focused():reason='focus_lost';break
                if current!=original:reason='quest_progressed';break
                now=time.monotonic()
                if now>=deadline:break
                if now<next_press:
                    time.sleep(min(.1,next_press-now,deadline-now));continue
                if presses>=max_presses:reason='press_limit';break
                next_press=now+1
                press_game_key(window,'space');presses+=1
        except KeyboardInterrupt:
            reason='interrupted'
        except Exception:
            reason='control_error';raise
        finally:
            try:window.screenshot(LATEST/'after-scene.png')
            finally:
                window.close()
                result={'reason':reason,'presses':presses,'before':initial,'current':state,
                        'before_screenshot':str(LATEST/'before-scene.png'),
                        'after_screenshot':str(LATEST/'after-scene.png')}
                temporary=LATEST/'scene-state.tmp'
                temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(LATEST/'scene-state.json')
                print(json.dumps({'reason':reason,'presses':presses,'main_quest':state.get('main_quest')}),flush=True)
        return result


def _dismiss_popup():
    """Press the game's normal X key after the AI/user sees a popup."""
    from game_control import GameWindow
    status=request('status')
    if status.get('phase')!='world':raise RuntimeError('Popup dismissal is only available in the game world.')
    window=GameWindow(status['pid'])
    try:
        window.focus()
        window.screenshot(LATEST/'before-dismiss.png')
        from PIL import Image
        with Image.open(LATEST/'before-dismiss.png') as screen:button=find_popup_close(screen)
        if button:click_game(window,*button)
        else:press_game_key(window,'x')
        time.sleep(.2);window.screenshot(LATEST/'after-dismiss.png')
    finally:window.close()
    print(('Clicked popup X' if button else 'Pressed X')+'. Screenshot: '+str(LATEST/'after-dismiss.png'),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    for command in ['login','run']:
        task=commands.add_parser(command)
        task.add_argument('--username');task.add_argument('--server')
        task.add_argument('--character');task.add_argument('--restart',action='store_true')
        task.add_argument('--use-filled-password',action='store_true')
        if command=='run':task.add_argument('--demo',action='store_true')
    commands.add_parser('status')
    commands.add_parser('start')
    commands.add_parser('dismiss')
    commands.add_parser('export-world')
    commands.add_parser('quest')
    commands.add_parser('interact')
    dialogue=commands.add_parser('talk');dialogue.add_argument('--seconds',type=float,default=30);dialogue.add_argument('--max-pages',type=int,default=12)
    scene_parser=commands.add_parser('scene',help='Send bounded Space presses for a visually verified scene',
        description='Explicit Space macro: Space can confirm choices. No scene or choice detection.')
    scene_parser.add_argument('--seconds',type=float,default=60)
    scene_parser.add_argument('--max-presses',type=int,default=30)
    movement=commands.add_parser('move');movement.add_argument('direction',choices=['up','down','left','right','up_left','up_right','down_left','down_right'])
    movement.add_argument('--milliseconds',type=int,default=250)
    follow=commands.add_parser('follow');follow.add_argument('--seconds',type=float,default=10)
    follow.add_argument('--continuous',action='store_true',help='Continue on each new map until time expires or interaction is needed')
    navigate=commands.add_parser('navigate',help='Walk to coordinates using the local atlas; no GPS trace required')
    navigate.add_argument('--x',type=float,required=True);navigate.add_argument('--y',type=float,required=True)
    navigate.add_argument('--seconds',type=float,default=30)
    navigate.add_argument('--cross-map',action='store_true',help='Continue briefly at destination to trigger a map exit')
    navigate.add_argument('--map',help='Require this starting map ID before planning')
    args=parser.parse_args()
    if args.command=='status':print(json.dumps(request('status')))
    elif args.command=='start':print(json.dumps(start()))
    elif args.command=='move':move(args.direction,args.milliseconds)
    elif args.command=='follow':follow_trace(args.seconds,continuous=args.continuous)
    elif args.command=='navigate':
        if args.map and request('status').get('map')!=args.map:raise RuntimeError('The current map does not match --map '+args.map)
        follow_trace(args.seconds,(args.x,args.y),args.cross_map)
    elif args.command=='dismiss':dismiss_popup()
    elif args.command=='interact':interact()
    elif args.command=='talk':talk(args.seconds,args.max_pages)
    elif args.command=='scene':scene(args.seconds,args.max_presses)
    elif args.command=='export-world':print(json.dumps(request('export_world')))
    elif args.command=='quest':
        quest=describe_quest(request('status'))
        (LATEST/'quest-state.json').write_text(json.dumps(quest,indent=2)+'\n')
        print(json.dumps(quest,indent=2))
    else:
        login(args.username,args.server,args.character,args.restart,args.use_filled_password)
        if args.command=='run' and args.demo:
            result=move('right',250)
            if result['moved']:move('left',250)
            else:move('down',250)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
