#!/usr/bin/env python3
from pathlib import Path
import importlib.util,sys,tempfile,unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('popup_game',ROOT/'ai-game.py');game=importlib.util.module_from_spec(s);s.loader.exec_module(game)
class PopupTests(unittest.TestCase):
 def test_finds_visible_x_and_ignores_empty_screen(self):
  # Synthetic fixture keeps game screenshot crops out of the source kit.
  with tempfile.TemporaryDirectory() as td,patch.object(game,'ROOT',Path(td)):
   directory=Path(td)/'linux/ui';directory.mkdir(parents=True)
   template=Image.new('RGB',(20,20),(160,170,180));draw=ImageDraw.Draw(template)
   draw.line((3,3,16,16),fill=(10,20,30),width=3)
   draw.line((3,16,16,3),fill=(10,20,30),width=3)
   template.save(directory/'popup-close.png')
   screen=Image.new('RGB',(400,300),(42,76,23));self.assertIsNone(game.find_popup_close(screen))
   screen.paste(template,(123,81))
   self.assertEqual(game.find_popup_close(screen),(133,91))
if __name__=='__main__':unittest.main(verbosity=2)
