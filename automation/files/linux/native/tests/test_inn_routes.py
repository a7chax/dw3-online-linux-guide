import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from inn_routes import InnRoutes,NoRouteError


class InnRouteTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);(root/'auxiliary/worldmap').mkdir(parents=True)
        spots=[{'ids':['a','alias'],'at':[[0,0],[40,0]],'x':100,'y':100,'pois':[]},
               {'ids':['b'],'x':300,'y':100,'pois':[[2,70,40]]}]
        world={'name':'fixture','spots':spots,'links':[[0,180,140,1,310,140]],'passages':[],
               'doors':[{'spot':0,'x':120,'y':140,'ids':['inn'],'pois':[[2,1]]},
                        {'spot':0,'x':110,'y':140,'ids':['inn'],'pois':[]}]}
        (root/'auxiliary/worldmap/world.json').write_text(json.dumps({'worlds':[world]}))
        (root/'auxiliary/npcs.json').write_text(json.dumps([
            {'stage':s,'npc':20,'character':'p039tail','file':6,'texts':[362,363]} for s in ['inn','b']]+[
            {'stage':'inn','npc':121,'character':'p039tail','file':6,'texts':[276]}]))
        maps=[]
        for name in ['a','alias','b','inn']:
            Image.new('L',(100,80),255).save(root/(name+'.png'))
            maps.append({'id':name,'width':100,'height':80,'collision':name+'.png'})
        (root/'atlas.json').write_text(json.dumps({'maps':maps}))
        return root

    def test_nearest_inn_door_uses_only_inn_marker(self):
        route=InnRoutes(self.fixture()).plan('a',15,40)
        self.assertEqual(route['inn_id'],'inn')
        self.assertEqual(route['legs'][0]['x'],20)
        self.assertEqual(route['legs'][0]['expected_next_maps'],['inn'])
        self.assertEqual(route['legs'][-1]['kind'],'inn')
        self.assertIsNone(route['legs'][-1]['x'])
        self.assertTrue(route['estimated'])

    def test_alias_offset_and_exclusion_choose_graph_inn(self):
        route=InnRoutes(self.fixture()).plan('alias',10,40,excluded={'inn'})
        self.assertEqual(route['inn_id'],'b')
        self.assertEqual(route['legs'][0]['map'],'alias')
        self.assertEqual((route['legs'][0]['x'],route['legs'][0]['y']),(40,40))
        self.assertEqual(route['legs'][0]['expected_next_maps'],['b'])
        self.assertEqual(route['legs'][-1]['kind'],'inn_approach')
        self.assertEqual((route['legs'][-1]['x'],route['legs'][-1]['y']),(70,40))

    def test_blocked_first_leg_is_skipped(self):
        root=self.fixture();image=Image.new('L',(100,80),255)
        ImageDraw.Draw(image).rectangle((35,0,45,79),fill=0);image.save(root/'a.png')
        with self.assertRaises(NoRouteError):InnRoutes(root).plan('a',20,40,excluded={'inn'})

    def test_no_unlisted_edges_or_interior_exit_are_invented(self):
        root=self.fixture()
        with self.assertRaises(NoRouteError):InnRoutes(root).plan('missing',10,40)
        route=InnRoutes(root).plan('inn',20,40)
        self.assertEqual(route['cost'],0)
        self.assertEqual(route['legs'],[{'map':'inn','x':None,'y':None,'kind':'inn','expected_next_maps':[]}])

    def test_current_outdoor_inn_still_plans_to_its_poi(self):
        route=InnRoutes(self.fixture()).plan('b',20,40)
        self.assertEqual(route['inn_id'],'b')
        self.assertEqual(route['cost'],50)
        self.assertEqual(route['legs'][-1]['kind'],'inn_approach')
        self.assertEqual(route['legs'][-1]['x'],70)

    def test_inn_greeting_matches_exact_bundled_map_file_and_index(self):
        routes=InnRoutes(self.fixture())
        self.assertTrue(routes.is_inn_dialogue('inn',{'text_file':6,'text_index':363}))
        self.assertFalse(routes.is_inn_dialogue('inn',{'text_file':6,'text_index':276}))
        self.assertFalse(routes.is_inn_dialogue('inn',{'text_file':5,'text_index':363}))
        self.assertFalse(routes.is_inn_dialogue('a',{'text_file':6,'text_index':363}))
        self.assertFalse(routes.is_inn_dialogue('inn',None))
        self.assertFalse(routes.is_inn_dialogue('inn',{'text_file':6}))

    def shortcut_fixture(self):
        root=self.fixture();p=root/'auxiliary/worldmap/world.json';data=json.loads(p.read_text());w=data['worlds'][0]
        w['spots'][0]['ids']=['a'];w['spots'][0]['at']=[[0,0]]
        w['spots'][1]['pois']=[]
        w['links']=[[0,115,140,1,310,140],[1,320,140,0,175,140]]
        w['doors']=[{'spot':0,'x':180,'y':140,'ids':['inn'],'pois':[[2,1]]}]
        p.write_text(json.dumps(data));return root

    def test_reachable_inn_does_not_take_optimistic_return_shortcut(self):
        route=InnRoutes(self.shortcut_fixture()).plan('a',10,40)
        self.assertEqual([leg['map'] for leg in route['legs']],['a','inn'])
        self.assertEqual((route['legs'][0]['x'],route['legs'][0]['y']),(80,40))

    def test_disconnected_current_map_can_still_use_real_detour(self):
        root=self.shortcut_fixture();image=Image.new('L',(100,80),255)
        ImageDraw.Draw(image).rectangle((40,0,50,79),fill=0);image.save(root/'a.png')
        route=InnRoutes(root).plan('a',10,40)
        self.assertEqual([leg['map'] for leg in route['legs']],['a','b','a','inn'])

    def test_actual_mirage_tower_chooses_hall_entrance_if_exported(self):
        root=Path(__file__).resolve().parents[3]/'linux/world'
        if not (root/'auxiliary/worldmap/world.json').exists():self.skipTest('Optional original assets not exported')
        route=InnRoutes(root).plan('s645',731.8292,566.1649)
        self.assertEqual((route['legs'][0]['x'],route['legs'][0]['y']),(644,250))
        self.assertEqual(route['legs'][0]['expected_next_maps'],['s650'])

    def test_actual_catalog_if_exported(self):
        root=Path(__file__).resolve().parents[3]/'linux/world'
        if not (root/'auxiliary/worldmap/world.json').exists():self.skipTest('Optional original assets not exported')
        routes=InnRoutes(root)
        self.assertTrue(routes.is_inn_dialogue('s360',{'text_file':6,'text_index':363}))
        route=routes.plan('s465',433,190)
        self.assertEqual(route['inn_id'],'s470')
        self.assertEqual((route['legs'][0]['x'],route['legs'][0]['y']),(433,175))


if __name__=='__main__':unittest.main()
