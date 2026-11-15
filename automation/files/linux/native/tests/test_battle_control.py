"""Battle adapter uses isolated normal UI methods and rejects stale commands."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
JAVA=r'''import java.util.*;import java.lang.reflect.*;import com.google.gson.*;
interface bv {record a()implements bv{} record f(int a)implements bv{} record e(int a,int b)implements bv{} record d(int a)implements bv{} record b(int a)implements bv{} record c()implements bv{}}
class Skill {String a="Pepper Breath";int b=5,c=123,e=7;float d=100;}
class Species {String a="Agumon";List<Skill> d=List.of(new Skill());}
class Fighter {Species a=new Species();int b=31001,c=31001,d=10,e=100,f=50,i=80,j=20;Set<Status> k=EnumSet.noneOf(Status.class);}
enum Status {SILENCE}
record Row(String a,String b,Object c,boolean d,Object e,int f,Object g,int h,int i){}
record Effect(int a,int b,int c,int d,List<Object> e,int f,int g){}
record Quantity(int a,int b){}
class Screen {Object ba=new Battle(),bn;}
class Battle {
 List<List<Fighter>> H=new ArrayList<>();int[] I=new int[6];boolean[] K={true,false,false,false,false,false};List<Integer> ay=List.of(0);int aC=1;boolean aB=true;
 List<Row> N=new ArrayList<>();boolean bs=true,br=false,bB=false,bD=false,bK=false,bt=false,bu=false,bw=false,noMutation=false,changeActor=false;float aY=0;Object bc=null,bC=null;Queue<Object>M=new ArrayDeque<>();int bx=0,bA=0;
 Map<Integer,Effect> by=Map.of(43,new Effect(43,50,0,0,List.of(),0,0),70,new Effect(70,0,0,0,List.of(),20,0));List<Quantity> bz=List.of(new Quantity(43,3),new Quantity(70,1));List<String> calls=new ArrayList<>();
 Battle(){for(int n=0;n<6;n++)H.add(new ArrayList<>());H.get(0).add(new Fighter());Fighter reserve=new Fighter();reserve.b=31002;reserve.i=0;H.get(0).add(reserve);H.get(1).add(new Fighter());H.get(4).add(new Fighter());main();}
 void main(){bt=false;bu=false;bw=false;bx=0;N=new ArrayList<>(List.of(new Row("Attack","",new bv.a(),true,null,0,null,0,0),new Row("Pepper Breath","5 DS",new bv.f(0),true,null,0,null,0,0),new Row("Items","",null,true,null,0,null,3,0)));bA=0;bs=true;br=false;}
 void a(int delta){calls.add("select:"+delta);bA=Math.floorMod(bA+delta,N.size());if(changeActor)H.get(0).get(0).j--;}
 void a(int delta,boolean target){calls.add("target:"+delta);List<Integer> list=List.of(1,4);aC=list.get(Math.floorMod(list.indexOf(aC)+delta,list.size()));}
 void b(){calls.add("confirm");if(noMutation)return;Row row=N.get(bA);if(row.c()==null){bw=true;bx=0;N=new ArrayList<>(List.of(new Row("Power Charge","",null,true,null,0,null,4,43)));bA=0;}else{bs=false;br=true;}}
 void d(){calls.add("back");main();}
}
public class BattleCheck {
 static Method snapshot,choose,back;
 static JsonObject read(Screen s)throws Exception{return (JsonObject)snapshot.invoke(null,s);}
 static JsonObject command(JsonObject before,int index){JsonObject r=new JsonObject();r.add("expected_token",before.get("menu_token"));r.addProperty("option_index",index);return r;}
 static void rejects(Method m,Screen s,JsonObject request)throws Exception{try{m.invoke(null,s,request);throw new AssertionError("Invalid command accepted");}catch(InvocationTargetException expected){if(!(expected.getCause() instanceof IllegalArgumentException||expected.getCause() instanceof IllegalStateException))throw expected;}}
 public static void main(String[]args)throws Exception {
  Class<?> type=Class.forName("dw3.linux.BattleControl");snapshot=type.getMethod("snapshot",Object.class);choose=type.getMethod("choose",Object.class,JsonObject.class);back=type.getMethod("back",Object.class,JsonObject.class);
  Screen screen=new Screen();Battle battle=(Battle)screen.ba;JsonObject first=read(screen);
  if(!first.get("telemetry_complete").getAsBoolean()||!first.get("command_ready").getAsBoolean()||!first.get("menu").getAsString().equals("main"))throw new AssertionError(first);
  if(!first.equals(read(screen))||!battle.calls.isEmpty())throw new AssertionError("Snapshot mutated UI or token");
  if(first.getAsJsonObject("actor").get("ds").getAsInt()!=20||first.getAsJsonArray("party").size()!=2||first.getAsJsonArray("fighters").size()!=3)throw new AssertionError(first);
  JsonObject skill=first.getAsJsonArray("options").get(1).getAsJsonObject();if(!skill.get("kind").getAsString().equals("skill")||skill.get("ds_cost").getAsInt()!=5)throw new AssertionError(skill);
  JsonObject item=first.getAsJsonArray("items").get(0).getAsJsonObject();if(item.get("quantity").getAsInt()!=3||item.get("heal_hp").getAsInt()!=50||!item.get("revive_percent").isJsonNull())throw new AssertionError(item);
  JsonObject request=command(first,1);request.addProperty("target_group",4);JsonObject chosen=(JsonObject)choose.invoke(null,screen,request);
  if(!battle.calls.equals(List.of("target:1","select:1","confirm"))||chosen.getAsJsonObject("after").get("command_ready").getAsBoolean())throw new AssertionError(battle.calls);
  rejects(choose,screen,request);battle.main();JsonObject next=read(screen);if(next.get("menu_token").equals(first.get("menu_token")))throw new AssertionError("New turn reused old token");rejects(choose,screen,command(first,0));
  JsonObject bad=command(next,0);bad.addProperty("target_group",5);rejects(choose,screen,bad);
  JsonObject beforeChange=read(screen);battle.H.get(0).get(0).j--;rejects(choose,screen,command(beforeChange,0));
  beforeChange=read(screen);battle.H.get(0).get(0).k.add(Status.SILENCE);rejects(choose,screen,command(beforeChange,0));
  battle.calls.clear();battle.changeActor=true;rejects(choose,screen,command(read(screen),1));if(battle.calls.contains("confirm"))throw new AssertionError("Actor changed during selection");battle.changeActor=false;
  for(String flag:List.of("br","bB","bD","bK")){Field f=Battle.class.getDeclaredField(flag);f.setBoolean(battle,true);if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Unsafe readiness: "+flag);f.setBoolean(battle,false);}
  battle.aY=1;if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Intro ready");battle.aY=0;
  battle.bC=new Object();if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Pending result packet ready");battle.bC=null;
  battle.bc=new Object();if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Animation ready");battle.bc=null;battle.M.add(new Object());if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Queue ready");battle.M.clear();
  battle.main();battle.N.set(1,new Row("Unavailable","",new bv.f(0),false,null,0,null,0,0));battle.calls.clear();rejects(choose,screen,command(read(screen),1));if(!battle.calls.isEmpty())throw new AssertionError("Disabled row caused UI input");
  battle.main();JsonObject generation=read(screen);battle.N.set(0,new Row("Attack","",new bv.a(),true,null,0,null,0,0));rejects(choose,screen,command(generation,0));
  battle.main();JsonObject oldBattle=read(screen);screen.ba=new Battle();rejects(choose,screen,command(oldBattle,0));screen.ba=battle;
  battle.main();battle.H.get(0).get(0).j=2;battle.calls.clear();rejects(choose,screen,command(read(screen),1));if(!battle.calls.isEmpty())throw new AssertionError("Unaffordable skill caused input");battle.H.get(0).get(0).j=20;
  battle.main();battle.noMutation=true;JsonObject noop=read(screen);choose.invoke(null,screen,command(noop,0));rejects(choose,screen,command(noop,0));battle.noMutation=false;
  battle.main();choose.invoke(null,screen,command(read(screen),2));JsonObject menu=read(screen);if(!menu.get("menu").getAsString().equals("items")||menu.getAsJsonArray("options").get(0).getAsJsonObject().get("item_id").getAsInt()!=43)throw new AssertionError(menu);
  back.invoke(null,screen,command(menu,0));if(!read(screen).get("menu").getAsString().equals("main"))throw new AssertionError("Normal back failed");rejects(back,screen,command(read(screen),0));
  battle.bw=true;battle.bx=43;battle.N=new ArrayList<>(List.of(new Row("Reserve","",new bv.e(43,1),true,null,0,null,0,0)));
  JsonObject target=read(screen).getAsJsonArray("options").get(0).getAsJsonObject();if(!target.get("kind").getAsString().equals("item_target")||target.get("target_slot").getAsInt()!=1)throw new AssertionError(target);
  screen.bn=new Object();if(read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Transition ready");screen.bn=null;screen.ba=new Object();if(read(screen).get("telemetry_complete").getAsBoolean()||read(screen).get("command_ready").getAsBoolean())throw new AssertionError("Unknown state trusted");
  System.out.println("Battle snapshot purity, normal UI commands and stale-action guards verified.");
 }
}'''
class BattleControlTests(unittest.TestCase):
 def test_snapshot_normal_actions_and_stale_guards(self):
  for original_commands in (False,True):
   with self.subTest(original_commands=original_commands),tempfile.TemporaryDirectory(prefix='dw3-battle-control-') as directory:
    source_text=JAVA
    if original_commands:source_text='\n'.join(line for line in source_text.splitlines() if not line.startswith('interface bv '))
    java=Path(directory)/'BattleCheck.java';java.write_text(source_text)
    cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
    if original_commands:cp+=f':{ROOT}/app/client.jar'
    source=ROOT/'linux/native/src/dw3/linux/BattleControl.java';sources=[str(source)] if source.exists() else []
    subprocess.run(['javac','--release','17','-cp',cp,'-d',directory,*sources,str(java)],check=True)
    result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',directory+':'+cp,'BattleCheck'],capture_output=True,text=True,timeout=15)
    self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Battle snapshot purity',result.stdout)
if __name__=='__main__':unittest.main()
