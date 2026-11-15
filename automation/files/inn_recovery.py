"""Persistent, telemetry-driven inn recovery; this module sends no game input."""
import json
import math
from pathlib import Path
import time

from inn_routes import InnRoutes
from world_map import NoRouteError


def party_health(state):
    party=state.get('party') or {};members=party.get('members') or []
    if party.get('telemetry_complete') is not True or not members or party.get('count')!=len(members):return None
    if any(type(m.get('hp')) is not int or type(m.get('max_hp')) is not int
           or m['hp']<0 or m['max_hp']<=0 for m in members):return None
    return any(member['hp']==0 for member in members)


def alignment(state,npc):
    dx,dy=npc['x']-state['x'],npc['y']-state['y']
    if math.hypot(dx,dy)<.5:return None
    if abs(dy)<abs(dx)*.25:direction='right' if dx>0 else 'left'
    elif abs(dy)>abs(dx):direction='down' if dy>0 else 'up'
    else:direction=('down' if dy>0 else 'up')+'_'+('right' if dx>0 else 'left')
    facing={'down':0,'down_left':1,'left':2,'up_left':3,'up':4,'up_right':5,'right':6,'down_right':7}[direction]
    return None if state.get('facing')==facing else (direction,50)


class InnRecovery:
    def __init__(self,session,*,router_factory=InnRoutes,clock=time.time):
        self.path=Path(session)/'inn-recovery.json';self.router_factory=router_factory;self.router=None;self.clock=clock
        try:self.job=json.loads(self.path.read_text()).get('job')
        except (OSError,ValueError):self.job=None

    @property
    def pending(self):return self.job is not None

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps({'job':self.job},indent=2)+'\n')
        temporary.chmod(0o600);temporary.replace(self.path)

    def report(self):
        return {'pending':self.pending,'inn_id':(self.job or {}).get('inn_id'),
                'stay_sent':(self.job or {}).get('stay_sent',False),
                'deferred':(self.job or {}).get('deferred_until',0)>self.clock(),
                'deferred_reason':(self.job or {}).get('deferred_reason'),
                'retry_after_seconds':max(0,round((self.job or {}).get('deferred_until',0)-self.clock()))}

    @staticmethod
    def wait(reason):return {'action':None,'reason':reason}

    def defer(self,reason,state):
        # A failed inn trip must not block the main quest while living party
        # members remain. Keep the actual fainted state and bounded retry intent.
        if not any(member.get('hp',0)>0 for member in (state.get('party') or {}).get('members',[])):
            return self.wait('all_party_fainted')
        self.job.update(deferred_until=self.clock()+300,deferred_reason=reason)
        self.save();return None

    def decide(self,state):
        if state.get('native_inn_recovery') is not True:return None
        # Let the existing battle/story/dialogue controller finish its modal.
        if any((state.get(key) or {}).get('active') for key in ('battle','story')) or state.get('dialogue'):return None
        fainted=party_health(state)
        if fainted is None:return self.wait('party_telemetry_unavailable')
        inn=state.get('inn') or {}
        if not fainted:
            if self.pending:
                if inn.get('active') or state.get('movement_ready') is not True:return self.wait('inn_revival_verifying')
                self.job=None;self.save();return {'action':'inn_recovered','reason':'party_revived'}
            return None
        if not self.job or self.job.get('pid')!=state['pid']:
            self.job={'pid':state['pid'],'excluded':[],'excluded_npcs':[],'stay_sent':False,'failures':0,'align_attempts':0,'interact_attempts':0}
            self.save()
        if inn.get('active'):
            self.job['inn_id']=state['map'];self.save()
            if inn.get('telemetry_complete') is not True:return self.wait('inn_telemetry_unavailable')
            if inn.get('state')!='offer':return self.wait('inn_'+str(inn.get('state') or 'waiting'))
            if self.job.get('stay_sent'):return self.wait('inn_confirmation_pending')
            wallet=state.get('wallet') or {};price=inn.get('cost_bits');bits=wallet.get('bits')
            if (wallet.get('telemetry_complete') is not True or type(price) is not int
                    or price<0 or type(bits) is not int):return self.wait('inn_price_unavailable')
            if bits<price:return self.wait('inn_insufficient_bit')
            if inn.get('selected_option')!=0 or inn.get('can_confirm') is not True:return self.wait('inn_stay_not_selected')
            return {'action':'inn_stay','reason':'revive_at_inn','cost_bits':price,'map':state['map']}
        if self.job.get('stay_sent'):
            if self.clock()-self.job.get('stay_time',self.clock())<10:return self.wait('inn_revival_verifying')
            return self.wait('inn_revival_unconfirmed')
        until=self.job.get('deferred_until',0)
        if until:
            nearby_ready=any(n.get('map')==state['map'] and state['map'] not in self.job['excluded']
                and (n.get('logical_id')==20 or n.get('inn_candidate') is True)
                and f"{state['map']}:{n.get('entity_id')}" not in self.job.get('excluded_npcs',[])
                and (n.get('can_interact') is True or bool(n.get('interaction_facings')))
                for n in state.get('nearby_inns',[]))
            if self.clock()<until and not nearby_ready:
                if not any(m.get('hp',0)>0 for m in (state.get('party') or {}).get('members',[])):return self.wait('all_party_fainted')
                return None
            self.job.pop('deferred_until',None);self.job.pop('deferred_reason',None)
            self.job.update(failures=0,align_attempts=0,interact_attempts=0);self.save()
        if state.get('movement_ready') is not True:return self.wait('inn_waiting_for_world')
        nearby=state.get('nearby_inns') or []
        npc=min((n for n in nearby if n.get('map')==state['map']
                 and (n.get('logical_id')==20 or n.get('inn_candidate') is True)
                 and state['map'] not in self.job['excluded']
                 and f"{state['map']}:{n.get('entity_id')}" not in self.job.get('excluded_npcs',[])),
                key=lambda n:(n.get('can_interact') is not True,not bool(n.get('interaction_facings')),
                              math.dist((state['x'],state['y']),(n['x'],n['y']))),default=None)
        if npc:
            self.job['inn_id']=state['map'];self.save()
            game_facings=npc.get('interaction_facings')
            game_ready=npc.get('can_interact') is True
            in_range=game_ready or (bool(game_facings) if game_facings is not None else math.dist((state['x'],state['y']),(npc['x'],npc['y']))<24)
            if in_range:
                step=None if game_ready else alignment(state,npc)
                if game_facings and not game_ready:
                    facing=min(game_facings,key=lambda f:min((f-state['facing'])%8,(state['facing']-f)%8))
                    direction=('down','down_left','left','up_left','up','up_right','right','down_right')[facing]
                    step=(direction,50)
                if step and self.job.get('align_attempts',0)<2:
                    return {'action':'inn_align','reason':'face_innkeeper','step':step,'npc':npc,'map':state['map']}
                if self.job.get('interact_attempts',0)>=3:
                    self.job.setdefault('excluded_npcs',[]).append(f"{state['map']}:{npc.get('entity_id')}")
                    return self.defer('inn_interaction_unconfirmed',state)
                return {'action':'inn_interact','reason':'speak_to_innkeeper','npc':npc,'map':state['map']}
            return {'action':'inn_travel','reason':'approach_innkeeper','npc':npc,'map':state['map'],
                    'destination':(npc['x'],npc['y']),'cross_map':False}
        try:
            if self.router is None:self.router=self.router_factory()
            plan=self.router.plan(state['map'],state['x'],state['y'],excluded=self.job['excluded'])
        except (OSError,ValueError,NoRouteError):return self.defer('inn_route_unavailable',state)
        if plan['inn_id'] in self.job['excluded']:return self.defer('inn_route_unavailable',state)
        self.job['inn_id']=plan['inn_id'];self.save()
        leg=plan['legs'][0]
        if leg['kind']=='inn':return self.defer('innkeeper_telemetry_unavailable',state)
        return {'action':'inn_travel','reason':'travel_to_closest_inn','map':state['map'],
                'destination':(leg['x'],leg['y']),'cross_map':leg['kind']=='exit',
                'expected_next_maps':leg.get('expected_next_maps',[]),'inn_id':plan['inn_id']}

    def note_result(self,decision,result):
        if not self.job:return
        action=decision['action']
        if action=='inn_stay':
            self.job.update(stay_sent=True,stay_time=self.clock(),cost_bits=decision['cost_bits'])
        elif action=='inn_align':self.job['align_attempts']=self.job.get('align_attempts',0)+1
        elif action=='inn_interact':
            self.job['interact_attempts']=self.job.get('interact_attempts',0)+1
            after=result.get('current') or {};npc=decision.get('npc') or {}
            greeting=False
            if npc.get('inn_candidate') and after.get('dialogue'):
                try:
                    if self.router is None:self.router=self.router_factory()
                    greeting=getattr(self.router,'is_inn_dialogue',lambda *args:False)(decision['map'],after['dialogue'])
                except (OSError,ValueError):pass
            if npc.get('inn_candidate') and after.get('dialogue') and not greeting and not (after.get('inn') or {}).get('active'):
                self.job.setdefault('excluded_npcs',[]).append(f"{decision['map']}:{npc.get('entity_id')}")
                self.job.update(interact_attempts=0,align_attempts=0)
        elif action=='inn_travel':
            if result.get('reason') in ('unable_to_advance','no_map_exit_detected','local_route_unavailable'):
                self.job['failures']=self.job.get('failures',0)+1
                if self.job['failures']>=3:
                    self.job['excluded'].append(self.job['inn_id']);self.job['failures']=0
                    self.defer('innkeeper_unreachable',result.get('current') or {})
            elif result.get('reason')=='map_changed':self.job.update(failures=0,align_attempts=0,interact_attempts=0)
        self.save()
