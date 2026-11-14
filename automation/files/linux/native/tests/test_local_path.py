#!/usr/bin/env python3
from pathlib import Path
import json,sys,tempfile,unittest
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import world_map
class LocalPathTests(unittest.TestCase):
 def test_routes_around_wall_through_gap(self):
  path=ROOT/'world_map.py'
  self.assertTrue(path.exists(),'Local collision-map planner is missing')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);image=Image.new('L',(64,64),255)
   for y in range(50):
    for x in range(29,35):image.putpixel((x,y),0)
   image.save(root/'mask.png')
   (root/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',name='Test',width=64,height=64,collision='mask.png')]}))
   m=world_map.WorldMap('test',root)
   points=m.path((12,12),(52,12),step=4)
   self.assertGreater(max(p[1] for p in points),50)
   for a,b in zip(points,points[1:]):self.assertTrue(m.clear(a,b))
   self.assertEqual(points[-1],[52.0,12.0])
   with self.assertRaisesRegex(RuntimeError,'blocked'):m.path((12,12),(31,12))
 def test_narrow_corridor_has_finer_grid_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);image=Image.new('L',(64,64),0)
   for x in list(range(4,25))+list(range(40,61)):
    for y in range(4,60):image.putpixel((x,y),255)
   for x in range(20,45):
    for y in range(29,32):image.putpixel((x,y),255)
   image.save(root/'mask.png');(root/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',width=64,height=64,collision='mask.png')]}))
   m=world_map.WorldMap('test',root);points=m.path((12,12),(52,12))
   self.assertEqual(points[0],[12.0,12.0]);self.assertEqual(points[-1],[52.0,12.0])
   for a,b in zip(points,points[1:]):self.assertTrue(m.clear(a,b))
 def test_every_pixel_touched_by_diagonal_is_checked(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);image=Image.new('L',(64,64),255);image.putpixel((32,32),0)
   image.save(root/'mask.png');(root/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',width=64,height=64,collision='mask.png')]}))
   m=world_map.WorldMap('test',root)
   start=(39.493850623519876,37.08897869478453)
   end=(21.722560154706915,30.042400135098625)
   self.assertTrue(m.walkable(*start));self.assertTrue(m.walkable(*end))
   self.assertFalse(m.walkable(29.17761650637395,32.99843984088686))
   self.assertFalse(m.clear(start,end))
   self.assertFalse(m.clear(end,start))
 def test_grid_boundaries_and_corner_contacts(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);image=Image.new('L',(64,64),255);image.putpixel((32,28),0)
   image.save(root/'mask.png');(root/'atlas.json').write_text(json.dumps({'maps':[dict(id='test',width=64,height=64,collision='mask.png')]}))
   m=world_map.WorldMap('test',root)
   # The right-hand clearance trace touches the obstacle's corner.
   start,end=(20.5,20.5),(40.5,40.5)
   self.assertTrue(m.walkable(*start));self.assertTrue(m.walkable(*end))
   self.assertFalse(m.clear(start,end));self.assertFalse(m.clear(end,start))
   # Exact horizontal/vertical grid lines remain usable in both directions.
   for start,end in [((12,12),(48,12)),((12,12),(12,48)),((12,12),(12,12))]:
    self.assertTrue(m.clear(start,end));self.assertTrue(m.clear(end,start))
if __name__=='__main__':unittest.main(verbosity=2)
