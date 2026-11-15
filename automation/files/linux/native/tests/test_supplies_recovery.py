"""Recovery purchases are bounded and require server state changes."""
import copy
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from supplies_recovery import SuppliesRecovery

def state():
 return {'pid':7,'phase':'world','map':'a','x':20.,'y':40.,'movement_ready':True,'native_supplies_control':True,
         'wallet':{'telemetry_complete':True,'bits':20000,'cash':77},
         'supplies':{'telemetry_complete':True,'state_token':'one','inventory_open':False,
           'party':[{'slot':0,'id':4,'hp':20,'max_hp':100,'ds':2,'max_ds':50}],
           'inventory':[{'id':10,'quantity':2,'heal_hp':60,'heal_ds':0},{'id':11,'quantity':2,'heal_hp':0,'heal_ds':30}],
           'shop':{'active':False,'telemetry_complete':True}}}
class Router:
 def plan(self,*args,**kwargs):return {'shop_id':'shop','legs':[{'kind':'exit','x':50,'y':40,'expected_next_maps':['shop']}]}
class SupplyRecoveryTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.session=Path(t.name);self.now=0
  self.controller=SuppliesRecovery(self.session,router_factory=Router,clock=lambda:self.now);self.state=state()
 def test_missing_loaded_rules_uses_normal_inventory_inspection_once(self):
  self.state['supplies'].update(telemetry_complete=False,rules_loaded=False)
  d=self.controller.decide(self.state);self.assertEqual(d['mode'],'inspect')
  self.controller.note_result(d,{'plan':{'key':'i','submit':False}})
  self.assertIsNone(self.controller.decide(self.state))
 def test_unconfirmed_purchase_closes_then_backs_off_without_rebuy(self):
  self.shop();d=self.controller.decide(self.state);self.controller.note_result(d,{'plan':{'key':'space','submit':True}})
  self.now=21
  self.assertEqual(self.controller.decide(self.state)['mode'],'close')
  self.state['supplies']['shop']['active']=False
  self.state['supplies']['party'][0].update(hp=100,ds=50)
  self.assertIsNone(self.controller.decide(self.state))
  self.assertGreater(self.controller.next_restock,self.now)
 def test_zero_key_failure_does_not_retry_same_unchanged_item(self):
  self.state['supplies']['party'][0]['ds']=50
  d=self.controller.decide(self.state)
  self.controller.note_result(d,{'plan':{'key':None,'reason':'item_not_visible','submit':False}})
  self.state['supplies']['party'][0]['ds']=50
  self.state['supplies']['inventory_open']=True
  self.assertEqual(self.controller.decide(self.state)['mode'],'close')
 def test_uses_owned_hp_item_before_shopping(self):
  d=self.controller.decide(self.state);self.assertEqual((d['action'],d['mode'],d['item_id'],d['party_slot']),('supplies_step','use',10,0))
 def test_ds_deficit_uses_ds_item_after_hp_is_healthy(self):
  self.state['supplies']['party'][0]['hp']=100
  self.assertEqual(self.controller.decide(self.state)['item_id'],11)
 def test_fainted_party_goes_to_existing_inn_controller(self):
  self.state['supplies']['party'][0]['hp']=0;self.assertIsNone(self.controller.decide(self.state))
 def test_use_waits_for_quantity_and_hp_change_before_another_item(self):
  d=self.controller.decide(self.state);self.controller.note_result(d,{'plan':{'key':'space','submit':True}})
  self.assertEqual(self.controller.decide(self.state)['reason'],'item_use_verifying')
  self.state['supplies']['inventory'][0]['quantity']-=1
  self.assertEqual(self.controller.decide(self.state)['reason'],'item_use_verifying')
  self.state['supplies']['party'][0]['hp']=80
  self.state['supplies']['inventory_open']=True
  self.assertEqual(self.controller.decide(self.state)['mode'],'close')
 def test_missing_supplies_routes_to_item_shop(self):
  self.state['supplies']['inventory']=[]
  d=self.controller.decide(self.state);self.assertEqual(d['action'],'supplies_travel');self.assertEqual(d['destination'],(50,40))
 def shop(self):
  self.state['supplies']['inventory']=[]
  self.state['supplies']['shop']={'active':True,'telemetry_complete':True,'offer_token':'offer1','mode':'buy','submitting':False,
    'offers':[{'index':0,'id':10,'unit_bits':200,'heal_hp':60,'heal_ds':0},
              {'index':1,'id':11,'unit_bits':100,'heal_hp':0,'heal_ds':30},
              {'index':2,'id':12,'unit_bits':0,'heal_hp':999,'heal_ds':999,'currency':'cash'}]}
 def test_purchase_uses_server_price_budget_and_retains_reserve(self):
  self.shop();d=self.controller.decide(self.state)
  self.assertEqual((d['mode'],d['quantity'],d['unit_bits']),('buy',3,200))
  self.assertEqual(d['expected_offer_token'],'offer1');self.assertLessEqual(d['quantity'],5)
  self.assertEqual(self.state['wallet']['cash'],77)
 def test_purchase_is_not_repeated_while_server_confirmation_is_pending(self):
  self.shop();d=self.controller.decide(self.state);self.controller.note_result(d,{'plan':{'key':'space','submit':True}})
  self.assertEqual(self.controller.decide(self.state)['reason'],'purchase_verifying')
  restored=SuppliesRecovery(self.session,router_factory=Router,clock=lambda:self.now)
  self.assertEqual(restored.decide(self.state)['reason'],'purchase_verifying')
 def test_insufficient_reserve_and_cash_only_offers_never_purchase(self):
  self.shop();self.state['wallet']['bits']=5000
  self.assertEqual(self.controller.decide(self.state)['mode'],'close')
 def test_battle_and_incomplete_telemetry_do_not_use_world_items(self):
  self.state['battle']={'active':True};self.assertIsNone(self.controller.decide(self.state))
  self.state.pop('battle');self.state['supplies']['telemetry_complete']=False
  self.assertIsNone(self.controller.decide(self.state))
 def test_confirmed_purchase_tracks_spend_then_selects_other_needed_supply(self):
  self.shop();d=self.controller.decide(self.state);self.controller.note_result(d,{'plan':{'key':'space','submit':True}})
  self.state['supplies']['inventory']=[{'id':10,'quantity':3,'heal_hp':60,'heal_ds':0}]
  self.state['wallet']['bits']-=600
  next_decision=self.controller.decide(self.state)
  self.assertEqual(next_decision['item_id'],11)
  self.assertEqual(self.controller.job['spent_bits'],600)
