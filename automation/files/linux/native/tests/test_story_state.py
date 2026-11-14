#!/usr/bin/env python3
"""Pure story telemetry uses isolated objects and never advances dialogue."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = '''import java.lang.reflect.*;import java.util.*;import com.google.gson.*;
public class StoryCheck {
 public static class Writer {
  boolean typing=true;
  boolean b(){return typing;}
  boolean e(){throw new AssertionError("Mutating typewriter advance was called");}
 }
 public static class Bubble {
  private Writer e=new Writer();
  boolean a(){throw new AssertionError("Mutating bubble advance was called");}
 }
 public static class Slot {private Bubble bubble=new Bubble();public Bubble a(){return bubble;}}
 public static class Story {
  private int v=0,w=0;private boolean x=false,t=false;private Object[] p={new Slot(),new Slot()};
  int f(){throw new AssertionError("Choice submitted by status");}
  void l(){throw new AssertionError("Story advanced by status");}
 }
 public static class GPS {private Object K=null;}
 public static class Result {private boolean a=true;}
 public static class Battle {
  private boolean bD=false,bK=false,aw=false;private Result bC=null;
  void b(){throw new AssertionError("Battle status submitted an action");}
 }
 public static class Screen {private Object aX=new Story();private Object aC=null,ba=null,bn=null;private GPS cG=new GPS();boolean C(){return true;}}
 public static class BrokenStory {private int v=2;}
 public static class MissingScreen {}
 public static void main(String[] args)throws Exception {
  Class<?> bridge=Class.forName("dw3.linux.ControlBridge");Method snapshot;
  try{snapshot=bridge.getDeclaredMethod("storySnapshot",Object.class);}
  catch(NoSuchMethodException error){throw new AssertionError("Missing pure story snapshot",error);}
  snapshot.setAccessible(true);Screen screen=new Screen();Story story=(Story)screen.aX;
  JsonObject first=(JsonObject)snapshot.invoke(null,screen);
  if(!first.get("active").getAsBoolean()||!first.get("typing").getAsBoolean()||first.get("can_advance").getAsBoolean())throw new AssertionError(first);
  if(!first.equals(snapshot.invoke(null,screen)))throw new AssertionError("Repeated polling changed story");
  ((Slot)story.p[0]).bubble.e.typing=false;
  if(((JsonObject)snapshot.invoke(null,screen)).get("can_advance").getAsBoolean())throw new AssertionError("Another active bubble is typing");
  ((Slot)story.p[1]).bubble.e.typing=false;
  JsonObject paused=(JsonObject)snapshot.invoke(null,screen);
  if(!paused.get("can_advance").getAsBoolean()||paused.get("awaiting_choice").getAsBoolean())throw new AssertionError(paused);
  story.v=2;story.w=1;JsonObject choice=(JsonObject)snapshot.invoke(null,screen);
  if(!choice.get("awaiting_choice").getAsBoolean()||choice.get("can_advance").getAsBoolean()||choice.get("choice_count").getAsInt()!=2||choice.get("selected_choice").getAsInt()!=1)throw new AssertionError(choice);
  story.x=true;JsonObject submitted=(JsonObject)snapshot.invoke(null,screen);
  if(submitted.get("awaiting_choice").getAsBoolean()||!submitted.get("submitted").getAsBoolean()||submitted.get("can_advance").getAsBoolean())throw new AssertionError(submitted);
  story.v=0;story.x=false;story.p=new Object[0];story.t=true;
  JsonObject finished=(JsonObject)snapshot.invoke(null,screen);
  if(finished.get("typing").getAsBoolean()||finished.get("can_advance").getAsBoolean()||!finished.get("script_complete").getAsBoolean())throw new AssertionError(finished);
  screen.aX=new BrokenStory();JsonObject broken=(JsonObject)snapshot.invoke(null,screen);
  if(!broken.get("active").getAsBoolean()||broken.get("can_advance").getAsBoolean()||broken.get("telemetry_complete").getAsBoolean())throw new AssertionError(broken);
  screen.aX=null;if(snapshot.invoke(null,screen)!=null)throw new AssertionError("Absent story reported active");
  if(snapshot.invoke(null,new MissingScreen())!=null)throw new AssertionError("Missing optional story field failed");
  Method ready=bridge.getDeclaredMethod("movementReady",Object.class);ready.setAccessible(true);
  if(!(Boolean)ready.invoke(null,screen))throw new AssertionError("World readiness unavailable");
  screen.aC=new Object();if((Boolean)ready.invoke(null,screen))throw new AssertionError("Transport was movement ready");
  if((Boolean)ready.invoke(null,new MissingScreen()))throw new AssertionError("Unknown readiness allowed movement");
  Method gps=bridge.getDeclaredMethod("gpsHasReply",Object.class);gps.setAccessible(true);
  if((Boolean)gps.invoke(null,screen))throw new AssertionError("Missing GPS reply reported present");
  screen.cG.K=new Object();if(!(Boolean)gps.invoke(null,screen))throw new AssertionError("Present GPS reply missed");
  if(gps.invoke(null,new MissingScreen())!=null)throw new AssertionError("Unknown GPS reply was invented");
  Method battleRead;
  try{battleRead=bridge.getDeclaredMethod("battleSnapshot",Object.class);}
  catch(NoSuchMethodException error){throw new AssertionError("Missing pure battle snapshot",error);}
  battleRead.setAccessible(true);
  if(battleRead.invoke(null,screen)!=null)throw new AssertionError("No battle should be absent");
  screen.bn=new Object();JsonObject transition=(JsonObject)battleRead.invoke(null,screen);
  if(!transition.get("active").getAsBoolean()||transition.get("can_advance").getAsBoolean())throw new AssertionError(transition);
  screen.bn=null;Battle battle=new Battle();screen.ba=battle;
  JsonObject fighting=(JsonObject)battleRead.invoke(null,screen);
  if(fighting.get("result_ready").getAsBoolean()||fighting.get("can_advance").getAsBoolean())throw new AssertionError("Combat Space would select an option");
  battle.bD=true;battle.bC=new Result();JsonObject victory=(JsonObject)battleRead.invoke(null,screen);
  if(!victory.get("can_advance").getAsBoolean()||!victory.get("result_ready").getAsBoolean()||!victory.get("result").getAsString().equals("victory"))throw new AssertionError(victory);
  if(!victory.equals(battleRead.invoke(null,screen)))throw new AssertionError("Polling changed battle");
  battle.bC.a=false;JsonObject defeat=(JsonObject)battleRead.invoke(null,screen);
  if(!defeat.get("result").getAsString().equals("defeat"))throw new AssertionError(defeat);
  battle.aw=true;JsonObject escape=(JsonObject)battleRead.invoke(null,screen);
  if(!escape.get("result").getAsString().equals("escape"))throw new AssertionError(escape);
  battle.bK=true;if(((JsonObject)battleRead.invoke(null,screen)).get("can_advance").getAsBoolean())throw new AssertionError("Duplicate result acknowledgement");
  screen.ba=new BrokenStory();JsonObject unknown=(JsonObject)battleRead.invoke(null,screen);
  if(unknown.get("telemetry_complete").getAsBoolean()||unknown.get("can_advance").getAsBoolean())throw new AssertionError(unknown);
  System.out.println("Pure story, choice, missing-field and movement readiness states verified.");
 }
}'''


class StoryStateTests(unittest.TestCase):
    def test_story_snapshot_is_pure_and_handles_all_readiness_states(self):
        with tempfile.TemporaryDirectory(prefix='dw3-story-') as directory:
            source = Path(directory) / 'StoryCheck.java'
            source.write_text(SOURCE)
            classpath = f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
            subprocess.run(['javac', '--release', '17', '-cp', classpath, '-d', directory,
                            str(ROOT / 'linux/native/src/dw3/linux/ControlBridge.java'), str(source)], check=True)
            result = subprocess.run([str(ROOT / 'linux/runtime/bin/java'), '-cp', directory + ':' + classpath,
                                     'StoryCheck'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Pure story, choice, missing-field', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
