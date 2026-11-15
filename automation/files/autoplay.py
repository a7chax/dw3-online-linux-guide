#!/usr/bin/env python3
"""Persistent DW3 controls with optional normal Space during verified combat."""
import argparse
from contextlib import contextmanager,redirect_stderr,redirect_stdout
from datetime import datetime,timezone
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parent
LATEST=ROOT/'linux/ai-sessions/latest'


class StopRequested(RuntimeError):pass
class InputPaused(RuntimeError):pass


def load_game():
    spec=importlib.util.spec_from_file_location('dw3_autoplay_game',ROOT/'ai-game.py')
    game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)
    return game


def route_endpoint(state):
    trace=state.get('trace') or {};points=trace.get('points') or []
    if not trace.get('enabled') or trace.get('route_type') in (None,0,4) or not points:return None
    point=points[-1]
    if len(point)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in point):return None
    return tuple(point)


def popup_modal_context(state):
    fields={'battle':('active','transitioning','submitted','can_advance'),
            'story':('active','awaiting_choice','choice_count','page_index','can_advance'),
            'dialogue':('entity_id','page_index','page_count','can_advance','choice_count'),
            'inn':('active','state','selected_option','cost_bits','submitted')}
    return tuple(tuple((state.get(kind) or {}).get(key) for key in keys) for kind,keys in fields.items())


def cacheable_trace(trace):
    points=trace.get('points') or []
    return (trace.get('enabled') is True and type(trace.get('route_type')) is int and trace.get('route_type') in (1,2)
            and 0<len(points)<=4096 and all(isinstance(point,(list,tuple)) and len(point)==2
                and all(type(value) in (int,float) and math.isfinite(value) for value in point) for point in points))


def interaction_alignment(state,blocked=False):
    endpoint=route_endpoint(state)
    if endpoint is None:return None
    dx,dy=endpoint[0]-state['x'],endpoint[1]-state['y']
    distance=math.hypot(dx,dy)
    if distance<.5:return None
    if abs(dy)<abs(dx)*.25:direction='right' if dx>0 else 'left'
    elif abs(dy)>abs(dx):direction='down' if dy>0 else 'up'
    else:direction=('down' if dy>0 else 'up')+'_'+('right' if dx>0 else 'left')
    facing={'down':0,'down_left':1,'left':2,'up_left':3,'up':4,'up_right':5,'right':6,'down_right':7}[direction]
    if state.get('facing')==facing and (distance<=16 or blocked):return None
    return direction,50


def policy(state,quest,scene_targets=(),blocked_alignment=False,battle_space=False):
    """Select only operations supported by current, explicit telemetry."""
    battle=state.get('battle') or {}
    if battle.get('active'):
        ready=battle.get('can_advance') is True
        if (battle.get('telemetry_complete') is True and not battle.get('transitioning')
                and not battle.get('submitted') and (ready or battle_space)):
            return 'space','battle_result_ready' if ready else 'battle_input_ready'
        return None,'battle_wait'
    story=state.get('story') or {}
    if story.get('active'):
        if not story.get('telemetry_complete'):return None,'story_telemetry_incomplete'
        if story.get('awaiting_choice') or (story.get('choice_count') or 0)>0:return None,'story_choice'
        if story.get('can_advance') and not story.get('submitted'):return 'space','story_ready'
        return None,'story_wait'
    if state.get('dialogue'):return 'talk','dialogue'
    action=quest.get('required_action')
    if action not in ('talk','enter','zone','drop'):return None,'unknown_action'
    target=(quest.get('chapter'),quest.get('step'),state.get('map'))
    if quest.get('on_target_map') and action in ('enter','zone') and target in scene_targets:
        return 'scene','configured_scene'
    if state.get('movement_ready') is False:return None,'movement_not_ready'
    trace=state.get('trace') or {};endpoint=route_endpoint(state)
    if endpoint is not None:
        if (trace.get('route_type')==2
                and all(isinstance(state.get(k),(int,float)) for k in ('x','y'))
                and math.dist((state['x'],state['y']),endpoint)<24):
            if interaction_alignment(state,blocked_alignment) is not None:return 'align','interaction_alignment'
            return 'talk','interaction_required'
        return 'follow','usable_route'
    if quest.get('on_target_map') and action=='drop':return None,'battle_objective_needs_route_or_combat'
    if trace.get('enabled') and not trace.get('points') and trace.get('route_type')==0:
        return None,'empty_gps_route'
    return None,'gps_disabled_or_unusable'


def fingerprint(state):
    progress=state.get('main_quest') or {};dialogue=state.get('dialogue') or {}
    def cell(value):return math.floor(value/2) if isinstance(value,(int,float)) and math.isfinite(value) else None
    return (state.get('pid'),state.get('map'),progress.get('chapter'),progress.get('step'),
        cell(state.get('x')),cell(state.get('y')),dialogue.get('text_file'),dialogue.get('text_index'),
        dialogue.get('page_index'),bool(dialogue),state.get('facing'),bool((state.get('story') or {}).get('active')),
        bool((state.get('battle') or {}).get('active')))


