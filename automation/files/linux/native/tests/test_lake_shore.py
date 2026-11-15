"""Shore candidates are connected collision hints, never cast permissions."""
from pathlib import Path
import json,sys,tempfile,unittest
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lake_shore import ShoreApproach

class ShoreTests(unittest.TestCase):
    def test_disconnected_hint_uses_current_component_boundary_and_caches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'maps/test').mkdir(parents=True)
            image=Image.new('L',(100,70),0)
            for x in range(5,45):
                for y in range(5,65):image.putpixel((x,y),1)
            for x in range(60,96):
                for y in range(5,65):image.putpixel((x,y),1)
            image.save(root/'maps/test/collision.png')
            (root/'atlas.json').write_text(json.dumps({'maps':[{'id':'test','width':100,'height':70,'collision':'maps/test/collision.png'}]}))
            shore=ShoreApproach('test',root=root,hint=(80,35))
            candidates=shore.candidates((20,35));self.assertTrue(candidates)
            self.assertEqual(candidates[0],(41.5,35.5))
            self.assertLessEqual(len(candidates),24)
            self.assertTrue(all(point[0]<45 for point in candidates))
            self.assertEqual(candidates,shore.candidates((21,35)))
            self.assertEqual(shore.component_searches,1)
            other=shore.candidates((80,35));self.assertEqual(other[0],(80.5,35.5));self.assertEqual(shore.component_searches,2)
    def test_blocked_start_never_selects_unconnected_hint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);image=Image.new('L',(20,20),0);image.save(root/'mask.png')
            (root/'atlas.json').write_text(json.dumps({'maps':[{'id':'test','width':20,'height':20,'collision':'mask.png'}]}))
            from world_map import NoRouteError
            with self.assertRaises(NoRouteError):ShoreApproach('test',root=root).candidates((10,10))
    def test_real_lake_mainland_candidate_is_reachable_from_both_entrances(self):
        # Optional integration evidence in the inspected game installation;
        # source-only kits intentionally omit map assets.
        if not (ROOT/'linux/world/maps/s380/collision.png').exists():self.skipTest('Original atlas not installed')
        from world_map import WorldMap
        shore=ShoreApproach('s380');points=shore.candidates((340,106))
        self.assertEqual(points[0],(486.5,571.5))
        atlas=WorldMap('s380')
        for entrance in ((340,106),(1199,886)):
            self.assertTrue(atlas.path(entrance,points[0],max_nodes=12000))
        self.assertEqual(points,shore.candidates((1199,886)))
        self.assertEqual(shore.component_searches,1)
if __name__=='__main__':unittest.main()
