#!/usr/bin/env python3
"""Bound expensive collision queries instead of relying on machine timings."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from world_map import WorldMap

class SteeringPerformanceTests(unittest.TestCase):
    def make_map(self,image):
        temporary=tempfile.TemporaryDirectory(prefix='dw3-steering-cost-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);image.save(root/'mask.png')
        (root/'atlas.json').write_text(json.dumps({'maps':[{'id':'test','width':image.width,
            'height':image.height,'collision':'mask.png'}]}))
        world=WorldMap('test',root);self.clear_calls=0;clear=world.clear
        def counted(start,end):self.clear_calls+=1;return clear(start,end)
        world.clear=counted
        return world

    def test_progressing_preferred_burst_uses_few_checks_on_long_routes(self):
        for size in (30,2000):
            with self.subTest(points=size):
                world=self.make_map(Image.new('L',(size*7+80,96),255))
                route=[[30+index*7,40] for index in range(size)]
                step=world.steering_step((30,40),route[-1],route,('right',100))
                self.assertEqual(step,('right',100));self.assertLessEqual(self.clear_calls,8)

    def test_clear_but_backward_preference_does_not_use_fast_path(self):
        world=self.make_map(Image.new('L',(256,96),255))
        step=world.steering_step((40,40),(200,40),[[40,40],[200,40]],('left',50))
        self.assertEqual(step[0],'right')

    def test_blocked_preference_has_bounded_join_search_on_long_routes(self):
        for size in (30,1000):
            with self.subTest(points=size):
                image=Image.new('L',(160,160),255)
                ImageDraw.Draw(image).rectangle((48,0,52,100),fill=0)
                world=self.make_map(image)
                route=[[40,40],[40,110],[60,110],*[[60,40] for _ in range(size)]]
                step=world.steering_step((40,40),(60,40),route,('right',100))
                self.assertIsNotNone(step);self.assertNotEqual(step[0],'right')
                self.assertLessEqual(self.clear_calls,2000)

    def test_blocked_direction_set_excludes_every_failed_direction(self):
        world=self.make_map(Image.new('L',(256,96),255))
        excluded={'right','up_right','down_right'}
        step=world.steering_step((40,40),(200,40),[[40,40],[200,40]],('right',100),blocked=excluded)
        self.assertIsNotNone(step);self.assertNotIn(step[0],excluded)

if __name__=='__main__':unittest.main(verbosity=2)
