#!/usr/bin/env python3
"""Offline NPC approach planning preserves the collision planner's strict goals."""
from pathlib import Path
import json, math, sys, tempfile, unittest
from PIL import Image
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from world_map import WorldMap, NoRouteError

class InteractionApproachTests(unittest.TestCase):
    def world(self, image):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);image.save(root/'mask.png')
        (root/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',width=image.width,height=image.height,collision='mask.png')]}))
        return WorldMap('test',root)

    def test_blocked_npc_center_gets_clear_in_range_approach(self):
        image=Image.new('L',(96,96),255)
        for x in range(46,57):
            for y in range(42,55):image.putpixel((x,y),0)
        m=self.world(image);start=(18,48);goal=(51,48)
        with self.assertRaises(NoRouteError):m.path(start,goal)
        destination=m.interaction_destination(start,goal)
        self.assertIsInstance(destination,tuple)
        self.assertLess(math.dist(destination,goal),24)
        self.assertTrue(m.walkable(*destination))
        route=m.path(start,destination)
        for a,b in zip(route,route[1:]):self.assertTrue(m.clear(a,b))
        with self.assertRaises(NoRouteError):m.path(start,goal)

    def test_routes_around_barrier_instead_of_returning_inaccessible_cell(self):
        image=Image.new('L',(96,96),255)
        for x in range(40,45):
            for y in range(6,70):image.putpixel((x,y),0)
        m=self.world(image);start=(20,30);goal=(68,30)
        destination=m.interaction_destination(start,goal)
        self.assertFalse(m.clear(start,destination))
        self.assertLess(math.dist(destination,goal),24)
        route=m.path(start,destination)
        self.assertTrue(min(point[1] for point in route)<6 or max(point[1] for point in route)>69)
        for a,b in zip(route,route[1:]):self.assertTrue(m.clear(a,b))

    def test_sealed_goal_and_invalid_coordinates_fail_safely(self):
        image=Image.new('L',(96,96),255)
        for x in range(35,96):
            for y in range(96):image.putpixel((x,y),0)
        m=self.world(image)
        with self.assertRaises(NoRouteError):m.interaction_destination((15,45),(65,45))
        with self.assertRaises(ValueError):m.interaction_destination((15,45),(math.nan,45))

    def test_unreachable_walkable_candidates_raise_no_route(self):
        image=Image.new('L',(80,80),255)
        for y in range(80):
            for x in range(26,34):image.putpixel((x,y),0)
        m=self.world(image)
        with self.assertRaises(NoRouteError):m.interaction_destination((12,40),(60,40))

    def test_detour_attempts_have_a_fixed_budget(self):
        m=self.world(Image.new('L',(96,96),255))
        with patch.object(m,'clear',return_value=False), patch.object(m,'path',side_effect=NoRouteError('sealed')) as paths:
            with self.assertRaises(NoRouteError):m.interaction_destination((12,12),(60,60))
        self.assertEqual(paths.call_count,8)
        for call in paths.call_args_list:
            self.assertLess(math.dist(call.args[1],(60,60)),24)
            self.assertEqual(call.kwargs['max_nodes'],12000)

    def test_already_in_range_returns_current_safe_position(self):
        m=self.world(Image.new('L',(64,64),255));start=(20.,20.)
        self.assertEqual(m.interaction_destination(start,(30,20)),start)

    @unittest.skipUnless((ROOT/'linux/world/atlas.json').exists(),'Exported atlas is optional')
    def test_actual_s255_blocked_center_has_short_clear_approach(self):
        try:m=WorldMap('s255')
        except RuntimeError:self.skipTest('s255 is absent from this optional atlas')
        start=(259.8908,277.5358);goal=(275.,255.)
        self.assertFalse(m.walkable(*goal))
        destination=m.interaction_destination(start,goal)
        self.assertLess(math.dist(destination,goal),24)
        self.assertTrue(m.walkable(*destination));self.assertTrue(m.clear(start,destination))
        self.assertLess(math.dist(start,destination),6)
        # Actual input uses minimum 50-ms bursts and one release-frame guard.
        # Verify that the existing loop detector can leave this tight corner
        # and enter talk range instead of endlessly oscillating near the goal.
        from motion_watch import MotionWatch
        from world_map import remaining_path
        import autoplay
        game=autoplay.load_game();position=start;route=m.path(start,destination);watch=MotionWatch(0);now=0
        for _ in range(35):
            if math.dist(position,goal)<24:break
            state={'phase':'world','x':position[0],'y':position[1],
                   'trace':{'enabled':True,'route_type':1,'points':remaining_path(route,position)}}
            preferred=game.trace_step(state,diagonal=True) or game.trace_step(
                {**state,'trace':{'enabled':True,'route_type':2,'points':[goal]}},diagonal=True)
            step=m.steering_step(position,destination,route,preferred_step=preferred,blocked=watch.blocked(position,now))
            if step is None:now+=.2;continue
            vx,vy=m._velocities()[step[0]];milliseconds=step[1]
            guard=(position[0]+vx*(milliseconds+17)/1000,position[1]+vy*(milliseconds+17)/1000)
            self.assertTrue(m.clear(position,guard))
            before=position;position=(position[0]+vx*milliseconds/1000,position[1]+vy*milliseconds/1000);now+=.2
            if not watch.observe(before,position,*step,now):route=m.path(position,destination)
        self.assertLess(math.dist(position,goal),24)

if __name__=='__main__':unittest.main(verbosity=2)
