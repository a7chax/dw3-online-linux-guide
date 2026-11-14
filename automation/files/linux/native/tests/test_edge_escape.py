"""Extra-margin recovery never crosses a blocked foot pixel."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from world_map import WorldMap,NoRouteError

class EdgeEscapeTests(unittest.TestCase):
    def world(self,barrier=False):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-edge-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);image=Image.new('L',(160,96),255);draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,20,95),fill=0)
        if barrier:draw.rectangle((27,0,27,95),fill=0)
        image.save(root/'mask.png')
        (root/'atlas.json').write_text(json.dumps({'maps':[{'id':'test','width':160,'height':96,'collision':'mask.png'}]}))
        return WorldMap('test',root)
    def test_valid_foot_clipped_margin_escapes_toward_goal(self):
        world=self.world();start=(21.5,40);goal=(120,40)
        self.assertTrue(world._pixel_walkable(21,40));self.assertFalse(world.walkable(*start))
        self.assertEqual(world.escape_step(start,goal,preferred_step=('left',50)),('right',50))
        self.assertEqual(world.steering_step(start,goal,[start,goal],('left',50)),('right',50))
    def test_path_prefix_restores_normal_clearance(self):
        world=self.world();start=(21.5,40);goal=(120,40)
        path=world.path(start,goal)
        self.assertEqual(path[0],list(start));self.assertEqual(path[-1],list(goal))
        self.assertTrue(world._clear_segment(path[0],path[1]));self.assertTrue(world.walkable(*path[1]))
        self.assertTrue(all(world.clear(a,b) for a,b in zip(path[1:],path[2:])))
    def test_blocked_foot_does_not_get_an_escape_exception(self):
        world=self.world();start=(20.5,40)
        self.assertIsNone(world.escape_step(start,(120,40)))
        self.assertIsNone(world.steering_step(start,(120,40),[start,(120,40)],('right',50)))
        with self.assertRaises(NoRouteError):world.path(start,(120,40))
    def test_thin_foot_barrier_cannot_be_crossed(self):
        world=self.world(barrier=True);start=(21.5,40)
        self.assertIsNone(world.escape_step(start,(120,40)))
        with self.assertRaises(NoRouteError):world.path(start,(120,40))
    def test_blocked_direction_set_is_respected(self):
        world=self.world();step=world.escape_step((21.5,40),(120,40),blocked={'right','up_right','down_right'})
        self.assertIsNone(step)
    @unittest.skipUnless((ROOT/'linux/world/maps/s205/collision.png').exists(),'Optional local s205 export')
    def test_recorded_s205_point_has_a_guarded_padded_landing(self):
        world=WorldMap('s205');start=(776.5,297.6646);goal=(800,280)
        self.assertTrue(world._pixel_walkable(*map(math.floor,start)));self.assertFalse(world.walkable(*start))
        step=world.escape_step(start,goal);self.assertIsNotNone(step)
        velocity={'up':(0,-120),'up_left':(-240/math.sqrt(2),-120/math.sqrt(2)),
                  'up_right':(240/math.sqrt(2),-120/math.sqrt(2))}[step[0]]
        end=tuple(start[i]+velocity[i]*step[1]/1000 for i in (0,1))
        guard=tuple(start[i]+velocity[i]*(step[1]+17)/1000 for i in (0,1))
        self.assertTrue(world._clear_segment(start,guard));self.assertTrue(world.walkable(*end));self.assertTrue(world.walkable(*guard))

if __name__=='__main__':unittest.main()
