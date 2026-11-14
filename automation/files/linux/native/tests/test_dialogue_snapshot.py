#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SOURCE='''import java.lang.reflect.*;import java.util.*;
public class DialogueCheck {
 public static class Typewriter {private List<String> a=List.of("first","last");private int c=0;private int d=10;boolean b(){return false;}}
 public static class Bubble {private Typewriter e=new Typewriter();boolean a(){throw new AssertionError("Status invoked mutating dialogue advance");}}
 public static class Packet {public int a(){return 7;}public int b(){return 6;}public int c(){return 806;}}
 public static class Screen {private Bubble aM=new Bubble();private Packet aO=new Packet();private String a(Packet p){return "First[pause][clear]Last";}}
 public static void main(String[] args)throws Exception {
  Class<?> type=Class.forName("dw3.linux.ControlBridge");Method read;
  try{read=type.getDeclaredMethod("dialogueSnapshot",Object.class);}catch(NoSuchMethodException e){throw new AssertionError("No verified pure dialogue snapshot",e);}
  read.setAccessible(true);Screen screen=new Screen();
  String first=read.invoke(null,screen).toString(),second=read.invoke(null,screen).toString();
  if(!first.equals(second))throw new AssertionError("Repeated status changed dialogue");
  if(!first.contains("\\\"can_advance\\\":true")||!first.contains("\\\"page_index\\\":0")||!first.contains("\\\"ready_to_close\\\":false"))throw new AssertionError(first);
  System.out.println("Pure dialogue snapshot verified.");
 }
}'''
class DialogueTests(unittest.TestCase):
 def test_status_does_not_reveal_or_advance_dialogue(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'DialogueCheck.java';source.write_text(SOURCE)
   cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
   subprocess.run(['javac','--release','17','-cp',cp,'-d',td,str(source)],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',td+':'+cp,'DialogueCheck'],capture_output=True,text=True,timeout=8)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('Pure dialogue snapshot verified',result.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