class Supervisor:
    def __init__(self,game,session,window_factory=None,expected_pid=None,scene_targets=(),
                 stop_file=None,clock=time.monotonic,sleep=time.sleep,
                 repair_with_codex=False,repair_manager=None,battle_space=False,close_popups=True,activity='after-loss'):
        self.game=game;self.session=Path(session).resolve();self.latest_source=Path(game.LATEST)
        self.game.LATEST=self.session
        if window_factory is None:
            from game_control import GameWindow
            window_factory=GameWindow
        self.window_factory=window_factory;self.window=None;self.expected_pid=expected_pid
        self.scene_targets=set(scene_targets);self.stop_file=Path(stop_file) if stop_file else self.session/'autoplay.stop'
        self.clock=clock;self.sleep=sleep;self.active=False;self.cycles=0;self.actions=0;self.progress_events=0
        self.state={};self.quest={};self.last_event=None;self.last_seen=None;self.no_progress=0;self.cooldown=0
        self.empty_since=None;self.last_refresh=-math.inf;self.pending_recovery=None;self.failed_recoveries={}
        self.rejected_gps=None
        self.alignments={};self.blocked_interactions={}
        self.route_context=None;self.cached_route=None;self.was_in_battle=False
        self.post_battle_since=None;self.post_battle_refreshed=False;self.atlas_factory=None
        self.route_cache_file=self.session/'autoplay-route-cache.json'
        try:
            saved=json.loads(self.route_cache_file.read_text())
            identity=tuple(saved['identity'])
            if len(identity)==5 and cacheable_trace(saved['trace']):
                self.route_context=identity;self.cached_route={'identity':identity,'trace':saved['trace']}
                self.was_in_battle=saved.get('battle_pending') is True
        except (OSError,ValueError,KeyError,TypeError):pass
        self.mode='starting';self.reason='starting'
        self.restart_requested=False
        self.battle_space=bool(battle_space)
        self.close_popups=bool(close_popups);self.last_popup_check=-math.inf
        self.repair_manager=repair_manager
        from fishing_goal import FishingGoal
        self.fishing_goal=FishingGoal(self.session,activity=activity,clock=self.clock);self.fishing_decision=None
        from inn_recovery import InnRecovery
        self.inn_recovery=InnRecovery(self.session,clock=self.clock);self.inn_decision=None
        from stall_watch import StallWatch
        self.stall_watch=StallWatch(self.session,clock=self.clock)
        self.stall_trigger=None;self.repair_in_progress=False
        from battle_policy import BattlePlanner
        from supplies_recovery import SuppliesRecovery
        self.battle_planner=BattlePlanner(self.session);self.battle_decision=None
        self.supplies_recovery=SuppliesRecovery(self.session,clock=self.clock);self.supplies_decision=None
        if repair_with_codex and self.repair_manager is None:
            from codex_repair import CodexRepair
            self.repair_manager=CodexRepair(self.session)

    def save_route_cache(self):
        try:
            if self.cached_route is None:
                self.route_cache_file.unlink(missing_ok=True);return
            saved={**self.cached_route,'battle_pending':self.was_in_battle or self.post_battle_since is not None}
            encoded=json.dumps(saved,sort_keys=True)+'\n'
            if self.route_cache_file.exists() and self.route_cache_file.read_text()==encoded:return
            temporary=self.route_cache_file.with_suffix('.tmp');temporary.write_text(encoded)
            temporary.chmod(0o600);temporary.replace(self.route_cache_file)
        except OSError:pass

    def route_identity(self,state):
        progress=state.get('main_quest') or {}
        step=self.game._quest_step(state)
        if (step is None or type(state.get('pid')) is not int or state['pid']<=0
                or not isinstance(state.get('map'),str) or not state['map']
                or not isinstance(progress.get('target_map'),str) or not progress['target_map']):return None
        return (state.get('pid'),state['map'],*step,progress['target_map'])

    def remember_route(self,state):
        identity=self.route_identity(state)
        if identity!=self.route_context:
            self.route_context=identity;self.cached_route=None;self.was_in_battle=False
            self.post_battle_since=None;self.post_battle_refreshed=False
        if identity is None:
            self.save_route_cache();return
        battle=bool((state.get('battle') or {}).get('active'))
        if battle:self.was_in_battle=True
        elif self.was_in_battle:
            self.was_in_battle=False;self.post_battle_since=self.clock()
            self.post_battle_refreshed=False;self.cooldown=0
        trace=state.get('trace') or {};points=trace.get('points') or []
        if not battle and cacheable_trace(trace):
            self.cached_route={'identity':identity,'trace':{
                'enabled':True,'route_type':trace['route_type'],'steps_remaining':trace.get('steps_remaining'),
                'points':[list(point) for point in points]}}
            self.post_battle_since=None;self.post_battle_refreshed=False
        self.save_route_cache()

    def routing_state(self,state):
        trace=state.get('trace') or {}
        if (not self.cached_route or self.cached_route['identity']!=self.route_identity(state)
                or self.post_battle_since is None or not self.post_battle_refreshed
                or self.clock()-self.last_refresh<2 or not trace.get('enabled')
                or trace.get('has_reply') is not False or trace.get('route_type')!=0 or trace.get('points')
                or (state.get('battle') or {}).get('active') or (state.get('story') or {}).get('active')):
            return state
        cached=dict(self.cached_route['trace'])
        progress=state.get('main_quest') or {}
        signature=(state.get('pid'),state.get('map'),progress.get('chapter'),progress.get('step'),tuple(cached['points'][-1]))
        if self.clock()<self.failed_recoveries.get(signature,-math.inf):return state
        if cached['route_type']==2:
            cached['steps_remaining']=math.ceil(math.dist((state['x'],state['y']),cached['points'][-1])/16)
        return {**state,'trace':cached}

    def recover_battle_route(self):
        state=self.game.request('status');self.check_input(state,self.state['map'])
        if route_endpoint(state) is not None:return {'reason':'route_changed','current':state}
        planned=self.routing_state(state)
        if planned is state or state.get('movement_ready') is not True:raise InputPaused('cached_route_changed')
        points=planned['trace']['points'];goal=tuple(points[-1]);target=goal;interaction=planned['trace']['route_type']==2
        try:
            factory=self.atlas_factory
            if factory is None:
                from world_map import WorldMap
                factory=WorldMap
            atlas=factory(state['map'])
            if interaction:goal=atlas.interaction_destination((state['x'],state['y']),target)
            else:atlas.path((state['x'],state['y']),goal)
        except (OSError,ValueError,RuntimeError):raise InputPaused('cached_route_blocked') from None
        self.check_input(state,self.state['map'])
        options={'interaction_target':target} if interaction else {}
        return self.game.follow_trace(seconds=12,destination=goal,cross_map=not interaction,**options)

    def recover_local_route(self):
        state=self.game.request('status');self.check_input(state,self.state['map'])
        signature=self.recovery_signature(state)
        if signature!=self.recovery_signature(self.state):raise InputPaused('route_changed')
        goal=route_endpoint(state)
        if goal is None:return {'reason':'route_changed','current':state}
        interaction=(state.get('trace') or {}).get('route_type')==2;options={}
        if interaction:
            from world_map import NoRouteError,WorldMap
            factory=self.atlas_factory or WorldMap
            try:destination=factory(state['map']).interaction_destination((state['x'],state['y']),goal)
            except NoRouteError:return {'reason':'local_route_unavailable','current':state}
            options['interaction_target']=goal;goal=destination
        verified=self.game.request('status');self.check_input(verified,state['map'])
        if self.recovery_signature(verified)!=signature:raise InputPaused('route_changed')
        return self.game.follow_trace(seconds=15,destination=goal,cross_map=not interaction,**options)

    def maybe_repair(self,reason,error_type=None,*,qualified=False):
        if self.repair_manager is None:return False
        from codex_repair import repair_context,TRIGGERS
        if reason not in TRIGGERS:return False
        context=repair_context(reason,self.state,self.quest,error_type,history=self.stall_watch.history())
        if qualified:
            if not self.repair_manager.eligible(context):return False
        elif not self.repair_manager.observe(context):return False
        # Pause all controller input and prevent another controller interleaving
        # while the isolated code worker or approval request is outstanding.
        self.repair_in_progress=True
        try:
            self.publish('repairing','codex_repair',repair_state_file=str(self.session/'repair-state.json'))
            with self.game.navigation_lease():
                result=self.repair_manager.repair(context,check_stop=self.check_stop)
            self.publish('paused',result['reason'],repair_state_file=str(self.session/'repair-state.json'))
        finally:self.repair_in_progress=False
        if result['restart']:
            self.restart_requested=True
            raise StopRequested('repair_restart')
        return True

    def close_known_popup(self):
        root=getattr(self.game,'ROOT',None)
        if ((self.state.get('inn') or {}).get('active') or not self.close_popups or root is None or self.clock()-self.last_popup_check<2
                or not (Path(root)/'linux/ui/popup-close.png').exists()):return False
        self.last_popup_check=self.clock()
        with self.game.navigation_lease():
            fresh=self.game.request('status');self.check_input(fresh,self.state['map'])
            if fresh.get('native_click_input') is not True:return False
            identity=self.route_identity(fresh)
            modal=popup_modal_context(fresh)
            self.window.screenshot(self.session/'popup-check.png')
            from PIL import Image
            with Image.open(self.session/'popup-check.png') as image:button=self.game.find_popup_close(image)
            # A native PNG can outlive the freshness window. Revalidate the
            # selected game/context after capture, before constructing guards.
            verified=self.game.request('status');self.check_input(verified,fresh['map'])
            if (identity is None or self.route_identity(verified)!=identity
                    or popup_modal_context(verified)!=modal):raise InputPaused('popup_context_changed')
            self.state=verified
            if button is None:return False
            with self.guarded_actions('popup_close'):self.game.click_game(self.window,*button)
            self.wait(.15)
            self.window.screenshot(self.session/'after-popup-close.png')
            with Image.open(self.session/'after-popup-close.png') as image:remaining=self.game.find_popup_close(image)
            self.state=self.game.request('status');self.actions+=1
            if remaining is None:self.no_progress=0;self.cooldown=0
            self.publish('waiting','popup_closed' if remaining is None else 'popup_still_visible',action='popup_close')
            return True

    def check_stop(self):
        if self.stop_file.exists():raise StopRequested('stop_requested')

    def wait(self,seconds):
        deadline=self.clock()+seconds
        while self.clock()<deadline:
            self.check_stop();self.sleep(min(.2,deadline-self.clock()))

    def publish(self,mode,reason,action=None,wait_seconds=0,**extra):
        self.mode=mode;self.reason=reason
        if mode!='stopped' and not self.repair_in_progress:self.record_watch(self.state,reason,action)
        report={'time':datetime.now(timezone.utc).isoformat(),'active':self.active,
            'supervisor_pid':os.getpid(),'game_pid':self.expected_pid,'session':str(self.session),
            'stop_file':str(self.stop_file),'mode':mode,'reason':reason,'action':action,
            'phase':self.state.get('phase'),'map':self.state.get('map'),
            'position':{k:self.state.get(k) for k in ('x','y')} if self.state.get('phase')=='world' else None,
            'quest':{k:self.quest.get(k) for k in ('chapter','step','target_map','required_action','next_action')},
            'cycles':self.cycles,'actions':self.actions,'progress_events':self.progress_events,
            'battle_space_enabled':self.battle_space,'codex_repair_enabled':self.repair_manager is not None,
            'background_input_enabled':self.state.get('native_background_input') is True,
            'inn_recovery':self.inn_recovery.report(),'fishing_goal':self.fishing_goal.report(),'activity':self.fishing_goal.activity,
            'supplies_recovery':self.supplies_recovery.report(),
            'tactical_battle_enabled':self.battle_space and self.state.get('native_battle_control') is True,
            'stall_repair_pending':self.stall_trigger['reason'] if self.stall_trigger else None,
            'repair_game_state_log':str(self.stall_watch.path),
            'cached_route_available':self.cached_route is not None,'post_battle_recovery':self.post_battle_since is not None,
            'no_progress_cycles':self.no_progress,'wait_seconds':round(wait_seconds,2),**extra}
        temporary=self.session/'autoplay-state.tmp';temporary.write_text(json.dumps(report,indent=2)+'\n')
        temporary.replace(self.session/'autoplay-state.json')
        key=(mode,reason,action,fingerprint(self.state),self.no_progress)
        if key!=self.last_event:
            with (self.session/'autoplay-events.jsonl').open('a') as output:output.write(json.dumps(report)+'\n')
            self.last_event=key

    @staticmethod
    def stall_identity(state):
        quest=state.get('main_quest') or {}
        def cell(value,size):return math.floor(value/size) if isinstance(value,(int,float)) and math.isfinite(value) else None
        return (state.get('pid'),state.get('map'),quest.get('chapter'),quest.get('step'),quest.get('target_map'),
                cell(state.get('x'),8),cell(state.get('y'),4),route_endpoint(state))

    def record_watch(self,state,reason,action=None):
        identity=self.stall_identity(state)
        if self.stall_trigger and (self.stall_trigger['identity']!=identity or
                (self.stall_trigger.get('modal') is not None and self.stall_trigger['modal']!=self.stall_modal_identity(state))):
            self.stall_trigger=None
        trigger=self.stall_watch.observe(state,reason,action)
        if trigger:
            self.stall_trigger={'reason':trigger,'identity':identity,
                                'modal':None if trigger=='navigation_stalled' else self.stall_modal_identity(state)}

    @staticmethod
    def stall_modal_identity(state):
        from stall_watch import sanitize_state
        safe=sanitize_state(state)
        return json.dumps({key:safe[key] for key in ('battle','story','dialogue','inn')},sort_keys=True)

    @staticmethod
    def stall_repair_allowed(state,reason):
        battle=state.get('battle') or {};story=state.get('story') or {};inn=state.get('inn') or {}
        if reason=='navigation_stalled':
            return state.get('movement_ready') is True and not any((battle.get('active'),story.get('active'),inn.get('active'),state.get('dialogue')))
        for modal in (battle,story,inn,state.get('dialogue') or {}):
            if not modal:continue
            if (modal.get('typing') or modal.get('awaiting_choice') or (modal.get('choice_count') or 0)>0
                    or modal.get('transitioning') or modal.get('submitted')):return False
        story_ready=(story.get('active') is True and story.get('telemetry_complete') is True
                     and story.get('typing') is False and not battle.get('active'))
        if reason=='story_stalled':return story_ready
        if reason=='input_guard_stalled':
            dialogue=state.get('dialogue') or {}
            return bool((battle.get('active') and battle.get('telemetry_complete') is True)
                        or story_ready or (inn.get('active') and inn.get('telemetry_complete') is True and inn.get('can_confirm') is True)
                        or (dialogue and dialogue.get('typing') is False and dialogue.get('can_advance') is True))
        return False

    def pause(self,reason,seconds=1):
        self.publish('paused',reason,wait_seconds=seconds);self.wait(seconds)

    def ensure_window(self):
        if self.window is None:
            with self.game.navigation_lease():
                candidate=self.window_factory(self.expected_pid)
                try:
                    if self.state.get('native_background_input') is not True:candidate.focus()
                except Exception:candidate.close();raise
                self.window=candidate
        if self.state.get('native_background_input') is not True and not self.window.focused():raise InputPaused('focus_lost')

    def check_input(self,state=None,expected_map=None):
        self.check_stop()
        if self.latest_source.resolve()!=self.session:raise InputPaused('session_changed')
        if not self.window:raise InputPaused('input_unavailable')
        current=self.state if state is None else state
        if current.get('native_background_input') is not True and not self.window.focused():raise InputPaused('focus_lost')
        if state is not None:
            if not self.game.fresh_state(state):raise InputPaused('stale_state')
            if state.get('phase')!='world':raise InputPaused('screen_changed')
            if state.get('pid')!=self.expected_pid:raise InputPaused('session_changed')
            if expected_map is not None and state.get('map')!=expected_map:raise InputPaused('map_changed')

    @contextmanager
    def guarded_actions(self,action):
        # Existing actions normally activate their own windows. Their temporary
        # proxy only verifies ownership, so repeated cycles cannot reclaim focus.
        import game_control
        original_factory=game_control.GameWindow
        original_request=self.game.request;original_press=self.game.press_game_key
        owner=self
        expected_map=self.state['map'];expected_quest=self.game._quest_step(self.state)
        expected_route_identity=self.route_identity(self.state)
        expected_popup_modal=popup_modal_context(self.state)
        expected_modal='battle' if (self.state.get('battle') or {}).get('active') else 'story'
        g_presses=0
        class FocusGuard:
            def __init__(self,window):self.window=window
            def __getattr__(self,name):return getattr(self.window,name)
            def focus(self):
                owner.check_input()
        def factory(pid):
            owner.check_input()
            if pid!=owner.expected_pid:raise InputPaused('session_changed')
            return FocusGuard(owner.window_factory(pid))
        def request(operation,**parameters):
            owner.check_input()
            result=original_request(operation,**parameters)
            if operation=='status':
                owner.check_input(result)
                owner.record_watch(result,'poll');owner.fishing_goal.observe(result)
                fishing=result.get('fishing') or {}
                if (action=='fishing_travel' and owner.fishing_goal.fishing and not owner.fishing_goal.saved.get('refresh_lake')
                        and result.get('map') in ('s380','s381','s950') and fishing.get('telemetry_complete') is True
                        and fishing.get('at_spot') is True):raise InputPaused('fishing_spot_detected')
                if action in ('cached_recovery','popup_close'):
                    owner.check_input(result,expected_map)
                    if owner.route_identity(result)!=expected_route_identity:raise InputPaused('cached_route_changed')
                    if action=='popup_close' and popup_modal_context(result)!=expected_popup_modal:raise InputPaused('popup_context_changed')
                owner.remember_route(result)
            return result
        def press(window,key):
            nonlocal g_presses
            owner.check_input()
            fresh=original_request('status')
            owner.check_input(fresh,expected_map)
            if owner.game._quest_step(fresh)!=expected_quest:raise InputPaused('quest_changed')
            battle=fresh.get('battle') or {};story=fresh.get('story') or {}
            if key=='space':
                if action=='supplies_interact':
                    decision=owner.supplies_recovery.decide(fresh)
                    if not decision or decision.get('action')!=action:raise InputPaused('shop_state_changed')
                    if (decision.get('npc') or {}).get('entity_id')!=(owner.supplies_decision.get('npc') or {}).get('entity_id'):
                        raise InputPaused('merchant_changed')
                elif action in ('inn_stay','inn_interact'):
                    decision=owner.inn_recovery.decide(fresh)
                    if not decision or decision.get('action')!=action:raise InputPaused('inn_state_changed')
                    if action=='inn_stay' and decision.get('cost_bits')!=owner.inn_decision.get('cost_bits'):
                        raise InputPaused('inn_price_changed')
                elif action=='space':
                    modal=battle if expected_modal=='battle' else story
                    ready=(modal.get('active') and modal.get('telemetry_complete') is True
                           and modal.get('can_advance') is True and not modal.get('submitted'))
                    if expected_modal=='battle':
                        ready=(modal.get('active') and modal.get('telemetry_complete') is True
                               and not modal.get('transitioning') and not modal.get('submitted')
                               and (modal.get('can_advance') is True or owner.battle_space))
                        completed_story=(story.get('telemetry_complete') is True and story.get('script_complete') is True
                                         and story.get('typing') is False and story.get('awaiting_choice') is False
                                         and story.get('choice_count')==0 and story.get('submitted') is False)
                        if story.get('active') and not completed_story:ready=False
                    if expected_modal=='story' and (battle.get('active') or story.get('awaiting_choice')
                            or (story.get('choice_count') or 0)>0):ready=False
                    if not ready:raise InputPaused('modal_changed')
                elif battle.get('active') or story.get('active'):
                    raise InputPaused('modal_changed')
                elif action=='talk':
                    dialogue=fresh.get('dialogue') or {}
                    if dialogue:
                        if not dialogue.get('can_advance'):raise InputPaused('dialogue_typing')
                    elif fresh.get('movement_ready') is not True or policy(owner.routing_state(fresh),owner.game.describe_quest(fresh),owner.scene_targets,owner.boundary_ready(fresh))[0]!='talk':
                        raise InputPaused('interaction_changed')
                elif action=='scene':
                    if policy(fresh,owner.game.describe_quest(fresh),owner.scene_targets)[0]!='scene':
                        raise InputPaused('scene_changed')
            elif key=='g':
                trace=fresh.get('trace') or {}
                if battle.get('active') or story.get('active') or fresh.get('movement_ready') is False:
                    raise InputPaused('modal_changed')
                if owner.route_identity(fresh)!=expected_route_identity:raise InputPaused('quest_changed')
                if ((g_presses==0 and not owner.gps_refreshable(fresh))
                        or (g_presses>0 and trace.get('enabled') is not False)):
                    raise InputPaused('route_changed')
                g_presses+=1
            owner.check_input(fresh,expected_map)
            return original_press(window,key)
        game_control.GameWindow=factory;self.game.request=request;self.game.press_game_key=press
        try:yield
        finally:
            game_control.GameWindow=original_factory;self.game.request=original_request;self.game.press_game_key=original_press

    def gps_signature(self,state):
        trace=state.get('trace') or {};identity=self.route_identity(state)
        # Static rejection applies to both travel and NPC routes. Keep the
        # type in the signature so changing it invalidates refresh permission.
        if (identity is None or state.get('movement_ready') is not True or state.get('dialogue')
                or any((state.get(key) or {}).get('active') for key in ('battle','story','inn'))
                or not cacheable_trace(trace)):return None
        return identity,state.get('x'),state.get('y'),trace['route_type'],tuple(tuple(point) for point in trace['points'])

    def gps_refreshable(self,state):
        trace=state.get('trace') or {}
        return bool((trace.get('enabled') and not trace.get('points') and trace.get('route_type')==0)
                    or (self.rejected_gps is not None and self.gps_signature(state)==self.rejected_gps))

    def gps_refresh(self):
        self.last_refresh=self.clock();expected_map=self.state['map']
        with self.game.navigation_lease():
            state=self.game.request('status');self.check_input(state,expected_map)
            if not self.gps_refreshable(state):
                return {'reason':'route_changed','current':state}
            self.game.press_game_key(self.window,'g');self.wait(.25)
            state=self.game.request('status');self.check_input(state,expected_map)
            # Do not blindly send a second toggle if the first did not disable GPS.
            if (state.get('trace') or {}).get('enabled') is False:
                self.game.press_game_key(self.window,'g');self.wait(.25)
                state=self.game.request('status');self.check_input(state,expected_map)
            return {'reason':'gps_refresh_attempted','current':state}

    def recovery_signature(self,state):
        state=self.routing_state(state)
        progress=state.get('main_quest') or {}
        return (state.get('pid'),state.get('map'),progress.get('chapter'),progress.get('step'),route_endpoint(state))

    def boundary_ready(self,state):
        return self.clock()-self.blocked_interactions.get(self.recovery_signature(state),-math.inf)<30

    def align_interaction(self):
        expected_map=self.state['map'];expected_quest=self.game._quest_step(self.state)
        with self.game.navigation_lease():
            state=self.game.request('status');self.check_input(state,expected_map)
            if self.game._quest_step(state)!=expected_quest:raise InputPaused('quest_changed')
            if (state.get('movement_ready') is not True or
                    policy(self.routing_state(state),self.game.describe_quest(state),self.scene_targets,self.boundary_ready(state))[0]!='align'):
                raise InputPaused('interaction_changed')
            step=interaction_alignment(self.routing_state(state))
            signature=self.recovery_signature(state)
            attempt=(signature,round(state['x'],1),round(state['y'],1),step[0])
            if self.clock()-self.alignments.get(attempt,-math.inf)<30:
                raise InputPaused('interaction_alignment_backoff')
            self.alignments[attempt]=self.clock()
            result=self.game.move(*step,focus=False,quiet=True,expected_map=expected_map)
            after=result['after'];self.check_input(after,expected_map)
            if (self.recovery_signature(after)==signature
                    and math.dist((state['x'],state['y']),(after['x'],after['y']))<2
                    and interaction_alignment(after,blocked=True) is None):
                self.blocked_interactions[signature]=self.clock()
            return {'reason':'interaction_alignment_attempted','current':after}

    def perform_fishing_action(self,action):
        fresh=self.game.request('status');self.check_input(fresh,self.state['map'])
        decision=self.fishing_goal.decide(fresh)
        if not decision or decision.get('action')!=action:raise InputPaused('fishing_state_changed')
        self.fishing_decision=decision
        if action=='fishing_travel':
            return self.game.follow_trace(seconds=12,destination=tuple(decision['destination']),cross_map=decision['cross_map'])
        if action=='fishing_align':
            with self.game.navigation_lease():
                result=self.game.move(*decision['step'],focus=False,quiet=True,expected_map=fresh['map'],expected_pid=self.expected_pid)
                return {'reason':'fishing_alignment_attempted','current':result['after']}
        if action in ('fishing_cast','fishing_reel','fishing_reel_attempt','fishing_exhausted'):
            if fresh.get('native_fishing_control') is not True:raise InputPaused('fishing_control_unavailable')
            with self.game.navigation_lease():
                reply=self.game.request('fishing_step',mode=action.removeprefix('fishing_'),
                    expected_state_token=decision['expected_token'],**self.automation_parameters(fresh))
            plan=reply.get('plan') or {}
            return {'reason':plan.get('reason','fishing_wait'),'current':reply.get('after') or self.game.request('status')}
        raise InputPaused('fishing_control_unavailable')

    def perform_inn_action(self,action):
        expected_map=self.state['map']
        fresh=self.game.request('status');self.check_input(fresh,expected_map)
        decision=self.inn_recovery.decide(fresh)
        if not decision or decision.get('action')!=action:raise InputPaused('inn_state_changed')
        self.inn_decision=decision
        if action=='inn_travel':
            goal=tuple(decision['destination']);options={}
            if decision.get('npc'):
                from world_map import NoRouteError,WorldMap
                try:destination=WorldMap(expected_map).interaction_destination((fresh['x'],fresh['y']),goal)
                except NoRouteError:return {'reason':'local_route_unavailable','current':fresh}
                options['interaction_target']=goal;goal=destination
            return self.game.follow_trace(seconds=12,destination=goal,cross_map=decision['cross_map'],**options)
        with self.game.navigation_lease():
            if action=='inn_align':
                result=self.game.move(*decision['step'],focus=False,quiet=True,expected_map=expected_map,expected_pid=self.expected_pid)
                return {'reason':'inn_alignment_attempted','current':result['after']}
            self.game.press_game_key(self.window,'space');self.wait(.25)
            return {'reason':'inn_stay_submitted' if action=='inn_stay' else 'inn_interaction_attempted',
                    'current':self.game.request('status')}

    def automation_parameters(self,state):
        quest=state.get('main_quest') or {}
        return {'expected_map':state['map'],'expected_pid':self.expected_pid,
                'expected_quest':{k:quest.get(k) for k in ('chapter','step')}}

    @staticmethod
    def battle_story_allowed(state):
        story=state.get('story') or {}
        return not story.get('active') or (story.get('telemetry_complete') is True and story.get('script_complete') is True
                    and story.get('typing') is False and story.get('awaiting_choice') is False
                    and story.get('choice_count')==0 and story.get('submitted') is False)

    def perform_battle_action(self,decision):
        attempted=False
        try:
            with self.game.navigation_lease():
                before=self.game.request('status');self.check_input(before,self.state['map'])
                if self.game._quest_step(before)!=self.game._quest_step(self.state):raise InputPaused('quest_changed')
                if before.get('native_battle_control') is not True:raise InputPaused('battle_control_unavailable')
                battle=before.get('battle') or {}
                if not self.battle_story_allowed(before):raise InputPaused('modal_changed')
                if not battle.get('command_ready') or battle.get('menu_token')!=decision['expected_token']:
                    raise InputPaused('battle_menu_changed')
                parameters={k:decision[k] for k in ('expected_token','option_index','target_group') if k in decision}
                operation='battle_back' if decision.get('back') else 'battle_choose'
                attempted=True
                reply=self.game.request(operation,**parameters,**self.automation_parameters(before))
                after=reply.get('after') or self.game.request('status')
                self.battle_planner.note_result(decision,before,after)
                return {'reason':'battle_menu_action','current':after}
        except BaseException:
            # Only a proven local pre-dispatch failure may release a token.
            # A missing RPC reply can mean the action was already accepted.
            if not attempted:self.battle_planner.cancel(decision)
            raise

    def perform_supplies_action(self,action):
        expected_map=self.state['map'];fresh=self.game.request('status');self.check_input(fresh,expected_map)
        decision=self.supplies_recovery.decide(fresh)
        if not decision or decision.get('action')!=action:raise InputPaused('supplies_state_changed')
        self.supplies_decision=decision
        if action=='supplies_travel':
            goal=tuple(decision['destination']);options={}
            if decision.get('npc'):
                from world_map import WorldMap,NoRouteError
                try:destination=WorldMap(expected_map).interaction_destination((fresh['x'],fresh['y']),goal)
                except NoRouteError:return {'reason':'local_route_unavailable','current':fresh}
                options['interaction_target']=goal;goal=destination
            return self.game.follow_trace(seconds=12,destination=goal,cross_map=decision['cross_map'],**options)
        with self.game.navigation_lease():
            if action=='supplies_align':
                result=self.game.move(*decision['step'],focus=False,quiet=True,expected_map=expected_map,expected_pid=self.expected_pid)
                return {'reason':'shop_alignment_attempted','current':result['after']}
            if action=='supplies_interact':
                self.game.press_game_key(self.window,'space');self.wait(.25)
                return {'reason':'shop_interaction_attempted','current':self.game.request('status')}
            parameters={k:decision[k] for k in ('mode','item_id','party_slot','quantity','unit_bits','expected_offer_token',
                         'expected_state_token','reserve_bits','max_total_bits') if k in decision}
            reply=self.game.request('supplies_step',**parameters,**self.automation_parameters(fresh))
            plan=reply.get('plan') or {}
            return {'reason':plan.get('reason','supplies_step'),'current':reply.get('after') or self.game.request('status'),'plan':plan}

    def cycle(self):
        self.cycles+=1;self.check_stop()
        try:self.state=self.game.request('status')
        except StopRequested:raise
        except Exception:
            self.pause('status_unavailable',2);return
        if self.latest_source.resolve()!=self.session:self.pause('session_changed',2);return
        if not self.game.fresh_state(self.state):self.pause('stale_state',2);return
        if self.state.get('phase')!='world':self.pause('not_in_world',2);return
        pid=self.state.get('pid')
        if type(pid) is not int or pid<=0:self.pause('invalid_game_pid',2);return
        if self.expected_pid is None:self.expected_pid=pid
        if pid!=self.expected_pid:self.pause('session_changed',2);return
        if self.game._quest_step(self.state) is None:self.pause('invalid_quest_state',2);return
        try:self.quest=self.game.describe_quest(self.state)
        except Exception:self.pause('unknown_quest',2);return
        self.record_watch(self.state,'poll')
        pending=self.stall_trigger
        if (pending and pending['identity']==self.stall_identity(self.state)
                and self.stall_repair_allowed(self.state,pending['reason'])):
            if self.maybe_repair(pending['reason'],qualified=True):self.stall_trigger=None;return
        elif pending:self.stall_trigger=None
        self.remember_route(self.state)
        try:self.ensure_window()
        except InputPaused as error:self.pause(str(error));return
        except Exception:self.pause('input_unavailable',2);return
        try:
            if self.close_known_popup():return
        except StopRequested:raise
        except InputPaused as error:self.pause(str(error));return
        except Exception:self.pause('popup_check_failed',2);return
        self.fishing_goal.observe(self.state)
        self.battle_planner.observe(self.state)
        current=fingerprint(self.state)
        if self.last_seen is not None and current!=self.last_seen:
            self.no_progress=0;self.cooldown=0
        self.last_seen=current
        planning=self.routing_state(self.state)
        self.fishing_decision=self.fishing_goal.decide(self.state)
        self.inn_decision=None if self.fishing_goal.fishing else self.inn_recovery.decide(self.state)
        self.supplies_decision=None if self.inn_decision or self.fishing_goal.fishing else self.supplies_recovery.decide(self.state)
        self.battle_decision=None
        if self.fishing_decision:
            action,reason=self.fishing_decision['action'],self.fishing_decision['reason']
        elif self.inn_decision:
            action,reason=self.inn_decision['action'],self.inn_decision['reason']
            if action=='inn_recovered':
                self.cooldown=0;self.no_progress=0;self.progress_events+=1
                self.publish('waiting',reason,action=action);return
        elif self.supplies_decision:
            action,reason=self.supplies_decision['action'],self.supplies_decision['reason']
        else:
            action,reason=policy(planning,self.quest,self.scene_targets,self.boundary_ready(self.state),self.battle_space)
            if planning is not self.state and action=='follow':action='cached_recovery';reason='post_battle_cached_route'
        battle=self.state.get('battle') or {}
        if self.battle_space and self.state.get('native_battle_control') is True and battle.get('active') and not battle.get('can_advance'):
            self.battle_decision=self.battle_planner.decide(self.state) if self.battle_story_allowed(self.state) else None
            action='battle_back' if self.battle_decision and self.battle_decision.get('back') else ('battle_choice' if self.battle_decision else None)
            reason=self.battle_decision['reason'] if self.battle_decision else ('modal_changed' if battle.get('command_ready') and self.battle_story_allowed(self.state) else 'battle_tactics_wait')
        now=self.clock()
        if self.rejected_gps is not None:
            if (self.gps_signature(self.state)!=self.rejected_gps
                    or now>=self.failed_recoveries.get(self.recovery_signature(self.state),-math.inf)):
                self.rejected_gps=None
            elif action=='follow':
                # A nonempty GPS reply can cross disconnected collision regions.
                # Replace that rejected route rather than following it again.
                action='gps_refresh' if now-self.last_refresh>=30 else None
                reason='unreachable_gps_route'
        if reason=='empty_gps_route':
            if self.empty_since is None:self.empty_since=now
            if (self.post_battle_since is not None and not self.post_battle_refreshed
                    and (self.state.get('trace') or {}).get('has_reply') is False):
                action='gps_refresh';reason='post_battle_gps_refresh';self.post_battle_refreshed=True;self.cooldown=0
            elif now-self.empty_since>=10 and now-self.last_refresh>=30:action='gps_refresh'
        else:self.empty_since=None
        if action is None:
            if reason=='modal_changed' and battle.get('command_ready'):self.record_watch(self.state,reason,'battle_choice')
            self.maybe_repair(reason)
            self.pause(reason,.05 if reason=='fishing_wait_timing' else 1);return
        if now<self.cooldown and not action.startswith(('inn_','supplies_','battle_')):self.pause('no_progress_backoff',min(1,self.cooldown-now));return
        signature=self.recovery_signature(self.state)
        if action=='follow' and self.pending_recovery==signature:
            action='local_recovery';self.pending_recovery=None
        self.publish('acting',reason,action=action)
        try:
            with self.guarded_actions(action),(self.session/'autoplay-actions.log').open('a') as log,redirect_stdout(log),redirect_stderr(log):
                if action.startswith('fishing_'):result=self.perform_fishing_action(action)
                elif action.startswith('battle_'):result=self.perform_battle_action(self.battle_decision)
                elif action.startswith('supplies_'):result=self.perform_supplies_action(action)
                elif action.startswith('inn_'):result=self.perform_inn_action(action)
                elif action=='align':result=self.align_interaction()
                elif action=='talk':result=self.game.talk(seconds=12,max_pages=6)
                elif action=='space':result=self.game.scene(seconds=1,max_presses=1)
                elif action=='scene':result=self.game.scene(seconds=8,max_presses=4)
                elif action=='gps_refresh':result=self.gps_refresh()
                elif action=='cached_recovery':result=self.recover_battle_route()
                elif action=='local_recovery':
                    result=self.recover_local_route()
                else:result=self.game.follow_trace(seconds=12,continuous=True)
        except StopRequested:raise
        except InputPaused as error:
            if action=='gps_refresh' and self.post_battle_since is not None:self.post_battle_refreshed=False
            if action=='cached_recovery' and str(error)=='cached_route_blocked':
                self.failed_recoveries[signature]=self.clock()+60
            self.pause(str(error));return
        except Exception as error:
            from game_control import WindowUnavailable
            if isinstance(error,WindowUnavailable):self.pause('window_unavailable',1);return
            self.no_progress+=1;self.cooldown=self.clock()+min(60,2**min(self.no_progress,6))
            self.publish('paused','action_failed',action=action,error_type=type(error).__name__)
            self.maybe_repair('action_failed',type(error).__name__)
            self.wait(1);return
        self.actions+=1
        if action.startswith('fishing_'):self.fishing_goal.note_result(self.fishing_decision,result)
        if action.startswith('inn_'):self.inn_recovery.note_result(self.inn_decision,result)
        if action.startswith('supplies_'):self.supplies_recovery.note_result(self.supplies_decision,result)
        after=result.get('current',self.state);result_reason=result.get('reason','unknown_result')
        self.fishing_goal.observe(after)
        self.remember_route(after)
        interrupted=bool((after.get('battle') or {}).get('active') or (after.get('story') or {}).get('active'))
        if fingerprint(after)!=current:
            self.progress_events+=1;self.no_progress=0;self.cooldown=0
        # Ready story/result pages need not change position or quest. Their
        # freshly verified Space action already has its own one-second bound.
        elif action in ('battle_choice','battle_back','supplies_step','fishing_cast','fishing_reel','fishing_reel_attempt','fishing_exhausted'):
            self.cooldown=0
        elif not (interrupted and action in ('follow','local_recovery','cached_recovery','space')):
            self.no_progress+=1;self.cooldown=self.clock()+min(60,2**min(self.no_progress,6))
        self.state=after;self.last_seen=fingerprint(after)
        if action=='follow' and result_reason=='unable_to_advance' and not interrupted:
            if self.clock()>=self.failed_recoveries.get(signature,-math.inf):self.pending_recovery=signature
        if action=='local_recovery' and not interrupted and result_reason not in ('map_changed','destination_reached'):
            self.failed_recoveries[signature]=self.clock()+60
            if result_reason=='local_route_unavailable':
                self.rejected_gps=self.gps_signature(after)
                if self.rejected_gps is not None:
                    # Movement backoff must not outlive rejection permission
                    # before a rate-limited GPS refresh can run.
                    self.cooldown=min(self.cooldown,max(self.clock(),self.last_refresh+30))
            if result_reason in ('unable_to_advance','no_map_exit_detected'):
                self.maybe_repair('local_recovery_failed')
        self.publish('waiting',result_reason,action=action,
            navigation_source='local_collision_atlas' if action in ('local_recovery','cached_recovery') else ('server_gps' if action=='follow' else None))
        self.wait(1)

    def run(self,max_cycles=None):
        if max_cycles is not None and (type(max_cycles) is not int or max_cycles<1):
            raise ValueError('--max-cycles must be a positive integer.')
        self.session.mkdir(parents=True,exist_ok=True)
        with (self.session/'autoplay.lock').open('a+') as lease:
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Autoplay is already running for this session.')
            lease.seek(0);lease.truncate();lease.write(str(os.getpid())+'\n');lease.flush()
            self.active=True;reason='max_cycles';start_cycles=self.cycles
            try:
                while max_cycles is None or self.cycles-start_cycles<max_cycles:self.cycle()
            except StopRequested as error:reason=str(error)
            except KeyboardInterrupt:reason='interrupted'
            except Exception:
                reason='supervisor_error';raise
            finally:
                self.active=False
                if self.window:self.window.close();self.window=None
                self.publish('stopped',reason,last_cycle_reason=self.reason)
        return json.loads((self.session/'autoplay-state.json').read_text())


