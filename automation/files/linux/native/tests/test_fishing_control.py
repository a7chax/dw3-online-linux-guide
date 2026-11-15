"""Fishing snapshots read original fields without running game actions."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
JAVA=r'''import com.google.gson.*;import dw3.linux.FishingControl;
public class FishingCheck {
 static class Menu {boolean open;boolean a(){return open;}boolean g(){return open;}}
 static class Screen {int ap=255,az=4;float aq=-1,ar=-1,aV=20,as=0,aQ=0,ac=-1,G=-1;boolean at,be;
  Object ag,ba,bn,aX,aZ,aM,aC,bz,bA,bB,bC,bO,cp,cq,ch,cF,cj,ck,cv,cz,cA,cB,cD,cE,cl,co,cm,cn,cx,bD,bE,ai;int bY=-1;
  Menu by=new Menu(),bs=new Menu(),cG=new Menu();
  boolean C(){return aX==null&&aZ==null&&ba==null&&bn==null&&aM==null&&aQ<=0&&bz==null&&bA==null&&bB==null&&bC==null&&bO==null&&cp==null&&cq==null;}
  void p(){throw new AssertionError("Snapshot sent Space");}}
 static class FloatGame {int d=0,e=4;float h=91;boolean f;int a(){return (int)(h-91);}boolean b(){return d!=255&&!f&&h>=91;}}
 static void yes(JsonObject s,String key){if(!s.get(key).getAsBoolean())throw new AssertionError(key+": "+s);}
 static void no(JsonObject s,String key){if(s.get(key).getAsBoolean())throw new AssertionError(key+": "+s);}
 public static void main(String[]args)throws Exception {
  Screen s=new Screen();JsonObject initial=FishingControl.snapshot(s);yes(initial,"telemetry_complete");no(initial,"at_spot");no(initial,"can_cast");
  if(!initial.get("rod_available").isJsonNull())throw new AssertionError("Rod ownership invented");
  s.ap=4;s.aq=1;JsonObject cast=FishingControl.snapshot(s);yes(cast,"at_spot");yes(cast,"can_cast");
  if(!FishingControl.plan(s,"cast",cast.get("state_token").getAsString()).get("key").getAsString().equals("space"))throw new AssertionError("Ready cast omitted");
  if(!FishingControl.plan(s,"cast","stale").get("key").isJsonNull())throw new AssertionError("Stale cast accepted");
  if(!FishingControl.plan(s,"unknown",cast.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Unknown action accepted");
  if(!FishingControl.plan(s,null,cast.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Null action accepted");
  if(!cast.equals(FishingControl.snapshot(s)))throw new AssertionError("Snapshot not stable");
  s.aV+=.1f;s.aq+=1;if(!cast.get("state_token").equals(FishingControl.snapshot(s).get("state_token")))throw new AssertionError("Frame drift invalidated generation");
  s.az=0;no(FishingControl.snapshot(s),"can_cast");s.az=4;
  s.aV=s.as+.5f;no(FishingControl.snapshot(s),"can_cast");s.aV=20;
  s.ar=1;no(FishingControl.snapshot(s),"can_cast");s.ar=-1;
  s.aq=-1;no(FishingControl.snapshot(s),"can_cast");s.aq=1;
  FloatGame game=new FloatGame();s.ag=game;JsonObject reel=FishingControl.snapshot(s);yes(reel,"active");yes(reel,"can_reel");no(reel,"can_cast");
  String token=reel.get("state_token").getAsString();game.h+=1;
  if(!token.equals(FishingControl.snapshot(s).get("state_token").getAsString()))throw new AssertionError("Reel frame drift invalidated generation");
  game.h=90;no(FishingControl.snapshot(s),"can_reel");game.h=91;game.f=true;no(FishingControl.snapshot(s),"can_reel");game.f=false;
  boolean found=false;for(int n=0;n<192;n++){game.h=91+n;JsonObject snap=FishingControl.snapshot(s);JsonObject plan=FishingControl.plan(s,"reel",snap.get("state_token").getAsString());if(snap.get("reel_good").getAsBoolean()){found=true;if(plan.get("key").isJsonNull())throw new AssertionError("Good reel omitted");}else if(!plan.get("key").isJsonNull())throw new AssertionError("Bad timing accepted");}if(!found)throw new AssertionError("No original good reel window");
  game.h=91;JsonObject difficult=FishingControl.snapshot(s);no(difficult,"reel_good");
  String difficultToken=difficult.get("state_token").getAsString();
  if(!FishingControl.plan(s,"reel",difficultToken).get("key").isJsonNull())throw new AssertionError("Strict reel accepted wrong window");
  if(FishingControl.plan(s,"reel_attempt",difficultToken).get("key").isJsonNull())throw new AssertionError("Best-effort normal Space omitted");
  if(!FishingControl.plan(s,"reel_attempt","stale").get("key").isJsonNull())throw new AssertionError("Best-effort accepted stale cast");
  game.f=true;JsonObject submitted=FishingControl.snapshot(s);
  if(!FishingControl.plan(s,"reel_attempt",submitted.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Submitted cast accepted");game.f=false;
  game.d=8;JsonObject exhausted=FishingControl.snapshot(s);
  if(!FishingControl.plan(s,"reel",exhausted.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Exhaustion counted as good reel");
  if(FishingControl.plan(s,"exhausted",exhausted.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Exhaustion ack omitted");
  game.d=8;yes(FishingControl.snapshot(s),"exhausted");no(FishingControl.snapshot(s),"reel_good");game.d=255;no(FishingControl.snapshot(s),"can_reel");game.d=0;
  for(String field:new String[]{"ba","bn","aX","aZ","aM","aC","bA","ch"}) {
   String previous=FishingControl.snapshot(s).get("state_token").getAsString();Screen.class.getDeclaredField(field).set(s,new Object());JsonObject blocked=FishingControl.snapshot(s);no(blocked,"can_reel");no(blocked,"can_cast");if(!FishingControl.plan(s,"reel",previous).get("key").isJsonNull())throw new AssertionError("Modal input accepted");if(!FishingControl.plan(s,"reel_attempt",blocked.get("state_token").getAsString()).get("key").isJsonNull())throw new AssertionError("Best-effort modal input accepted");Screen.class.getDeclaredField(field).set(s,null);
  }
  s.by.open=true;no(FishingControl.snapshot(s),"can_reel");s.by.open=false;s.bs.open=true;no(FishingControl.snapshot(s),"can_reel");s.bs.open=false;s.cG.open=true;no(FishingControl.snapshot(s),"can_reel");s.cG.open=false;
  String before=FishingControl.snapshot(s).get("state_token").getAsString();s.ag=new FloatGame();if(before.equals(FishingControl.snapshot(s).get("state_token").getAsString()))throw new AssertionError("New cast reused token");
  s.ag=new Object();JsonObject missing=FishingControl.snapshot(s);no(missing,"telemetry_complete");no(missing,"can_cast");no(missing,"can_reel");
  if(!FishingControl.plan(s,"reel_attempt","unknown").get("key").isJsonNull())throw new AssertionError("Best-effort missing telemetry accepted");
  missing=FishingControl.snapshot(new Object());no(missing,"telemetry_complete");no(missing,"can_cast");no(missing,"can_reel");
  System.out.println("Pure fishing snapshots, exact timing and fail-closed readiness verified");
 }
}'''
class FishingControlTests(unittest.TestCase):
 def test_pure_original_fishing_readiness_and_timing(self):
  with tempfile.TemporaryDirectory(prefix='dw3-fishing-control-') as directory:
   source=Path(directory)/'FishingCheck.java';source.write_text(JAVA)
   cp=str(ROOT/'app/gson-2.11.0.jar')+':'+str(ROOT/'app/client.jar')
   subprocess.run(['javac','--release','17','-cp',cp,'-d',directory,str(ROOT/'linux/native/src/dw3/linux/FishingControl.java'),str(source)],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',directory+':'+cp,'FishingCheck'],capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Pure fishing',result.stdout)
if __name__=='__main__':unittest.main()
