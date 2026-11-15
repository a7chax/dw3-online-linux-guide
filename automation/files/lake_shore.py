"""Bounded collision-connected shoreline hints; no fishing permission is inferred."""
from collections import deque
import math

from world_map import ATLAS,NoRouteError,WorldMap


class ShoreApproach:
    def __init__(self,map_id,root=ATLAS,*,hint=(590,519)):
        self.atlas=WorldMap(map_id,root)
        self.width=min(self.atlas.width,self.atlas.mask_width)
        self.height=min(self.atlas.height,self.atlas.mask_height)
        if self.width*self.height>2_000_000:
            raise NoRouteError('Lake component exceeds the bounded shoreline search size.')
        self.hint=tuple(math.floor(value)+.5 for value in hint)
        self._components=[];self.component_searches=0

    def _walkable(self,x,y):
        if not 3<=x<self.width-3 or not 1<=y<self.height-1:return False
        pixels=self.atlas.pixels
        if pixels is None:return True
        stride=self.atlas.mask_width;i=y*stride+x
        return bool(pixels[i] and pixels[i-3] and pixels[i+3] and pixels[i-stride] and pixels[i+stride])

    def candidates(self,position):
        """Return at most 24 separated boundary points in this physical component.

        Positions use pixel centres to avoid boundary-rounding ambiguities.
        A one-pixel four-neighbour search respects the original five-sample body
        clearance. Results are cached per connected region, not per position.
        They are places to inspect fresh server fishing telemetry, not proof of
        a shore trigger, tool ownership, catch, or unlocked server access.
        """
        if len(position)!=2 or not all(math.isfinite(value) for value in position):
            raise ValueError('Shore position must contain two finite coordinates.')
        x,y=map(math.floor,position);start=y*self.width+x
        if not self._walkable(x,y):raise NoRouteError('Shore approach starts outside the clear collision component.')
        for cells,points in self._components:
            if start in cells:return list(points)
        self.component_searches+=1
        cells={start};queue=deque([start]);boundary=[]
        while queue:
            cell=queue.popleft();x=cell%self.width;y=cell//self.width;edge=False
            for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if not self._walkable(nx,ny):edge=True;continue
                neighbor=ny*self.width+nx
                if neighbor not in cells:cells.add(neighbor);queue.append(neighbor)
            if edge:boundary.append((x+.5,y+.5))
        hx,hy=self.hint
        boundary.sort(key=lambda p:((p[0]-hx)**2+4*(p[1]-hy)**2,p))
        points=[];hint_cell=math.floor(hy)*self.width+math.floor(hx)
        if 0<=hx<self.width and 0<=hy<self.height and hint_cell in cells:points.append(self.hint)
        for point in boundary:
            if all(math.dist(point,previous)>=24 for previous in points):points.append(point)
            if len(points)>=24:break
        self._components.append((cells,points));return list(points)
