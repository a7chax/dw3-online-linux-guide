import copy
from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('smart_follow',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

class Window:
    def __init__(self,pid):pass
    def focus(self):pass
    def focused(self):return True
    def close(self):pass

def world():
    return {'phase':'world','map':'fixture','x':40.,'y':40.,'pid':123,'facing':6,
            'movement_directions':['right','up','down_right'],
            'time':datetime.now(timezone.utc).isoformat(),
            'trace':{'enabled':True,'route_type':1,'points':[[70,40],[100,40]]}}

class SmartFollowTests(unittest.TestCase):
    def test_failed_direction_survives_sideways_progress_and_route_refresh(self):
        state=world();calls=[];blocked_seen=[]
        class Terrain:
            def __init__(self,*args):pass
            def steering_step(self,position,goal,path,preferred_step=None,blocked=None,**kwargs):
                blocked={blocked} if isinstance(blocked,str) else set(blocked or ())
                blocked_seen.append(blocked)
                return ('up',50) if 'right' in blocked else ('right',100)
        def movement(direction,milliseconds,**kwargs):
            before=copy.deepcopy(state);calls.append(direction)
            if direction=='right':state['x']+=.1
            else:state['y']-=6
            state['trace']['points'][0][0]+=.1
            if len(calls)>=3:state['map']='next-map'
            return {'before':before,'after':copy.deepcopy(state),'moved':True}
        with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),\
             patch.object(game,'request',side_effect=lambda op:copy.deepcopy(state)),\
             patch.object(game,'move',side_effect=movement),patch('game_control.GameWindow',Window),\
             patch('world_map.WorldMap',Terrain):
            report=game.follow_trace(3)
        self.assertEqual(calls,['right','up','up'])
        self.assertIn('right',blocked_seen[-1])
        self.assertEqual(report['reason'],'map_changed')

    def test_changed_process_stops_before_any_input(self):
        state=world();changed={**state,'pid':456}
        with tempfile.TemporaryDirectory() as td,patch.object(game,'LATEST',Path(td)),\
             patch.object(game,'request',side_effect=[state,changed]),\
             patch.object(game,'move',side_effect=AssertionError('Wrong process must receive no input')) as move,\
             patch('game_control.GameWindow',Window):
            report=game.follow_trace(1)
        move.assert_not_called();self.assertEqual(report['reason'],'session_changed')

if __name__=='__main__':unittest.main()
