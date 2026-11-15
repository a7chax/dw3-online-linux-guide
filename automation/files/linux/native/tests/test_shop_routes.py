"""Shop routing reuses validated world hints without treating inns as shops."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from linux.native.tests.test_inn_routes import InnRouteTests
from shop_routes import ShopRoutes

class ShopRouteTests(unittest.TestCase):
    fixture=InnRouteTests.fixture
    def test_item_shop_markers_and_catalog_are_distinct_from_inns(self):
        root=self.fixture();path=root/'auxiliary/npcs.json'
        rows=json.loads(path.read_text());rows.append({'stage':'inn','npc':22,'character':'p038wiza','file':5,'texts':[66]});path.write_text(json.dumps(rows))
        path=root/'auxiliary/worldmap/world.json';data=json.loads(path.read_text());data['worlds'][0]['doors'][0]['pois']=[[0,3]];path.write_text(json.dumps(data))
        routes=ShopRoutes(root);plan=routes.plan('a',15,40)
        self.assertEqual(plan['shop_id'],'inn');self.assertEqual(plan['legs'][-1]['kind'],'shop')
        self.assertTrue(routes.is_shop_dialogue('inn',{'text_file':5,'text_index':66}))
        self.assertFalse(routes.is_shop_dialogue('inn',{'text_file':6,'text_index':363}))
