#!/usr/bin/env python3
"""Inspect local map coordinates and plan paths through exported collision masks."""
import argparse
import heapq
import json
import math
from pathlib import Path
import time
from PIL import Image

ROOT=Path(__file__).resolve().parent
ATLAS=ROOT/'linux/world'

class WorldMap:
    def __init__(self,map_id,root=ATLAS):
        self.root=Path(root)
        index=json.loads((self.root/'atlas.json').read_text())
        self.info=next((entry for entry in index['maps'] if entry['id']==map_id),None)
        if self.info is None:raise RuntimeError('Map is not in the local atlas: '+map_id)
        self.width,self.height=self.info['width'],self.info['height']
        self.pixels=None
        if self.info.get('collision'):
            with Image.open(self.root/self.info['collision']) as image:
                self.mask_width,self.mask_height=image.size
                if image.mode in ('RGB','RGBA'):image=image.getchannel(0)
                if image.mode in ('L','P'):self.pixels=image.tobytes()
                else:self.pixels=bytes(value&255 for value in image.getdata())
        else:self.mask_width,self.mask_height=self.width,self.height

    def _pixel_walkable(self,x,y):
        return (0<=x<min(self.width,self.mask_width) and
                0<=y<min(self.height,self.mask_height) and
                (self.pixels is None or bool(self.pixels[y*self.mask_width+x])))

    def walkable(self,x,y):
        # Original aa.a checks nonzero raster band zero. Add the original
        # player's horizontal body clearance, plus one unit vertically.
        return all(self._pixel_walkable(math.floor(x+dx),math.floor(y+dy))
                   for dx,dy in ((0,0),(-3,0),(3,0),(0,-1),(0,1)))

    def _clear_segment(self,start,end):
        # Visit each raster cell crossed by the segment. Sampling at unit
        # intervals misses short visits near pixel corners.
        x,y=map(math.floor,start);last_x,last_y=map(math.floor,end)
        dx,dy=end[0]-start[0],end[1]-start[1]
        sx=1 if dx>0 else -1
        sy=1 if dy>0 else -1
        while True:
            if not self._pixel_walkable(x,y):return False
            if (x,y)==(last_x,last_y):return True
            # Once an axis reaches its endpoint cell, do not cross its far
            # boundary at t=1 when the endpoint lies exactly on a grid line.
            tx=((x+(dx>0))-start[0])/dx if x!=last_x else math.inf
            ty=((y+(dy>0))-start[1])/dy if y!=last_y else math.inf
            if math.isclose(tx,ty,rel_tol=0,abs_tol=1e-12):
                # At a corner, both side cells must also be clear.
                if not (self._pixel_walkable(x+sx,y) and self._pixel_walkable(x,y+sy)):return False
                x+=sx;y+=sy
            elif tx<ty:x+=sx
            else:y+=sy

    def clear(self,start,end):
        return all(self._clear_segment((start[0]+dx,start[1]+dy),(end[0]+dx,end[1]+dy))
                   for dx,dy in ((0,0),(-3,0),(3,0),(0,-1),(0,1)))

    def steering_step(self,position,goal,path,preferred_step=None,blocked=None,allow_diagonal=True):
        """Choose a collision-clear burst, including a frame of release margin.

        Reconnect to visible points on the ordered route instead of discarding
        nearby corners. A short retreat can expose a later safe segment. This
        helper sends no input and declares no arrival: callers own live feedback,
        stopping, and replanning when a dynamic obstacle blocks a legal burst.
        """
        position=tuple(map(float,position));goal=tuple(map(float,goal))
        route=[tuple(map(float,point)) for point in path] if path else [goal]
        if route[-1]!=goal:route.append(goal)
        if not all(math.isfinite(value) for point in [position,goal,*route] for value in point):
            raise ValueError('Steering coordinates must be finite.')
        def travel(a,b):return math.hypot((a[0]-b[0])/240,(a[1]-b[1])/120)
        suffix=[0.0]*len(route)
        for index in range(len(route)-2,-1,-1):
            suffix[index]=suffix[index+1]+travel(route[index],route[index+1])
        def projection(node,index):
            a,b=route[index:index+2]
            dx,dy=(b[0]-a[0])/240,(b[1]-a[1])/120
            length=dx*dx+dy*dy
            t=0 if not length else max(0,min(1,(((node[0]-a[0])/240)*dx+((node[1]-a[1])/120)*dy)/length))
            return a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])
        # Finding the current segment is arithmetic only. Collision queries stay
        # within twelve nearby points, including the preceding corner segments.
        anchor=min(range(len(route)-1),key=lambda index:travel(position,projection(position,index))) if len(route)>1 else 0
        first,last=max(0,anchor-2),min(len(route),anchor+10)
        def remaining(node):
            joins=[(travel(node,route[index])+suffix[index],route[index]) for index in range(first,last)]
            for index in range(first,last-1):
                b=route[index+1];point=projection(node,index)
                joins.append((travel(node,point)+travel(point,b)+suffix[index+1],point))
            for cost,point in sorted(joins):
                if self.clear(node,point):return cost
            return math.inf
        diagonal=math.sqrt(.5)
        velocities={'left':(-240,0),'right':(240,0),'up':(0,-120),'down':(0,120)}
        if allow_diagonal:
            velocities.update({'up_left':(-240*diagonal,-120*diagonal),
                'up_right':(240*diagonal,-120*diagonal),
                'down_left':(-240*diagonal,120*diagonal),
                'down_right':(240*diagonal,120*diagonal)})
        preferred_ms=preferred_step[1] if preferred_step else 100
        blocked_directions={blocked} if isinstance(blocked,str) else set(blocked or ())
        if preferred_step and preferred_step[0] in velocities and preferred_step[0] not in blocked_directions:
            milliseconds=round(preferred_ms);vx,vy=velocities[preferred_step[0]]
            guard=(position[0]+vx*(milliseconds+17)/1000,position[1]+vy*(milliseconds+17)/1000)
            if 50<=milliseconds<=175 and self.clear(position,guard):
                end=(position[0]+vx*milliseconds/1000,position[1]+vy*milliseconds/1000)
                before,after=remaining(position),remaining(end)
                # A clear preference must make substantial progress along a
                # visible route connection; a safe but backward key is rejected.
                if math.isfinite(before) and math.isfinite(after) and before-after>=milliseconds/1000*.8:
                    return preferred_step[0],milliseconds
        best=None
        for direction,(vx,vy) in velocities.items():
            if direction in blocked_directions:continue
            durations={50,75,100,125,150,175}
            if preferred_step:durations.add(round(preferred_ms))
            # Include bursts that stop one frame before a nearby route point.
            for point in [goal,*route[:4]]:
                seconds=(((point[0]-position[0])/240)*(vx/240)
                         +((point[1]-position[1])/120)*(vy/120))/((vx/240)**2+(vy/120)**2)
                durations.update((round(seconds*1000),round(seconds*1000)-17))
            for milliseconds in sorted(durations):
                if not 50<=milliseconds<=175:continue
                guard=(position[0]+vx*(milliseconds+17)/1000,position[1]+vy*(milliseconds+17)/1000)
                if not self.clear(position,guard):continue
                end=(position[0]+vx*milliseconds/1000,position[1]+vy*milliseconds/1000)
                cost=milliseconds/1000+remaining(end)
                if not math.isfinite(cost):continue
                step=(direction,milliseconds)
                rank=(round(cost,6),step!=preferred_step,abs(milliseconds-preferred_ms))
                if best is None or rank<best[0]:best=(rank,step)
        return None if best is None else best[1]

    def path(self,start,goal,step=4,max_nodes=350000):
        start=tuple(map(float,start));goal=tuple(map(float,goal))
        if not self.walkable(*goal):raise RuntimeError('Destination is blocked in the local collision map.')
        if self.clear(start,goal):return [list(start),list(goal)]
        for resolution in ([step,1] if step>1 else [step]):
            points=self._grid_path(start,goal,resolution,max_nodes)
            if points is not None:return points
        raise RuntimeError('No route through the static collision map.')

    def _grid_path(self,start,goal,step,max_nodes):
        def nearest(point):
            base=(round(point[0]/step)*step,round(point[1]/step)*step)
            choices=[]
            for dx in range(-2,3):
                for dy in range(-2,3):
                    node=(base[0]+dx*step,base[1]+dy*step)
                    if self.clear(point,node):choices.append(node)
            if not choices:return None
            return min(choices,key=lambda p:math.dist(p,point))
        first,last=nearest(start),nearest(goal)
        if first is None or last is None:return None
        def cost(a,b):return math.hypot(a[0]-b[0],2*(a[1]-b[1]))
        queue=[(cost(first,last),0,first)];distance={first:0};parents={};visited=set()
        moves=[(dx*step,dy*step) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy]
        while queue:
            _,travel,node=heapq.heappop(queue)
            if node in visited:continue
            if node==last:
                points=[node]
                while node in parents:node=parents[node];points.append(node)
                points.reverse();points=[start,*points,goal]
                # Shorten only where the full segment is collision-clear.
                reduced=[list(points[0])];anchor=0
                while anchor<len(points)-1:
                    far=min(len(points)-1,anchor+24)
                    while far>anchor+1 and not self.clear(points[anchor],points[far]):far-=1
                    reduced.append(list(points[far]));anchor=far
                return reduced
            visited.add(node)
            if len(visited)>max_nodes:raise RuntimeError('Local route search exceeded its node limit.')
            for dx,dy in moves:
                other=(node[0]+dx,node[1]+dy)
                if other in visited or not self.clear(node,other):continue
                proposed=travel+cost(node,other)
                if proposed<distance.get(other,float('inf')):
                    distance[other]=proposed;parents[other]=node
                    heapq.heappush(queue,(proposed+cost(other,last),proposed,other))
        return None


