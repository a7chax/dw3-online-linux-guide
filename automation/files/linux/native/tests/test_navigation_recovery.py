#!/usr/bin/env python3
"""Collision-aware movement selection without a game process or input device."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from world_map import WorldMap

VELOCITIES={'left':(-240,0),'right':(240,0),'up':(0,-120),'down':(0,120),
            'up_left':(-240/math.sqrt(2),-120/math.sqrt(2)),
            'up_right':(240/math.sqrt(2),-120/math.sqrt(2)),
            'down_left':(-240/math.sqrt(2),120/math.sqrt(2)),
            'down_right':(240/math.sqrt(2),120/math.sqrt(2))}

def endpoint(position,step,extra_ms=0):
    direction,milliseconds=step
    vx,vy=VELOCITIES[direction]
    return position[0]+vx*(milliseconds+extra_ms)/1000,position[1]+vy*(milliseconds+extra_ms)/1000

class RecoveryTests(unittest.TestCase):
    def make_map(self,image):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-steering-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        image.save(root/'collision.png')
        (root/'atlas.json').write_text(json.dumps({'maps':[{'id':'fixture','width':image.width,
            'height':image.height,'collision':'collision.png'}]}))
        return WorldMap('fixture',root)

    def assert_safe(self,world,position,step):
        self.assertIsNotNone(step)
        self.assertGreaterEqual(step[1],50)
        self.assertLessEqual(step[1],175)
        self.assertTrue(world.clear(position,endpoint(position,step,17)),step)

    def test_clear_preferred_burst_is_preserved(self):
        world=self.make_map(Image.new('L',(256,96),255))
        self.assertEqual(world.steering_step((20,40),(200,40),[[20,40],[200,40]],('right',100)),('right',100))

    def test_corner_trap_uses_safe_backoff_and_then_reaches_goal(self):
        image=Image.new('L',(160,96),255)
        draw=ImageDraw.Draw(image)
        draw.rectangle((72,30,110,60),fill=0)
        draw.rectangle((69,32,110,60),fill=0)
        world=self.make_map(image)
        position=(68.9,29.9);goal=(140,70)
        path=world.path(position,goal)
        self.assertFalse(world.clear(position,endpoint(position,('down_right',50))))
        first=world.steering_step(position,goal,path,('down_right',100),blocked='down_right')
        self.assert_safe(world,position,first)
        self.assertNotIn(first[0],('right','down','down_right'))
        for _ in range(40):
            if math.dist(position,goal)<8:break
            step=world.steering_step(position,goal,path,('down_right',100))
            self.assert_safe(world,position,step)
            position=endpoint(position,step,17)
        self.assertLess(math.dist(position,goal),8,position)

    def test_frame_guard_rejects_nominally_clear_overshoot(self):
        image=Image.new('L',(96,64),255)
        ImageDraw.Draw(image).rectangle((48,0,95,63),fill=0)
        world=self.make_map(image);position=(30,30)
        self.assertTrue(world.clear(position,endpoint(position,('right',50))))
        self.assertFalse(world.clear(position,endpoint(position,('right',50),17)))
        step=world.steering_step(position,(44,30),[[30,30],[44,30]],('right',50))
        self.assert_safe(world,position,step)
        self.assertNotEqual(step,('right',50))

    def test_blocked_direction_and_cardinal_only_capability_are_respected(self):
        world=self.make_map(Image.new('L',(160,96),255));position=(40,40)
        step=world.steering_step(position,(120,40),[[40,40],[120,40]],('right',100),blocked='right',allow_diagonal=False)
        self.assert_safe(world,position,step)
        self.assertNotEqual(step[0],'right')
        self.assertNotIn('_',step[0])

    def test_no_legal_minimum_burst_returns_none(self):
        image=Image.new('L',(64,64),0)
        ImageDraw.Draw(image).rectangle((28,30,36,34),fill=255)
        world=self.make_map(image)
        self.assertTrue(world.walkable(32,32))
        self.assertIsNone(world.steering_step((32,32),(33,32),[[32,32],[33,32]],('right',50)))

    @unittest.skipUnless((ROOT/'linux/world/maps/s465/collision.png').exists(),'Exported s465 collision mask is optional')
    def test_s465_recorded_corner_trap_progresses_with_frame_guard(self):
        world=WorldMap('s465');position=(673.96686,430.9959);goal=(1046,410)
        path=world.path(position,goal)
        first=world.steering_step(position,goal,path,('down_right',50),blocked='down_right')
        self.assert_safe(world,position,first)
        self.assertIn(first[0],('left','up','up_left'))
        for _ in range(40):
            if math.dist(position,goal)<8:break
            step=world.steering_step(position,goal,path,('down_right',100))
            self.assert_safe(world,position,step)
            position=endpoint(position,step,17)
        self.assertLess(math.dist(position,goal),8,position)

if __name__=='__main__':unittest.main(verbosity=2)
