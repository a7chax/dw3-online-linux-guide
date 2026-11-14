from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('interrupted_follow',ROOT/'ai-game.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)

class Window:
    def __init__(self,pid):pass
    def focus(self):pass
    def focused(self):return True
    def close(self):pass

class Interruptions(unittest.TestCase):
    def test_modal_state_stops_navigation_before_input(self):
        cases=[({'battle':{'active':True}},'battle_active'),
               ({'story':{'active':True}},'story_active'),
               ({'dialogue':{'can_advance':False}},'interaction_required'),
               ({'movement_ready':False},'world_input_blocked')]
        for extra,reason in cases:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as directory:
                state={'phase':'world','pid':123,'map':'fixture','x':10,'y':10,
                       'time':datetime.now(timezone.utc).isoformat(),
                       'trace':{'enabled':True,'route_type':1,'points':[[100,10]]},**extra}
                with patch.object(game,'LATEST',Path(directory)),patch.object(game,'request',return_value=state),\
                     patch.object(game,'move',side_effect=AssertionError('Modal state must prevent movement')) as move,\
                     patch('game_control.GameWindow',Window):
                    report=game.follow_trace(1)
                move.assert_not_called()
                self.assertEqual(report['reason'],reason)

if __name__=='__main__':unittest.main()
