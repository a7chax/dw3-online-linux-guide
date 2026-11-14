import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]

class MotionTests(unittest.TestCase):
    def watch(self):
        spec=importlib.util.spec_from_file_location('motion_watch',ROOT/'motion_watch.py')
        if spec is None or not Path(spec.origin).exists():self.fail('MotionWatch is not implemented')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.MotionWatch(0)

    def test_float_bump_is_failed_even_when_coordinates_differ(self):
        w=self.watch()
        self.assertFalse(w.observe((40,40),(40.1,40),'right',100,.1))
        self.assertEqual(w.blocked((40.1,40),.2),{'right'})
        self.assertEqual(w.last_progress,0)

    def test_sideways_detour_does_not_forget_failed_direction(self):
        w=self.watch();w.observe((40,40),(40,40),'right',100,.1)
        self.assertTrue(w.observe((40,40),(40,34),'up',50,.2))
        self.assertIn('right',w.blocked((40,34),.3))
        self.assertNotIn('right',w.blocked((100,34),.3))
        self.assertEqual(w.blocked((40,40),7),set())

    def test_back_and_forth_is_not_continuing_progress(self):
        w=self.watch();x=40
        outcomes=[]
        for index in range(8):
            next_x=44 if index%2==0 else 40
            outcomes.append(w.observe((x,40),(next_x,40),'right' if next_x>x else 'left',50,.1*(index+1)))
            x=next_x
        self.assertFalse(any(outcomes[-4:]))
        self.assertLess(w.last_progress,.5)
        self.assertEqual(w.blocked((40,40),1),{'left','right'})

    def test_real_forward_progress_remains_unrestricted(self):
        w=self.watch()
        for index in range(8):
            self.assertTrue(w.observe((index*12,40),((index+1)*12,40),'right',50,.1*(index+1)))
        self.assertEqual(w.blocked((96,40),1),set())
        self.assertAlmostEqual(w.last_progress,.8)

    def test_large_wrong_direction_displacement_is_not_success(self):
        w=self.watch()
        self.assertFalse(w.observe((40,40),(28,40),'right',100,.1))
        self.assertEqual(w.blocked((28,40),.2),{'right'})

if __name__=='__main__':unittest.main()
