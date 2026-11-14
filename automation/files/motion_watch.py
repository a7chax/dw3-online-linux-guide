"""Measure movement and remember nearby failures without sending game input."""
from collections import deque
import math


class MotionWatch:
    def __init__(self,now):
        self.last_progress=now
        self.samples=deque(maxlen=16)
        self.failures=deque(maxlen=48)

    @staticmethod
    def distance(a,b):
        return math.hypot(a[0]-b[0],2*(a[1]-b[1]))

    def blocked(self,position,now):
        self.failures=deque((entry for entry in self.failures if entry[2]>now),maxlen=48)
        return {direction for direction,origin,expires in self.failures
                if self.distance(position,origin)<=24}

    def observe(self,before,after,direction,milliseconds,now):
        before,after=tuple(before),tuple(after)
        axes={'left':(-1,0),'right':(1,0),'up':(0,-1),'down':(0,1),
              'up_left':(-1,-1),'up_right':(1,-1),
              'down_left':(-1,1),'down_right':(1,1)}
        vx,vy=axes[direction];length=math.hypot(vx,vy)
        advance=((after[0]-before[0])*vx+2*(after[1]-before[1])*vy)/length
        if not self.samples:self.samples.append((now,before))
        while self.samples and now-self.samples[0][0]>3:self.samples.popleft()
        # Returning to a recent position after several commands is a loop,
        # even when each small forward/backward step changed the coordinates.
        looping=any(self.distance(after,position)<2 for _,position in list(self.samples)[:-2])
        useful=advance>=max(2,240*milliseconds/1000*.25) and not looping
        if useful:self.last_progress=now
        else:self.failures.append((direction,before,now+6))
        self.samples.append((now,after))
        return useful
