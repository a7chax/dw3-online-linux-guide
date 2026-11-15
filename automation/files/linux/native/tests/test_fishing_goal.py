"""Persistent confirmed defeats and the requested fishing fallback."""
import copy
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from fishing_goal import FishingGoal


def result(outcome='defeat',**changes):
    battle={'active':True,'telemetry_complete':True,'result':'defeat','battle_id':'run:7',
            'result_ready':True,'can_advance':True,'transitioning':False,'submitted':False}
    battle['result']=outcome;battle.update(changes)
    return {'pid':123,'phase':'world','map':'s345','battle':battle}


class FishingGoalTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.session=Path(temp.name);self.goal=FishingGoal(self.session)
    def test_next_confirmed_loss_switches_goal(self):
        self.assertEqual(self.goal.report()['mode'],'main_quest')
        s=result();before=copy.deepcopy(s);self.goal.observe(s)
        self.assertEqual(s,before)
        self.assertEqual(self.goal.report()['losses'],1)
        self.assertEqual(self.goal.report()['mode'],'diverlake_fishing')
    def test_repeated_result_and_restart_count_once(self):
        self.goal.observe(result());self.goal.observe(result(menu_token='another-row'))
        restored=FishingGoal(self.session);restored.observe(result())
        self.assertEqual(restored.report()['losses'],1)
        restored.observe(result(battle_id='run:9'))
        self.assertEqual(restored.report()['losses'],2)
    def test_victory_escape_unknown_and_early_results_do_not_count(self):
        samples=[result('victory'),result('escape'),result(None),result(result_ready=False,can_advance=False),
                 result(telemetry_complete=False),result(transitioning=True),result(active=False),result(battle_id=None)]
        for s in samples:self.goal.observe(s)
        self.assertEqual(self.goal.report()['losses'],0)
        self.assertEqual(self.goal.report()['mode'],'main_quest')
    def test_count_survives_nonbattle_snapshot(self):
        self.goal.observe(result());self.goal.observe({'pid':123,'phase':'world','map':'s345'})
        self.assertEqual(self.goal.report()['mode'],'diverlake_fishing')
    def test_ready_result_is_handled_before_fishing_travel(self):
        self.goal.observe(result())
        self.assertIsNone(self.goal.decide(result()))
    def test_no_fishing_override_before_loss(self):
        self.assertIsNone(self.goal.decide({'pid':123,'phase':'world','map':'s345','movement_ready':True}))

    def test_fishing_route_uses_its_destination_instead_of_quest_gps(self):
        class Route:
            def plan(self,*args,**kwargs):return {'legs':[{'kind':'exit','x':80,'y':90,'expected_next_maps':['s380']}]}
        goal=FishingGoal(self.session,router_factory=Route);goal.observe(result())
        s={'pid':123,'phase':'world','map':'s345','x':20,'y':30,'movement_ready':True}
        decision=goal.decide(s)
        self.assertEqual(decision['action'],'fishing_travel')
        self.assertEqual(decision['destination'],(80,90));self.assertTrue(decision['cross_map'])
    def test_unavailable_route_keeps_fishing_goal_and_waits(self):
        from world_map import NoRouteError
        class Missing:
            def plan(self,*args,**kwargs):raise NoRouteError('No route')
        goal=FishingGoal(self.session,router_factory=Missing);goal.observe(result())
        decision=goal.decide({'pid':123,'phase':'world','map':'s345','x':20,'y':30,'movement_ready':True})
        self.assertIsNone(decision['action']);self.assertEqual(decision['reason'],'fishing_route_unavailable')
        self.assertEqual(goal.report()['mode'],'diverlake_fishing')

    def lake(self,**changes):
        self.goal.observe(result())
        fishing={'telemetry_complete':True,'state_token':'cast-1','at_spot':True,'can_cast':False,
                 'can_reel':False,'reel_good':False,'active':False,'cast_facing':0,'facing':0,'exhausted':False}
        fishing.update(changes)
        return {'pid':123,'phase':'world','map':'s380','x':590.,'y':519.,'movement_ready':True,
                'native_fishing_control':True,'fishing':fishing}
    def test_lake_cast_uses_fresh_native_readiness(self):
        self.assertEqual(self.goal.decide(self.lake(can_cast=True))['action'],'fishing_cast')
    def test_reel_waits_for_original_good_timing(self):
        s=self.lake(active=True,can_reel=True,fishing_type=0);s['movement_ready']=False
        self.assertEqual(self.goal.decide(s)['reason'],'fishing_wait_timing')
        s['fishing']['reel_good']=True
        self.assertEqual(self.goal.decide(s)['action'],'fishing_reel')
    def test_unknown_lake_telemetry_never_sends_space(self):
        s=self.lake(can_cast=True,telemetry_complete=False)
        self.assertIsNone(self.goal.decide(s)['action'])
    def test_face_server_shore_direction_before_casting(self):
        s=self.lake(cast_facing=0,facing=4)
        decision=self.goal.decide(s)
        self.assertEqual(decision['action'],'fishing_align');self.assertEqual(decision['step'],('down',50))
    def test_at_hint_without_server_spot_does_not_blindly_cast(self):
        decision=self.goal.decide(self.lake(at_spot=False,cast_facing=255))
        self.assertIsNone(decision['action']);self.assertEqual(decision['reason'],'fishing_spot_unconfirmed')
    def test_exhausted_pool_is_acknowledged_without_claiming_a_catch(self):
        s=self.lake(exhausted=True,active=True,can_reel=True,fishing_type=8)
        self.assertEqual(self.goal.decide(s)['action'],'fishing_exhausted')

    def test_exhausted_pool_leaves_and_returns_in_fishing_mode(self):
        class Route:
            def leave_lake(self,*args):return {'kind':'exit','x':100,'y':100,'expected_next_maps':['s375']}
            def plan(self,*args):return {'legs':[{'kind':'exit','x':200,'y':200,'expected_next_maps':['s380']}]}
        s=self.lake(exhausted=True,active=True,can_reel=True,fishing_type=8)
        self.goal.router=Route();self.goal.decide(s)
        s['fishing'].update(active=False,can_reel=False,fishing_type=None,exhausted=False,at_spot=False)
        decision=self.goal.decide(s)
        self.assertEqual(decision['reason'],'refresh_exhausted_lake');self.assertTrue(decision['cross_map'])
        s['map']='s375';decision=self.goal.decide(s)
        self.assertEqual(decision['reason'],'travel_to_diverlake');self.assertTrue(self.goal.fishing)
        self.assertNotIn('refresh_lake',self.goal.saved)

    def test_reached_shore_hint_is_probed_once_without_inventing_permission(self):
        self.goal.observe(result())
        decision={'action':'fishing_travel','shore_key':'s380:486:571','destination':(486,571)}
        self.goal.note_result(decision,{'reason':'destination_reached','current':{'map':'s380','x':484,'y':573}})
        self.assertIn('s380:486:571',self.goal.saved['shore_probes'])
        restored=FishingGoal(self.session)
        self.assertIn('s380:486:571',restored.saved['shore_probes'])
    def test_interrupted_shore_approach_is_not_marked_as_tested(self):
        self.goal.observe(result())
        self.goal.note_result({'action':'fishing_travel','shore_key':'s380:486:571'}, {'reason':'battle_active'})
        self.assertEqual(self.goal.saved.get('shore_probes',[]),[])

    def test_lake_route_chooses_connected_shore_instead_of_island_poi(self):
        from fishing_goal import LakeRoutes
        class Shore:
            def candidates(self,position):return [(486.5,571.5),(510.5,580.5)]
        route=LakeRoutes.__new__(LakeRoutes);route.inns={'s380'};route.shores={'s380':Shore()}
        route._local_cost=lambda *args:10
        plan=route.plan('s380',340,106)
        self.assertEqual((plan['legs'][0]['x'],plan['legs'][0]['y']),(486.5,571.5))
        plan=route.plan('s380',340,106,probed=['s380:486.5:571.5'])
        self.assertEqual(plan['legs'][0]['x'],510.5)

if __name__=='__main__':unittest.main()
