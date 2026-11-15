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
    def test_missing_inn_route_defers_and_returns_control_to_quest(self):
        from world_map import NoRouteError
        class Missing:
            calls=0
            def plan(self,*args,**kwargs):self.calls+=1;raise NoRouteError('No link')
        missing=Missing();self.recovery.router_factory=lambda:missing
        self.assertIsNone(self.recovery.decide(state()))
        self.assertTrue(self.recovery.report()['deferred'])
        self.assertEqual(self.recovery.report()['deferred_reason'],'inn_route_unavailable')
        self.assertIsNone(self.recovery.decide(state()));self.assertEqual(missing.calls,1)
        resumed=InnRecovery(self.session,router_factory=lambda:missing,clock=lambda:self.now)
        self.assertIsNone(resumed.decide(state()));self.assertEqual(missing.calls,1)

    def test_unreachable_keeper_stops_detour_after_bounded_failures(self):
        current=state();current.update(map='inn',x=10.,y=10.)
        current['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':7,'x':100,'y':100}]
        for _ in range(3):
            decision=self.recovery.decide(current)
            self.recovery.note_result(decision,{'reason':'local_route_unavailable','current':current})
        self.assertIsNone(self.recovery.decide(current))
        self.assertTrue(self.recovery.report()['deferred'])

    def test_reachable_nearby_keeper_can_override_deferred_trip(self):
        from world_map import NoRouteError
        class Missing:
            def plan(self,*args,**kwargs):raise NoRouteError('No link')
        self.recovery.router_factory=Missing
        self.recovery.decide(state())
        current=state();current.update(map='other-inn',x=40.,y=50.,facing=6)
        current['nearby_inns']=[{'map':'other-inn','logical_id':20,'entity_id':9,'x':50,'y':50,'can_interact':True,'interaction_facings':[6]}]
        self.assertEqual(self.recovery.decide(current)['action'],'inn_interact')

    def test_inn_retry_is_bounded_by_cooldown(self):
        from world_map import NoRouteError
        class Flaky:
            fail=True;calls=0
            def plan(inner,*args,**kwargs):
                inner.calls+=1
                if inner.fail:raise NoRouteError('No link')
                return self.router.plan(*args,**kwargs)
        router=Flaky();self.recovery.router_factory=lambda:router
        self.recovery.decide(state());router.fail=False
        self.now=299;self.assertIsNone(self.recovery.decide(state()));self.assertEqual(router.calls,1)
        self.now=301;self.assertEqual(self.recovery.decide(state())['action'],'inn_travel');self.assertEqual(router.calls,2)

    def test_deferral_keeps_fainted_state_and_blocks_when_no_member_can_fight(self):
        from world_map import NoRouteError
        class Missing:
            def plan(self,*args,**kwargs):raise NoRouteError('No link')
        self.recovery.router_factory=Missing
        current=state();before=copy.deepcopy(current)
        self.assertIsNone(self.recovery.decide(current));self.assertEqual(current,before)
        current['party']['members'][0]['hp']=0
        decision=self.recovery.decide(current)
        self.assertIsNone(decision['action']);self.assertEqual(decision['reason'],'all_party_fainted')

    def test_real_inn_offer_can_be_used_during_deferred_quest_mode(self):
        from world_map import NoRouteError
        class Missing:
            def plan(self,*args,**kwargs):raise NoRouteError('No link')
        self.recovery.router_factory=Missing;self.recovery.decide(state())
        offer=self.offer();decision=self.recovery.decide(offer)
        self.assertEqual(decision['action'],'inn_stay')
        self.recovery.note_result(decision,{'current':offer})
        self.assertIsNone(self.recovery.decide(offer)['action'])

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
    def test_failed_nearby_inn_is_excluded_while_quest_resumes(self):
        s=state();s.update(map='inn',x=10.,y=10.)
        s['nearby_inns']=[{'map':'inn','logical_id':20,'entity_id':7,'x':100,'y':100}]
        for _ in range(3):
            d=self.recovery.decide(s);self.recovery.note_result(d,{'reason':'local_route_unavailable','current':s})
        d=self.recovery.decide(s)
        self.assertEqual(self.recovery.job['excluded'],['inn'])
        self.assertEqual(self.router.calls,[])
        self.assertIsNone(d)
    def test_ambiguous_gatomon_is_only_a_candidate_until_inn_offer(self):
        s=state();s.update(map='inn',x=40.,y=50.,facing=6)
        s['nearby_inns']=[{'map':'inn','logical_id':None,'inn_candidate':True,'entity_id':e,'x':x,'y':50}
                          for e,x in ((7,50),(8,55))]
        d=self.recovery.decide(s);self.assertEqual(d['action'],'inn_interact');self.assertEqual(d['npc']['entity_id'],7)
        after=copy.deepcopy(s);after['dialogue']={'can_advance':True}
        self.recovery.note_result(d,{'current':after})
        d=self.recovery.decide(s);self.assertEqual(d['npc']['entity_id'],8)

if __name__=='__main__':unittest.main()
