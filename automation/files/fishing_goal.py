"""Persistent battle-loss counter and deterministic fishing destination policy."""
import json
import math

from inn_routes import InnRoutes
from world_map import NoRouteError,WorldMap
from lake_shore import ShoreApproach
from pathlib import Path


class LakeRoutes(InnRoutes):
    """Reuse collision-validated world links with the bundled fishing POI."""
    def __init__(self):
        super().__init__(poi_type=5)
        self.inns={'s380','s381','s950'};self.shores={}

    def _local_cost(self,map_id,start,end):
        if map_id not in self._masks:self._masks[map_id]=WorldMap(map_id,self.root)
        try:points=self._masks[map_id].path(start,end,max_nodes=12000)
        except RuntimeError as error:
            if str(error)=='Local route search exceeded its node limit.':raise NoRouteError('Fishing route exceeds bounded local search.') from None
            raise
        return sum(math.hypot(a[0]-b[0],2*(a[1]-b[1])) for a,b in zip(points,points[1:]))

    def plan(self,map_id,x,y,excluded=(),*,probed=()):
        if map_id not in self.inns:return super().plan(map_id,x,y,excluded)
        if map_id not in self.shores:self.shores[map_id]=ShoreApproach(map_id,self.root)
        for point in self.shores[map_id].candidates((x,y)):
            key=f'{map_id}:{point[0]}:{point[1]}'
            if key in probed:continue
            try:cost=self._local_cost(map_id,(x,y),point)
            except NoRouteError:continue
            return self._result(map_id,cost,[{'kind':'shore','x':point[0],'y':point[1],
                'shore_key':key,'expected_next_maps':[]}])
        raise NoRouteError('No untested reachable shore candidate remains.')

    def leave_lake(self,map_id,x,y):
        choices=[]
        for world in self.worlds:
            spots=world['spots']
            for index,spot in enumerate(spots):
                if map_id not in spot['ids']:continue
                for a,ax,ay,b,bx,by in world.get('links',[]):
                    if index==b:a,ax,ay,b,bx,by=b,bx,by,a,ax,ay
                    if index!=a or any(m in self.inns for m in spots[b]['ids']):continue
                    target=self._local(spot,map_id,(ax,ay))
                    if not self._contains(map_id,target):continue
                    try:cost=self._local_cost(map_id,(x,y),target)
                    except NoRouteError:continue
                    choices.append((cost,{'kind':'exit','x':target[0],'y':target[1],'expected_next_maps':spots[b]['ids']}))
        if not choices:raise NoRouteError('No collision-clear lake exit.')
        return min(choices,key=lambda row:row[0])[1]


