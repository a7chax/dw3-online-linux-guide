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

    def test_explicit_fishing_starts_without_a_loss(self):
        goal=FishingGoal(self.session,activity='fishing')
        self.assertTrue(goal.fishing);self.assertEqual(goal.report()['losses'],0)
        self.assertEqual(goal.report()['activity'],'fishing')
    def test_main_quest_mode_ignores_saved_fishing_fallback(self):
        self.goal.observe(result())
        goal=FishingGoal(self.session,activity='main-quest');goal.observe(result(battle_id='other'))
        self.assertFalse(goal.fishing);self.assertEqual(goal.report()['mode'],'main_quest')
    def test_remaining_bait_is_retained_between_casts(self):
        s=self.lake(active=True,fishing_type=0,cast_count=15)
        self.goal.decide(s);self.assertEqual(self.goal.report()['bait_remaining'],15)
        s['fishing'].update(active=False,fishing_type=None,cast_count=None)
        self.goal.decide(s);self.assertEqual(self.goal.report()['bait_remaining'],15)
        self.assertEqual(FishingGoal(self.session).report()['bait_remaining'],15)
    def test_zero_bait_finishes_last_reel_then_refreshes_map(self):
        class Route:
            def leave_lake(self,*args):return {'kind':'exit','x':100,'y':100,'expected_next_maps':['s375']}
        s=self.lake(active=True,fishing_type=0,cast_count=0,can_reel=True,reel_good=True)
        self.goal.router=Route()
        self.assertEqual(self.goal.decide(s)['action'],'fishing_reel')
        self.assertEqual(self.goal.report()['bait_remaining'],0)
        s['fishing'].update(active=True,fishing_type=None,cast_count=None,can_reel=False,can_cast=True)
        decision=self.goal.decide(s)
        self.assertEqual(decision['action'],'fishing_travel');self.assertTrue(decision['cross_map'])
        self.assertEqual(decision['reason'],'refresh_exhausted_lake')
    def test_unknown_bait_is_not_assumed_to_be_fifteen(self):
        self.goal.decide(self.lake(can_cast=True))
        self.assertIsNone(self.goal.report()['bait_remaining'])
        self.assertEqual(self.goal.report()['bait_capacity'],15)
    def test_actual_exit_clears_stale_bait_and_shore_probes(self):
        s=self.lake(active=True,fishing_type=0,cast_count=0,can_reel=True,reel_good=True)
        self.goal.decide(s);self.goal.saved['shore_probes']=['s380:486.5:571.5']
        class Route:
            def plan(self,*args,**kwargs):return {'legs':[{'kind':'exit','x':200,'y':200}]}
        self.goal.router=Route();s['map']='s375';s['fishing']={}
        self.goal.decide(s)
        self.assertIsNone(self.goal.report()['bait_remaining'])
        self.assertEqual(self.goal.saved.get('shore_probes'),[])
    def test_known_interior_can_use_one_fresh_gps_exit(self):
        from world_map import NoRouteError
        class Interior:
            def plan(self,*args,**kwargs):raise NoRouteError('Interior')
            def is_interior(self,map_id):return map_id=='s360'
        goal=FishingGoal(self.session,activity='fishing',router_factory=Interior)
        s={'pid':123,'phase':'world','map':'s360','x':357,'y':338,'movement_ready':True,
           'trace':{'enabled':True,'route_type':1,'points':[[422,358]]}}
        decision=goal.decide(s)
        self.assertEqual(decision['action'],'fishing_travel');self.assertEqual(decision['destination'],(422,358))
        self.assertTrue(decision['cross_map'])
        s['trace']['route_type']=2
        self.assertIsNone(goal.decide(s)['action'])

    def test_hard_reel_tries_after_two_seconds_without_perfect_window(self):
        now=[0.]
        goal=FishingGoal(self.session,activity='fishing',clock=lambda:now[0])
        s=self.lake(active=True,can_reel=True,fishing_type=1,reel_good=False,cast_count=10)
        self.assertIsNone(goal.decide(s)['action'])
        now[0]=1.9;self.assertIsNone(goal.decide(s)['action'])
        now[0]=2.1;self.assertEqual(goal.decide(s)['action'],'fishing_reel_attempt')
        s['fishing']['state_token']='new-cast'
        self.assertIsNone(goal.decide(s)['action'])
    def test_ready_green_window_is_used_before_reel_deadline(self):
        goal=FishingGoal(self.session,activity='fishing',clock=lambda:0.)
        self.assertEqual(goal.decide(self.lake(active=True,can_reel=True,fishing_type=1,reel_good=True))['action'],'fishing_reel')

if __name__=='__main__':unittest.main()