def scene_target(value):
    try:
        chapter,step,map_id=value.split(':',2);chapter=int(chapter);step=int(step)
        if chapter<1 or step<1 or not map_id:raise ValueError
        return chapter,step,map_id
    except ValueError:raise argparse.ArgumentTypeError('Use CHAPTER:STEP:MAP, for example 5:2:s475.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activity',choices=('main-quest','fishing','after-loss'),default='main-quest')
    parser.add_argument('--session',type=Path,default=LATEST,help='Monitored session directory (resolved once)')
    parser.add_argument('--max-cycles',type=int,help='Bound iterations for a deliberate test run; default is unlimited')
    parser.add_argument('--pid',type=int,help='Require this game PID instead of binding the first fresh world PID')
    parser.add_argument('--stop-file',type=Path,help='Override the session autoplay.stop flag')
    parser.add_argument('--scene-target',action='append',type=scene_target,default=[],
        help='Explicitly allow an unhooked scene at CHAPTER:STEP:MAP; Space can confirm choices')
    parser.add_argument('--resume',action='store_true',help='Remove a previous stop flag before starting')
    parser.add_argument('--battle-space',action='store_true',help='Enable tactical skills/items on a capable bridge; use normal Space for results and legacy combat')
    parser.add_argument('--repair-with-codex',action='store_true',help='Pause and request a bounded Codex repair after repeated genuine controller failures')
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--status',action='store_true',help='Print the saved supervisor state without input')
    modes.add_argument('--stop',action='store_true',help='Request the supervisor to stop without sending game input')
    args=parser.parse_args();session=args.session.resolve(strict=True)
    stop_file=args.stop_file.resolve() if args.stop_file else session/'autoplay.stop'
    if args.status:
        print((session/'autoplay-state.json').read_text(),end='');return
    if args.stop:
        stop_file.write_text(datetime.now(timezone.utc).isoformat()+'\n')
        print(json.dumps({'stop_requested':True,'stop_file':str(stop_file)}));return
    if args.pid is not None and args.pid<=0:raise ValueError('--pid must be positive.')
    if args.resume:stop_file.unlink(missing_ok=True)
    def terminate(signum,frame):raise StopRequested('termination_requested')
    signal.signal(signal.SIGTERM,terminate)
    supervisor=Supervisor(load_game(),session,expected_pid=args.pid,scene_targets=args.scene_target,stop_file=stop_file,repair_with_codex=args.repair_with_codex,battle_space=args.battle_space,activity=args.activity)
    print(json.dumps({'session':str(session),'state_file':str(session/'autoplay-state.json'),'supervisor_pid':os.getpid()}),flush=True)
    supervisor.run(args.max_cycles)
    if supervisor.restart_requested and not stop_file.exists():
        from codex_repair import restart_arguments
        # run() has closed its window and both controller leases before exec.
        os.execv(sys.executable,restart_arguments(sys.argv[1:],session,supervisor.expected_pid))


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError) as error:raise SystemExit(str(error))
