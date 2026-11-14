"""Inn recovery decisions never inject input or alter party health."""
from pathlib import Path
import copy,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from inn_recovery import InnRecovery

def state(dead=True):
    return {'pid':123,'phase':'world','map':'field','x':10.,'y':20.,'facing':6,
            'movement_ready':True,'native_inn_recovery':True,
            'main_quest':{'chapter':9,'step':6},
            'party':{'telemetry_complete':True,'count':2,'any_fainted':dead,'members':[
                {'slot':0,'id':1,'hp':100,'max_hp':100},{'slot':1,'id':2,'hp':0 if dead else 100,'max_hp':100}]},
            'wallet':{'telemetry_complete':True,'bits':1000},'inn':{'active':False},
            'nearby_inns_complete':True,'nearby_inns':[]}

class Router:
    def __init__(self):self.calls=[]
    def plan(self,map_id,x,y,excluded=()):
        self.calls.append((map_id,x,y,tuple(excluded)))
        leg={'map':map_id,'kind':'exit','x':50,'y':60,'expected_next_maps':['inn']}
        if map_id=='inn':leg={'map':map_id,'kind':'inn','x':None,'y':None,'expected_next_maps':[]}
        return {'inn_id':'inn','map':'inn','cost':30,'estimated':True,'legs':[leg]}

class InnTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.session=Path(temporary.name);self.router=Router();self.now=0
        self.recovery=InnRecovery(self.session,router_factory=lambda:self.router,clock=lambda:self.now)
    def offer(self,**changes):
        s=state();s['map']='inn';s['movement_ready']=False
        s['inn']={'active':True,'telemetry_complete':True,'state':'offer','selected_option':0,
                  'cost_bits':100,'can_confirm':True,'submitted':False}
        s['inn'].update(changes);return s
    def test_any_reserve_faint_triggers_inn_travel(self):
        decision=self.recovery.decide(state())
        self.assertEqual(decision['action'],'inn_travel');self.assertTrue(decision['cross_map'])
        self.assertEqual(decision['destination'],(50,60));self.assertTrue(self.recovery.pending)
    def test_healthy_party_does_not_leave_quest(self):
        self.assertIsNone(self.recovery.decide(state(False)));self.assertEqual(self.router.calls,[])
    def test_active_battle_is_not_interrupted_for_inn_travel(self):
        s=state();s['battle']={'active':True};self.assertIsNone(self.recovery.decide(s))
        self.assertEqual(self.router.calls,[])
    def test_affordable_normal_stay_and_no_duplicate_payment(self):
        s=self.offer();d=self.recovery.decide(s);self.assertEqual(d['action'],'inn_stay')
        self.recovery.note_result(d,{'current':s})
        self.assertIsNone(self.recovery.decide(s)['action'])
    def test_insufficient_bit_cancel_option_or_unknown_price_never_confirm(self):
        for changes in ({'cost_bits':1001},{'selected_option':1},{'cost_bits':None},{'telemetry_complete':False}):
            with self.subTest(changes=changes):self.assertIsNone(self.recovery.decide(self.offer(**changes))['action'])
    def test_animation_ack_is_not_party_revival(self):
        s=self.offer(state='resting',can_confirm=False)
        self.assertIsNone(self.recovery.decide(s)['action']);self.assertTrue(self.recovery.pending)
        s['inn']={'active':False};s['party']=state(False)['party'];s['movement_ready']=True
        self.assertEqual(self.recovery.decide(s)['action'],'inn_recovered');self.assertFalse(self.recovery.pending)
    def test_missing_health_telemetry_does_not_resume_quest(self):
        s=state();s['party']['telemetry_complete']=False
        self.assertEqual(self.recovery.decide(s)['reason'],'party_telemetry_unavailable')
    def test_recovery_intent_survives_controller_restart(self):
        self.recovery.decide(state())
        resumed=InnRecovery(self.session,router_factory=lambda:self.router,clock=lambda:self.now)
        self.assertTrue(resumed.pending);self.assertEqual(resumed.decide(self.offer())['action'],'inn_stay')
    def test_inn_target_uses_fresh_npc_position(self):
        s=state();s.update(map='inn',x=40.,y=50.,facing=6)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':7,'x':50,'y':50}]
        self.assertEqual(self.recovery.decide(s)['action'],'inn_interact')
    def test_game_interaction_check_opens_counter_dialogue_beyond_24_pixels(self):
        s=state();s.update(map='inn',x=357.35846,y=338.4521,facing=5)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':4,'x':345,'y':308,
                          'can_interact':True,'interaction_facings':[3,4,5]}]
        self.assertEqual(self.recovery.decide(s)['action'],'inn_interact')
    def test_game_interaction_facings_take_priority_over_radial_approach(self):
        s=state();s.update(map='inn',x=357.35846,y=338.4521,facing=6)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':4,'x':345,'y':308,
                          'can_interact':False,'interaction_facings':[4]}]
        d=self.recovery.decide(s);self.assertEqual(d['action'],'inn_align');self.assertEqual(d['step'],('up',50))
    def test_ready_innkeeper_is_preferred_over_a_closer_unreachable_candidate(self):
        s=state();s.update(map='inn',x=40.,y=50.,facing=6)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':7,'x':45,'y':50,
                          'can_interact':False,'interaction_facings':[]},
                         {'map':'inn','logical_id':20,'entity_id':8,'x':70,'y':50,
                          'can_interact':True,'interaction_facings':[6]}]
        d=self.recovery.decide(s);self.assertEqual(d['action'],'inn_interact');self.assertEqual(d['npc']['entity_id'],8)
    def test_failed_nearby_inn_is_excluded_before_selecting_another(self):
        s=state();s.update(map='inn',x=10.,y=10.)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':7,'x':100,'y':100}]
        for _ in range(3):
            d=self.recovery.decide(s);self.recovery.note_result(d,{'reason':'local_route_unavailable','current':s})
        d=self.recovery.decide(s)
        self.assertEqual(self.router.calls[-1][-1],('inn',))
        self.assertIsNone(d['action'])
    def test_ambiguous_gatomon_is_only_a_candidate_until_inn_offer(self):
        s=state();s.update(map='inn',x=40.,y=50.,facing=6)
        s['nearby_inns']=[{'map':'inn','logical_id':None,'inn_candidate':True,'entity_id':e,'x':x,'y':50}
                          for e,x in ((7,50),(8,55))]
        d=self.recovery.decide(s);self.assertEqual(d['action'],'inn_interact');self.assertEqual(d['npc']['entity_id'],7)
        after=copy.deepcopy(s);after['dialogue']={'can_advance':True}
        self.recovery.note_result(d,{'current':after})
        d=self.recovery.decide(s);self.assertEqual(d['npc']['entity_id'],8)

if __name__=='__main__':unittest.main()
