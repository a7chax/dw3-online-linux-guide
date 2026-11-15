"""Bounded, private state history and conservative controller liveness checks.

Call observe with a freshly validated control snapshot. This module does not
poll the game, parse wall-clock timestamps, send input, or spawn repair workers.
"""
from collections import OrderedDict,deque
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

NAV_FAILURES={'unable_to_advance','no_map_exit_detected','local_route_unavailable'}
NAV_ACTIONS={'follow','navigate','move','inn_travel','align_interaction','inn_align','local_recovery','cached_recovery','supplies_travel','supplies_align'}
ACTIONS=NAV_ACTIONS|{'talk','space','scene','story_space','battle_space','inn_interact','inn_stay',
                     'gps_refresh','popup_close','dismiss','poll','wait','battle_choice','battle_back','supplies_step','supplies_interact'}
REASONS=NAV_FAILURES|{'poll','modal_changed','no_progress_backoff','time_limit','battle_space',
    'story_space','dialogue_closed','press_limit','max_cycles','action_failed','focus_lost',
    'stale_state','loading_map','session_changed','stop_requested','inn_insufficient_bit',
    'navigation_stalled','input_guard_stalled','story_stalled'}


def _number(value):
    return type(value) in (int,float) and abs(value)<1e12 and math.isfinite(value)


def _fields(source,numbers=(),flags=()):
    source=source if isinstance(source,dict) else {}
    return {**{k:source[k] for k in numbers if _number(source.get(k))},
            **{k:source[k] for k in flags if type(source.get(k)) is bool}}


def _map(value):
    return value if isinstance(value,str) and re.fullmatch(r's\d{1,6}',value) else None


def sanitize_state(state):
    """Copy only bounded numeric state and known flags; never text/identity."""
    state=state if isinstance(state,dict) else {}
    safe=_fields(state,('pid','x','y','facing'),('movement_ready','native_background_input','window_focused','window_minimized'))
    phase=state.get('phase')
    safe['phase']=phase if isinstance(phase,str) and phase in {'world','starting','login','character_selection','loading_map','other_screen'} else 'unknown'
    if _map(state.get('map')):safe['map']=state['map']
    quest=state.get('main_quest') or {}
    safe['main_quest']=_fields(quest,('chapter','step'))
    if isinstance(quest,dict) and _map(quest.get('target_map')):safe['main_quest']['target_map']=quest['target_map']
    trace=state.get('trace') or {};trace=trace if isinstance(trace,dict) else {}
    safe['trace']=_fields(trace,('route_type','steps_remaining'),('enabled','has_reply','auto_walk'))
    points=trace.get('points');points=points if isinstance(points,list) else []
    valid=lambda p:isinstance(p,(tuple,list)) and len(p)==2 and all(_number(v) for v in p)
    safe['trace']['points']=[list(p) for p in points[:32] if valid(p)]
    endpoint=trace.get('endpoint')
    if valid(endpoint):safe['trace']['endpoint']=list(endpoint)
    elif points and valid(points[-1]):safe['trace']['endpoint']=list(points[-1])
    party=state.get('party') or {};party=party if isinstance(party,dict) else {}
    safe['party']=_fields(party,('count',),('telemetry_complete',))
    members=party.get('members');members=members if isinstance(members,list) else []
    safe['party']['members']=[_fields(m,('id','species_id','slot','hp','max_hp')) for m in members[:32]]
    safe['wallet']=_fields(state.get('wallet'),('bits','cash'),('telemetry_complete',))
    safe['inn']=_fields(state.get('inn'),('cost_bits','selected_option','digimon_count','party_count','name_index'),
                        ('active','telemetry_complete','can_confirm','submitted'))
    inn=state.get('inn') or {}
    if isinstance(inn,dict) and isinstance(inn.get('state'),str) and inn['state'] in {'offer','submitted','rejected','resting','closed'}:safe['inn']['state']=inn['state']
    for key in ('battle','story','dialogue'):
        safe[key]=_fields(state.get(key),('choice_count','selected_choice','page_index','page_count','entity_id','text_file','text_index'),
            ('active','telemetry_complete','transitioning','result_ready','can_advance','typing','awaiting_choice','submitted','script_complete','ready_to_close'))
    battle=state.get('battle') or {};battle=battle if isinstance(battle,dict) else {}
    safe['battle'].update(_fields(battle,('target_group','selected_item_id'),('command_ready','command_telemetry_complete')))
    if battle.get('menu') in {'main','items','item_target','switch','digivolve'}:safe['battle']['menu']=battle['menu']
    def rows(source,numbers,flags=(),limit=32):
        return [_fields(row,numbers,flags) for row in source[:limit]] if isinstance(source,list) else []
    if isinstance(battle.get('menu_token'),str) and len(battle['menu_token'])<=256:
        safe['battle']['menu_token_hash']=hashlib.sha256(battle['menu_token'].encode()).hexdigest()
    if isinstance(battle.get('actor'),dict):safe['battle']['actor']=_fields(battle['actor'],('group','active_index','form_id','hp','max_hp','ds','max_ds'))
    for key in ('fighters','party'):
        if key in battle:safe['battle'][key]=rows(battle[key],('group','slot','form_id','hp','max_hp','ds','max_ds'),('controlled',))
    if isinstance(battle.get('options'),list):
        safe['battle']['options']=[]
        for source in battle['options'][:32]:
            row=_fields(source,('index','skill_index','ds_cost','item_id','target_slot'),('enabled',))
            if isinstance(source,dict) and source.get('kind') in {'attack','skill','items','item','item_target','switch','switch_target','digivolve','digivolve_target','escape'}:row['kind']=source['kind']
            safe['battle']['options'].append(row)
    supplies=state.get('supplies') or {};supplies=supplies if isinstance(supplies,dict) else {}
    if supplies:
        clean=_fields(supplies,(),('telemetry_complete','rules_loaded','inventory_open','world_modal'))
        clean['inventory']=rows(supplies.get('inventory'),('id','item_id','quantity','heal_hp','heal_ds'),limit=64)
        clean['party']=rows(supplies.get('party'),('slot','id','hp','max_hp','ds','max_ds'))
        shop=supplies.get('shop') or {};shop=shop if isinstance(shop,dict) else {}
        clean['shop']=_fields(shop,('shop_id','quantity','selected_index'),('active','telemetry_complete','submitting','closed'))
        if shop.get('mode') in {'buy','sell'}:clean['shop']['mode']=shop['mode']
        clean['shop']['offers']=rows(shop.get('offers'),('index','id','item_id','unit_bits','heal_hp','heal_ds'),limit=64)
        safe['supplies']=clean
    return safe