def remaining_path(points,position):
    if len(points)<2:return points
    best=None
    for index,(a,b) in enumerate(zip(points,points[1:])):
        dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
        t=0 if not length else max(0,min(1,((position[0]-a[0])*dx+(position[1]-a[1])*dy)/length))
        projected=[a[0]+dx*t,a[1]+dy*t]
        candidate=(math.dist(projected,position),index)
        if best is None or candidate<best:best=candidate
    # Match the GPS observer's dense dots without requesting a server route.
    tail=points[best[1]+1:];dots=[];previous=position
    for point in tail:
        distance=math.dist(previous,point);count=max(1,math.ceil(distance/7))
        for i in range(1,count+1):
            dots.append([previous[0]+(point[0]-previous[0])*i/count,
                         previous[1]+(point[1]-previous[1])*i/count])
        previous=point
    return dots


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list')
    info=commands.add_parser('info');info.add_argument('map')
    route=commands.add_parser('path');route.add_argument('map');route.add_argument('--start',nargs=2,type=float,required=True);route.add_argument('--goal',nargs=2,type=float,required=True)
    args=parser.parse_args()
    if args.command=='list':
        index=json.loads((ATLAS/'atlas.json').read_text())
        for entry in index['maps']:print(f"{entry['id']}  {entry['width']}x{entry['height']}  {entry['name']}")
    elif args.command=='info':print(json.dumps(WorldMap(args.map).info,indent=2))
    else:
        start=time.perf_counter();points=WorldMap(args.map).path(args.start,args.goal)
        result={'source':'local_collision_atlas','map':args.map,'start':args.start,'goal':args.goal,'points':points,'planned_ms':round((time.perf_counter()-start)*1000,2)}
        output=ATLAS/'last-path.json';output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'path_file':str(output),'points':len(points),'planned_ms':result['planned_ms']}))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