class FishingGoal:
    def __init__(self,session,*,router_factory=None):
        self.path=Path(session)/'fishing-goal.json'
        self.router_factory=router_factory;self.router=None
        self.saved={'version':1,'losses':0,'loss_limit':1,'mode':'main_quest','seen_defeats':[]}
        try:
            saved=json.loads(self.path.read_text())
            if (saved.get('version')==1 and type(saved.get('losses')) is int and saved['losses']>=0
                    and saved.get('mode') in ('main_quest','diverlake_fishing')
                    and isinstance(saved.get('seen_defeats'),list)):
                self.saved.update(saved)
        except (OSError,ValueError,TypeError):pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.saved,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(self.path)

    def report(self):
        return {key:self.saved[key] for key in ('mode','losses','loss_limit')}

    @property
    def fishing(self):return self.saved['mode']=='diverlake_fishing'

    def observe(self,state):
        battle=state.get('battle') or {};identity=battle.get('battle_id')
        if (state.get('phase')!='world' or type(state.get('pid')) is not int
                or battle.get('active') is not True or battle.get('telemetry_complete') is not True
                or battle.get('transitioning') or battle.get('result')!='defeat'
                or not (battle.get('result_ready') is True or battle.get('can_advance') is True)
                or not isinstance(identity,str) or not identity or len(identity)>256):return
        identity=str(state['pid'])+':'+identity
        if identity in self.saved['seen_defeats']:return
        self.saved['seen_defeats']=(self.saved['seen_defeats']+[identity])[-256:]
        self.saved['losses']+=1
        if self.saved['losses']>=self.saved['loss_limit']:self.saved['mode']='diverlake_fishing'
        self.save()

    def decide(self,state):
        if not self.fishing:return None
        if any((state.get(key) or {}).get('active') for key in ('battle','story','inn')) or state.get('dialogue'):return None
        lake=state.get('map') in ('s380','s381','s950')
        fishing=state.get('fishing') or {}
        if lake:
            if state.get('native_fishing_control') is not True or fishing.get('telemetry_complete') is not True:
                return {'action':None,'reason':'fishing_telemetry_unavailable'}
            if fishing.get('exhausted'):
                if not self.saved.get('refresh_lake'):
                    self.saved['refresh_lake']=state['map'];self.save()
                if fishing.get('can_reel') and fishing.get('fishing_type')==8:
                    return {'action':'fishing_exhausted','reason':'fishing_pool_exhausted','expected_token':fishing['state_token']}
            if fishing.get('can_cast') is True and not self.saved.get('refresh_lake'):
                return {'action':'fishing_cast','reason':'cast_at_diverlake','expected_token':fishing['state_token']}
            if fishing.get('active') is True and fishing.get('fishing_type') is not None:
                if fishing.get('can_reel') is True and fishing.get('reel_good') is True and not self.saved.get('refresh_lake'):
                    return {'action':'fishing_reel','reason':'reel_in_good_window','expected_token':fishing['state_token']}
                return {'action':None,'reason':'fishing_wait_timing' if fishing.get('can_reel') else 'fishing_wait_result'}
            if not self.saved.get('refresh_lake') and fishing.get('at_spot') is True:
                facing,wanted=fishing.get('facing'),fishing.get('cast_facing')
                if type(facing) is int and type(wanted) is int and 0<=wanted<8 and (facing-wanted)%8 not in (0,1,7):
                    if state.get('movement_ready') is not True:return {'action':None,'reason':'fishing_waiting_for_world'}
                    direction=('down','down_left','left','up_left','up','up_right','right','down_right')[wanted]
                    return {'action':'fishing_align','reason':'face_fishing_spot','step':(direction,50)}
                return {'action':None,'reason':'fishing_wait_cast_ready'}
            if not self.saved.get('refresh_lake') and math.dist((state['x'],state['y']),(590,519))<10:
                return {'action':None,'reason':'fishing_spot_unconfirmed'}
        elif self.saved.pop('refresh_lake',None):self.save()
        if state.get('movement_ready') is not True:return {'action':None,'reason':'fishing_waiting_for_world'}
        try:
            if self.router is None:self.router=(self.router_factory or LakeRoutes)()
            if self.saved.get('refresh_lake'):
                leg=self.router.leave_lake(state['map'],state['x'],state['y'])
            else:
                options={'probed':self.saved.get('shore_probes',[])} if lake else {}
                route=self.router.plan(state['map'],state['x'],state['y'],**options)
                leg=route['legs'][0]
        except (OSError,ValueError,NoRouteError):return {'action':None,'reason':'fishing_route_unavailable'}
        return {'action':'fishing_travel','reason':'refresh_exhausted_lake' if self.saved.get('refresh_lake') else 'travel_to_diverlake','map':state['map'],
                'destination':(leg['x'],leg['y']),'cross_map':leg['kind']=='exit',
                'expected_next_maps':leg.get('expected_next_maps',[]),'shore_key':leg.get('shore_key')}

    def note_result(self,decision,result):
        key=decision.get('shore_key')
        if key and result.get('reason')=='destination_reached':
            self.saved['shore_probes']=list(dict.fromkeys([*self.saved.get('shore_probes',[]),key]))[-96:]
            self.save()
