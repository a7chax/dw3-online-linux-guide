from pathlib import Path
import subprocess,tempfile,unittest

ROOT=Path(__file__).resolve().parents[3]
SOURCE=r'''import java.util.*;import com.google.gson.*;import dw3.linux.SuppliesControl;
public class SuppliesCheck {
 enum Kind {KEY,USE,WEAPON,ARMOUR,ACCESSORY} enum Power {NONE,BITS,EXP}
 static class Rule {Kind a=Kind.USE;int b=100,c=25,d;Power e=Power.NONE;int f;Rule(int hp,int ds){d=hp;f=ds;}}
 static class Rules {Map<Integer,Object>a=new HashMap<>(Map.of(43,new Rule(500,0),463,new Rule(0,1000)));}
 static class Game {Object O=new Rules();Map<String,String[]>af=new HashMap<>();String[]N=new String[500];Game(){String[]names=new String[500];names[43]="Power Charge";names[463]="Mind Charge";af.put("items",names);}}
 static class Stats {int a=100,b=80;}
 static class Member {int a=7,e=60,f=10;Stats g=new Stats();}
 static class Party {List<Object>d=new ArrayList<>(List.of(new Member()));}
 static class Row {int a,b;Row(int id,int amount){a=id;b=amount;}}
 static class Context {Object a;Object a(){return a;}}
 static class Bag {int t=-1,u,v,w,x,y,aj;boolean k,z,K,A;Object S;StringBuilder j=new StringBuilder();Context ac=new Context();static int l;static boolean m;
  private List<?>a(List<?>rows){return rows;}private List<?>a(List<?>rows,List<Long>times){return rows;}
  void b(int op,int item){throw new AssertionError("UI action called by plan");}}
 static class Wallet {int a=1000,b;}
 static class Offer {int a=5;List<Object>b=new ArrayList<>(List.of(new Row(43,100),new Row(463,200)));}
 static class Shop {Offer c=new Offer();boolean f,j,m,o;int g,h,i=1,n=-1,p;float q=3;}
 static class Screen {Game M=new Game();Bag by=new Bag();Party bu=new Party();List<Object>bv=new ArrayList<>(List.of(new Row(43,3),new Row(463,2)));Wallet bt=new Wallet();Object bA,ba,bn,aC,aX,aZ,aM,bz;}
 static String key(JsonObject p){return p.get("key").isJsonNull()?null:p.get("key").getAsString();}
 static void eq(Object a,Object b){if(!Objects.equals(a,b))throw new AssertionError(a+" != "+b);}
 public static void main(String[]args)throws Exception {
  Screen s=new Screen();JsonObject snap=SuppliesControl.snapshot(s);
  if(!snap.get("rules_loaded").getAsBoolean())throw new AssertionError("Loaded rules missing");
  if(!snap.get("telemetry_complete").getAsBoolean())throw new AssertionError(snap);
  JsonObject hp=snap.getAsJsonArray("inventory").get(0).getAsJsonObject();eq(hp.get("heal_hp").getAsInt(),500);eq(hp.get("quantity").getAsInt(),3);eq(hp.get("name").getAsString(),"Power Charge");
  eq(snap.getAsJsonArray("party").get(0).getAsJsonObject().get("ds").getAsInt(),10);
  eq(key(SuppliesControl.planUse(s,43,0)),"i");s.by.t=1;
  eq(key(SuppliesControl.planUse(s,463,0)),"right");eq(key(SuppliesControl.planUse(s,43,0)),"space");
  if(SuppliesControl.planUse(s,43,0).get("submit").getAsBoolean())throw new AssertionError("Opening picker is not using");
  if(!SuppliesControl.snapshot(s).get("inventory_open").getAsBoolean())throw new AssertionError("Open inventory missing");
  s.by.v=43;eq(key(SuppliesControl.planUse(s,43,0)),"space");
  if(!SuppliesControl.planUse(s,43,0).get("submit").getAsBoolean())throw new AssertionError("Final use omitted");
  s.bu.d.get(0).getClass();((Member)s.bu.d.get(0)).e=0;
  eq(key(SuppliesControl.planUse(s,43,0)),null);((Member)s.bu.d.get(0)).e=60;s.by.v=0;
  eq(key(SuppliesControl.planClose(s)),"i");s.bA=new Shop();Shop shop=(Shop)s.bA;
  JsonObject offer=SuppliesControl.snapshot(s).getAsJsonObject("shop");String token=offer.get("offer_token").getAsString();
  eq(key(SuppliesControl.planBuy(s,43,1,token)),"space");
  if(!SuppliesControl.planBuy(s,43,1,token).get("submit").getAsBoolean())throw new AssertionError("Final buy omitted");
  eq(offer.getAsJsonArray("offers").get(0).getAsJsonObject().get("currency").getAsString(),"bits");
  eq(key(SuppliesControl.planBuy(s,463,1,token)),"down");
  eq(key(SuppliesControl.planBuy(s,43,2,token)),"right");eq(key(SuppliesControl.planBuy(s,43,1,"old")),null);
  eq(key(SuppliesControl.planBuy(s,43,6,token)),null);shop.j=true;eq(key(SuppliesControl.planBuy(s,43,1,token)),null);shop.j=false;
  s.bt.a=50;eq(key(SuppliesControl.planBuy(s,43,1,token)),null);s.bt.a=1000;
  eq(key(SuppliesControl.planClose(s)),"x");
  String before=SuppliesControl.snapshot(s).get("state_token").getAsString();s.bt.a=999;
  if(before.equals(SuppliesControl.snapshot(s).get("state_token").getAsString()))throw new AssertionError("Wallet not bound");
  ((Row)shop.c.b.get(0)).b=101;
  if(token.equals(SuppliesControl.snapshot(s).getAsJsonObject("shop").get("offer_token").getAsString()))throw new AssertionError("Offer price not bound");
  s.bt.a=50000;((Row)shop.c.b.get(0)).b=10000;
  token=SuppliesControl.snapshot(s).getAsJsonObject("shop").get("offer_token").getAsString();
  if(SuppliesControl.planBuy(s,43,1,token).get("submit").getAsBoolean())throw new AssertionError("First expensive confirmation counted as buy");
  shop.n=43;shop.p=1;shop.q=0;
  if(!SuppliesControl.planBuy(s,43,1,token).get("submit").getAsBoolean())throw new AssertionError("Second expensive confirmation omitted");
  s.bA=null;s.by.t=-1;
  String stable=SuppliesControl.snapshot(s).get("state_token").getAsString();
  for(String field:new String[]{"bn","aC"}) {
   Screen.class.getDeclaredField(field).set(s,new Object());
   JsonObject blocked=SuppliesControl.snapshot(s);
   if(!blocked.get("world_modal").getAsBoolean() || stable.equals(blocked.get("state_token").getAsString()))throw new AssertionError("Transition not bound: "+field);
   eq(key(SuppliesControl.planUse(s,43,0)),null);eq(key(SuppliesControl.planInspect(s)),null);eq(key(SuppliesControl.planClose(s)),null);
   Screen.class.getDeclaredField(field).set(s,null);
  }
  s.M.O=null;
  if(SuppliesControl.snapshot(s).get("rules_loaded").getAsBoolean())throw new AssertionError("Unknown rules invented");
  eq(key(SuppliesControl.planInspect(s)),"i");s.by.t=1;eq(key(SuppliesControl.planInspect(s)),null);
  if(SuppliesControl.snapshot(s).get("telemetry_complete").getAsBoolean())throw new AssertionError("Missing rules accepted");
  if(SuppliesControl.snapshot(new Object()).get("telemetry_complete").getAsBoolean())throw new AssertionError("Missing state accepted");
  System.out.println("Pure supplies snapshots and normal input plans verified");
 }
}'''

class SuppliesTests(unittest.TestCase):
    def test_pure_inventory_shop_and_normal_input_plans(self):
        with tempfile.TemporaryDirectory(prefix='dw3-supplies-') as directory:
            source=Path(directory)/'SuppliesCheck.java';source.write_text(SOURCE)
            cp=str(ROOT/'app/gson-2.11.0.jar')
            subprocess.run(['javac','--release','17','-cp',cp,'-d',directory,
                str(ROOT/'linux/native/src/dw3/linux/SuppliesControl.java'),str(source)],check=True)
            result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',directory+':'+cp,'SuppliesCheck'],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Pure supplies',result.stdout)

if __name__=='__main__':unittest.main()