class StallWatch:
    def __init__(self,session,clock=time.monotonic,stall_seconds=60,story_seconds=180):
        self.path=Path(session)/'repair-game-state.json';self.clock=clock
        self.stall_seconds=stall_seconds;self.story_seconds=story_seconds
        self._rows=deque(maxlen=96);self._context=None;self._cells=OrderedDict()
        self._last_progress=None;self._nav_failures=0;self._guard_failures=0
        self._guard_key=None;self._guard_since=None;self._story_key=None;self._story_since=None
        self._triggered=set()

    def history(self):return copy.deepcopy(list(self._rows))

    def _record(self,state,reason,action,now):
        row={'at':now,'reason':reason if reason in REASONS else 'other',
             'action':action if action in ACTIONS else None,'state':sanitize_state(state)}
        previous=self._rows[-1] if self._rows else None
        failure=reason in NAV_FAILURES or reason=='modal_changed'
        if (previous and not failure and now-previous['at']<1 and
                all(row[k]==previous[k] for k in ('reason','action','state'))):return
        self._rows.append(row);self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.repair-game-state-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as output:json.dump(list(self._rows),output,allow_nan=False);output.write('\n')
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def _reset(self,now):
        self._context=None;self._cells.clear();self._last_progress=now
        self._nav_failures=0;self._guard_failures=0;self._guard_since=None;self._guard_key=None
        self._story_since=None;self._story_key=None;self._triggered.clear()

    @staticmethod
    def _modal(state):
        story=state.get('story') or {};story=story if isinstance(story,dict) else {}
        if story.get('active'):
            if (story.get('telemetry_complete') is not True or story.get('typing') is not False
                    or type(story.get('choice_count')) is not int or story['choice_count']!=0
                    or story.get('awaiting_choice') is not False or story.get('submitted') is not False
                    or type(story.get('can_advance')) is not bool):return None
        battle=state.get('battle') or {};battle=battle if isinstance(battle,dict) else {}
        if battle.get('active'):
            if (battle.get('telemetry_complete') is not True or battle.get('transitioning') is not False
                    or battle.get('submitted') is not False):return None
            safe=sanitize_state(state)
            return 'battle',json.dumps({k:safe[k] for k in ('battle','story','dialogue')},sort_keys=True)
        for key in ('story','dialogue','inn'):
            modal=state.get(key) or {}
            if not isinstance(modal,dict) or not modal or (key!='dialogue' and not modal.get('active')):continue
            if modal.get('telemetry_complete') is False:return None
            if modal.get('typing') is True or modal.get('awaiting_choice') is True or modal.get('choice_count',0)!=0 or modal.get('submitted') is True:return None
            if key=='inn':
                if modal.get('telemetry_complete') is not True or modal.get('state')!='offer' or modal.get('can_confirm') is not True:return None
            elif key!='story' and (modal.get('can_advance') is not True or modal.get('typing') is not False):return None
            if key=='story' and modal.get('telemetry_complete') is not True:return None
            return key,json.dumps(sanitize_state({key:modal})[key],sort_keys=True)
        return None

    def observe(self,state,reason,action=None):
        """Return one trigger per stalled context, or None. Freshness is caller-owned."""
        now=self.clock();state=state if isinstance(state,dict) else {}
        action=action.get('action') if isinstance(action,dict) else action
        action=action if isinstance(action,str) else None
        reason=reason if isinstance(reason,str) else 'other'
        self._record(state,reason,action,now)
        quest=state.get('main_quest') or {};quest=quest if isinstance(quest,dict) else {}
        excluded=any(token in reason for token in ('focus_lost','stale','loading','session_changed','stop','choice','insufficient'))
        valid=(state.get('phase')=='world' and state.get('fresh') is not False and type(state.get('pid')) is int
               and _map(state.get('map')) and all(_number(state.get(k)) for k in ('x','y'))
               and all(type(quest.get(k)) is int and quest[k]>0 for k in ('chapter','step')))
        legacy_unfocused=state.get('window_focused') is False and state.get('native_background_input') is not True
        battle=state.get('battle') or {}
        battle_active=isinstance(battle,dict) and battle.get('active') is True
        if not valid or excluded or legacy_unfocused:
            self._reset(now);return None
        context=(state['pid'],state['map'],quest['chapter'],quest['step'],quest.get('target_map'))
        if context!=self._context:self._reset(now);self._context=context
        for cell,stamp in list(self._cells.items()):
            if now-stamp>180:del self._cells[cell]
        cell=(math.floor(state['x']/8),math.floor(state['y']/4))
        if cell not in self._cells:
            self._last_progress=now;self._nav_failures=0;self._triggered.clear()
        self._cells[cell]=now;self._cells.move_to_end(cell)
        while len(self._cells)>256:self._cells.popitem(last=False)
        if battle_active:
            self._nav_failures=0;self._last_progress=now
            self._triggered.discard('navigation_stalled')
        modal=self._modal(state)
        if modal!=self._guard_key:
            self._guard_key=modal;self._guard_since=now if modal else None;self._guard_failures=0
            self._triggered.discard('input_guard_stalled')
        if modal and reason=='modal_changed' and action is not None:self._guard_failures+=1
        story=modal if modal and modal[0]=='story' else None
        if story!=self._story_key:
            self._story_key=story;self._story_since=now if story else None
            self._triggered.discard('story_stalled')
        has_modal=battle_active or bool(state.get('dialogue')) or any(
            isinstance(state.get(k),dict) and state[k].get('active') is True for k in ('story','inn'))
        if not has_modal and state.get('movement_ready') is True and action in NAV_ACTIONS and reason in NAV_FAILURES:
            self._nav_failures+=1
        trigger=None
        if modal and self._guard_failures>=3 and now-self._guard_since>=self.stall_seconds:trigger='input_guard_stalled'
        elif story and now-self._story_since>=self.story_seconds:trigger='story_stalled'
        elif not has_modal and self._nav_failures>=3 and now-self._last_progress>=self.stall_seconds:trigger='navigation_stalled'
        if trigger and trigger not in self._triggered:self._triggered.add(trigger);return trigger
        return None
