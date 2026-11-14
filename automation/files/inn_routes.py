"""Estimated inn routes from the original world-map hints and local masks.

World-map links describe the map illustration, not unlocked server exits.
Only the current map's approach is collision-validated; replan after each
actual transfer. Interior inn NPC positions must come from fresh game state.
"""
import heapq
import itertools
import json
import math
from pathlib import Path

from world_map import ATLAS,NoRouteError,WorldMap


def _distance(a,b):
    return math.hypot(a[0]-b[0],2*(a[1]-b[1]))


class InnRoutes:
    def __init__(self,root=ATLAS):
        self.root=Path(root)
        self.worlds=json.loads((self.root/'auxiliary/worldmap/world.json').read_text())['worlds']
        self.maps={m['id']:m for m in json.loads((self.root/'atlas.json').read_text())['maps']}
        records=json.loads((self.root/'auxiliary/npcs.json').read_text())
        self.inns={n['stage'] for n in records if n.get('npc')==20 and n.get('character')=='p039tail'}
        self._inn_dialogues={(n['stage'],n.get('file'),index)
            for n in records if n.get('npc')==20 and n.get('character')=='p039tail'
            for index in n.get('texts',[])}
        self._masks={}

    def is_inn_dialogue(self,map_id,dialogue):
        """Match innkeeper greetings without confusing runtime entity IDs."""
        if not isinstance(dialogue,dict):return False
        file,index=dialogue.get('text_file'),dialogue.get('text_index')
        return type(file) is int and type(index) is int and (map_id,file,index) in self._inn_dialogues

    @staticmethod
    def _offset(spot,map_id):
        index=spot['ids'].index(map_id)
        offsets=spot.get('at',[])
        return offsets[index] if index<len(offsets) else (0,0)

    def _local(self,spot,map_id,point):
        dx,dy=self._offset(spot,map_id)
        return point[0]-spot['x']-dx,point[1]-spot['y']-dy

    def _contains(self,map_id,point):
        info=self.maps.get(map_id)
        return bool(info and 0<=point[0]<info['width'] and 0<=point[1]<info['height'])

    def _local_cost(self,map_id,start,end):
        if map_id not in self._masks:self._masks[map_id]=WorldMap(map_id,self.root)
        points=self._masks[map_id].path(start,end)
        return sum(_distance(a,b) for a,b in zip(points,points[1:]))

    def plan(self,map_id,x,y,excluded=()):
        """Return the least estimated reachable inn; raise NoRouteError if none.

        ``excluded`` contains inn map IDs that failed during this recovery.
        Returned exit points are approach hints: movement must still use the
        existing bounded collision-aware controller and verify the next map.
        """
        position=(float(x),float(y));excluded={excluded} if isinstance(excluded,str) else set(excluded)
        if not all(math.isfinite(v) for v in position):raise ValueError('Position must be finite.')
        on_world_map=any(map_id in s['ids'] for w in self.worlds for s in w['spots'])
        if map_id in self.inns and map_id not in excluded and not on_world_map:
            return self._result(map_id,0,[self._inn_leg(map_id)])
        results=[]
        for world in self.worlds:
            spots=world['spots']
            starts=[i for i,s in enumerate(spots) if map_id in s['ids']]
            for start in starts:
                route=self._plan_world(world,start,map_id,position,excluded)
                if route:results.append(route)
        if not results:raise NoRouteError('No inn reachable through the exported world-map hints and current collision mask.')
        return min(results,key=lambda r:(r['cost'],r['inn_id']))

    @staticmethod
    def _inn_leg(map_id):
        return {'map':map_id,'x':None,'y':None,'kind':'inn','expected_next_maps':[]}

    @staticmethod
    def _result(inn,cost,legs):
        return {'inn_id':inn,'map':inn,'cost':cost,'legs':legs,'estimated':True,
                'source':'bundled_worldmap_hints',
                'reachability':'Server locks and transitions require fresh runtime verification.'}

    def _plan_world(self,world,start,map_id,position,excluded):
        spots=world['spots'];edges={i:[] for i in range(len(spots))}
        for link in world.get('links',[]):
            a,ax,ay,b,bx,by=link
            edges[a].append((b,(ax,ay),(bx,by)))
            edges[b].append((a,(bx,by),(ax,ay)))
        for passage in world.get('passages',[]):
            edges[passage['spot']].append((passage['to'],(passage['x'],passage['y']),
                                         (passage['tx'],passage['ty'])))
        doors={i:[] for i in range(len(spots))}
        for door in world.get('doors',[]):
            if any(p[0]==2 for p in door.get('pois',[])):
                doors[door['spot']].append(door)
        counter=itertools.count();queue=[(0,next(counter),start,map_id,position,[])];best={};choices=[]
        first_costs={}
        def cost(current,origin,target,initial):
            if not initial:return _distance(origin,target)
            key=(current,origin,target)
            if key not in first_costs:
                try:first_costs[key]=self._local_cost(current,origin,target)
                except NoRouteError:first_costs[key]=math.inf
            return first_costs[key]
        while queue:
            total,_,index,current,origin,legs=heapq.heappop(queue)
            node=(index,current,origin)
            if total>=best.get(node,math.inf):continue
            best[node]=total;spot=spots[index];initial=not legs
            if choices and total>min(c['cost'] for c in choices):continue
            if current in self.inns and current not in excluded:
                for poi in spot.get('pois',[]):
                    if poi[0]!=2:continue
                    # Spot POIs use the common spot frame, like world links.
                    target=self._local(spot,current,(spot['x']+poi[1],spot['y']+poi[2]))
                    if not self._contains(current,target):continue
                    score=total+cost(current,origin,target,initial)
                    if math.isfinite(score):
                        leg={'map':current,'x':target[0],'y':target[1],'kind':'inn_approach','expected_next_maps':[]}
                        choices.append(self._result(current,score,legs+[leg]))
            for door in doors[index]:
                inns=sorted(self.inns.intersection(door['ids'])-excluded)
                if not inns:continue
                target=self._local(spot,current,(door['x'],door['y']))
                if not self._contains(current,target):continue
                score=total+cost(current,origin,target,initial)
                if not math.isfinite(score):continue
                for inn in inns:
                    leg={'map':current,'x':target[0],'y':target[1],'kind':'exit',
                         'expected_next_maps':inns,'innmap':inn}
                    choices.append(self._result(inn,score,legs+[leg,self._inn_leg(inn)]))
            for destination,source_point,arrival in edges[index]:
                target=self._local(spot,current,source_point)
                if not self._contains(current,target):continue
                score=total+cost(current,origin,target,initial)
                if not math.isfinite(score):continue
                # Each listed map is a variant/subregion; only use endpoints
                # whose transformed coordinates actually lie within that map.
                next_spot=spots[destination]
                candidates=[(m,self._local(next_spot,m,arrival)) for m in next_spot['ids']]
                candidates=[(m,p) for m,p in candidates if self._contains(m,p)]
                expected=[m for m,_ in candidates]
                for next_map,next_position in candidates:
                    leg={'map':current,'x':target[0],'y':target[1],'kind':'exit','expected_next_maps':expected}
                    heapq.heappush(queue,(score,next(counter),destination,next_map,next_position,legs+[leg]))
        return min(choices,key=lambda r:(r['cost'],r['inn_id'])) if choices else None
