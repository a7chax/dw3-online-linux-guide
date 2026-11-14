#!/usr/bin/env python3
"""Party health reads only the full server snapshot, never active battle widgets."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SOURCE='''import java.lang.reflect.*;import java.util.*;import com.google.gson.*;
public class PartyCheck {
 static class Stats {private int a=100;int a(){throw new AssertionError("Getter called");}}
 static class Member {private int a,e;private Stats g=new Stats();Member(int id,int hp){a=id;e=hp;}int e(){throw new AssertionError("HP getter called");}}
 static class Party {private List<Object> d;Party(Object...members){d=Arrays.asList(members);}List<Object> d(){throw new AssertionError("Party getter called");}}
 static class Wallet {private int a=1250,b=15;}
 static class Game {private Map<Integer,String> x=new HashMap<>(Map.of(7,"My partner"));private Map<Integer,String> H=new HashMap<>(Map.of(8,"Reserve Digimon"));}
 enum InnState {OFFER,WAITING,ERROR,RESTING,CLOSED}
 static class Offer {private int a=4,c=3,d=300;}
 static class Inn {private InnState d=InnState.OFFER;private int e=0;private Offer c=new Offer();void b(boolean confirm){throw new AssertionError("Inn submitted by polling");}}
 static class Npc {private String a;private int b=93,c=345,d=308,f=40,g;Npc(String sprite,int interaction){a=sprite;g=interaction;}}
 static class ActualInn {private Object d;private int e=0;private Offer c=new Offer();ActualInn(Object state){d=state;}}
 static class Screen {private float ax=357.35846f,ay=338.4521f;private int az=5;private Object bu,bt=new Wallet(),M=new Game(),bz,aC;private List<Object> Y=List.of(new Npc("p039tail",7),new Npc("p074jiji",20),new Npc("p039tail",-1));boolean C(){return bz==null;}}
 static class Missing {}
 static Method party,wallet,inn;
 static JsonObject read(Method method,Object screen)throws Exception{return (JsonObject)method.invoke(null,screen);}
 public static void main(String[]args)throws Exception {
  Class<?> bridge=Class.forName("dw3.linux.ControlBridge");
  try{party=bridge.getDeclaredMethod("partySnapshot",Object.class);wallet=bridge.getDeclaredMethod("walletSnapshot",Object.class);inn=bridge.getDeclaredMethod("innSnapshot",Object.class);}catch(NoSuchMethodException e){throw new AssertionError("Missing full-party telemetry",e);}
  party.setAccessible(true);wallet.setAccessible(true);inn.setAccessible(true);Screen screen=new Screen();
  screen.bu=new Party(new Member(7,70),new Member(8,0),new Member(9,25));
  JsonObject all=read(party,screen);if(!all.get("telemetry_complete").getAsBoolean()||!all.get("any_fainted").getAsBoolean()||all.get("count").getAsInt()!=3)throw new AssertionError(all);
  JsonArray rows=all.getAsJsonArray("members");if(rows.size()!=3||rows.get(1).getAsJsonObject().get("hp").getAsInt()!=0||!rows.get(1).getAsJsonObject().get("fainted").getAsBoolean())throw new AssertionError("Reserve fainting omitted");
  if(!rows.get(0).getAsJsonObject().get("name").getAsString().equals("My partner")||!rows.get(1).getAsJsonObject().get("name").getAsString().equals("Reserve Digimon")||!rows.get(2).getAsJsonObject().get("name").isJsonNull())throw new AssertionError("Names invented or ignored");
  if(rows.get(2).getAsJsonObject().get("slot").getAsInt()!=2||rows.get(0).getAsJsonObject().get("max_hp").getAsInt()!=100)throw new AssertionError(rows);
  if(!all.equals(read(party,screen)))throw new AssertionError("Status mutated party");
  ((Member)((Party)screen.bu).d.get(1)).e=100;if(read(party,screen).get("any_fainted").getAsBoolean())throw new AssertionError("Restored HP stale");
  screen.bu=new Party(new Member(7,0),new Missing());JsonObject partial=read(party,screen);
  if(partial.get("telemetry_complete").getAsBoolean()||!partial.get("any_fainted").isJsonNull()||partial.getAsJsonArray("members").size()!=2)throw new AssertionError("Partial party declared complete");
  Member invalid=new Member(7,-1);screen.bu=new Party(invalid);if(read(party,screen).get("telemetry_complete").getAsBoolean())throw new AssertionError("Invalid HP accepted");
  screen.bu=new Party();JsonObject empty=read(party,screen);if(empty.get("count").getAsInt()!=0||empty.get("any_fainted").getAsBoolean())throw new AssertionError("Empty party treated as fainted");
  screen.bu=new Party(new Member(7,0),new Member(8,0));if(!read(party,screen).get("any_fainted").getAsBoolean())throw new AssertionError("All-fainted party missed");
  Member over=new Member(7,101);screen.bu=new Party(over);if(read(party,screen).get("telemetry_complete").getAsBoolean())throw new AssertionError("HP above maximum accepted");
  screen.bu=null;if(read(party,screen).get("telemetry_complete").getAsBoolean())throw new AssertionError("No party declared known");
  if(read(party,new Missing()).get("telemetry_complete").getAsBoolean())throw new AssertionError("Missing party fields crashed or declared known");
  JsonObject money=read(wallet,screen);if(!money.get("telemetry_complete").getAsBoolean()||money.get("bits").getAsInt()!=1250||money.get("cash").getAsInt()!=15)throw new AssertionError(money);
  if(read(wallet,new Missing()).get("telemetry_complete").getAsBoolean())throw new AssertionError("Unknown wallet invented");
  if(read(inn,screen).get("active").getAsBoolean())throw new AssertionError("Absent inn active");
  Method nearby=bridge.getDeclaredMethod("nearbyInnsSnapshot",Object.class,String.class);nearby.setAccessible(true);
  JsonObject npcs=(JsonObject)nearby.invoke(null,screen,"s235");
  if(!npcs.get("telemetry_complete").getAsBoolean()||npcs.getAsJsonArray("npcs").size()!=1)throw new AssertionError(npcs);
  JsonObject npc=npcs.getAsJsonArray("npcs").get(0).getAsJsonObject();
  if(npc.get("logical_id").getAsInt()!=20||npc.get("interaction_id").getAsInt()!=7||!npc.get("source").getAsString().equals("bundled_inn_catalog")||npc.get("entity_id").getAsInt()!=93||npc.get("x").getAsInt()!=345||!npc.get("map").getAsString().equals("s235"))throw new AssertionError(npc);
  if(!npc.get("can_interact").getAsBoolean()||npc.get("interaction_radius").getAsInt()!=40)throw new AssertionError("Large-radius >24px inn interaction omitted");
  Npc liveNpc=(Npc)screen.Y.get(0);
  for(float[] location:new float[][]{{357.35846f,338.4521f},{345.9f,308.9f},{290.5f,310.1f},{-0.5f,-0.5f}})for(int radius:List.of(0,16,24,32,48)) {
   screen.ax=location[0];screen.ay=location[1];liveNpc.f=radius;
   for(int facing=0;facing<8;facing++) {
    screen.az=facing;JsonObject measured=((JsonObject)nearby.invoke(null,screen,"s360")).getAsJsonArray("npcs").get(0).getAsJsonObject();
    boolean exact=bF.a((int)Math.floor(screen.ax),(int)Math.floor(screen.ay),facing,liveNpc.c,liveNpc.d,radius);
    if(measured.get("can_interact").getAsBoolean()!=exact)throw new AssertionError("Interaction predicate differs from original");
    JsonArray facings=measured.getAsJsonArray("interaction_facings");
    for(int candidate=0;candidate<8;candidate++)if(facings.contains(new JsonPrimitive(candidate))!=bF.a((int)Math.floor(screen.ax),(int)Math.floor(screen.ay),candidate,liveNpc.c,liveNpc.d,radius))throw new AssertionError("Interaction facing list differs from original");
   }
  }
  screen.ax=357.35846f;screen.ay=338.4521f;screen.az=5;liveNpc.f=40;
  for(String ambiguousMap:List.of("s470","s471")) {
   JsonObject ambiguous=(JsonObject)nearby.invoke(null,screen,ambiguousMap);
   if(!ambiguous.get("telemetry_complete").getAsBoolean()||ambiguous.getAsJsonArray("npcs").size()!=1)throw new AssertionError("Ambiguous inn candidate omitted");
   JsonObject candidate=ambiguous.getAsJsonArray("npcs").get(0).getAsJsonObject();
   if(!candidate.get("logical_id").isJsonNull()||!candidate.get("inn_candidate").getAsBoolean()||!candidate.get("source").getAsString().equals("inn_sprite_candidate_requires_offer")||candidate.get("interaction_id").getAsInt()!=7)throw new AssertionError("Candidate presented as verified innkeeper: "+candidate);
  }
  if(((JsonObject)nearby.invoke(null,screen,"unknown")).getAsJsonArray("npcs").size()!=0)throw new AssertionError("Unknown map inn invented");
  screen.bz=new Inn();JsonObject offer=read(inn,screen);
  if(!offer.get("active").getAsBoolean()||!offer.get("can_confirm").getAsBoolean()||offer.get("cost_bits").getAsInt()!=300||!offer.get("state").getAsString().equals("offer"))throw new AssertionError(offer);
  Method ready=bridge.getDeclaredMethod("movementReady",Object.class);ready.setAccessible(true);if((Boolean)ready.invoke(null,screen))throw new AssertionError("Inn allowed movement");
  if(!offer.equals(read(inn,screen)))throw new AssertionError("Inn polling mutated offer");
  ((Wallet)screen.bt).a=200;if(read(inn,screen).get("can_confirm").getAsBoolean())throw new AssertionError("Unaffordable inn confirmed");((Wallet)screen.bt).a=1250;
  ((Inn)screen.bz).e=1;if(read(inn,screen).get("can_confirm").getAsBoolean())throw new AssertionError("Cancel option accepted as stay");((Inn)screen.bz).e=0;
  String[] states={"offer","submitted","rejected","resting","closed"};int index=0;
  for(InnState state:InnState.values()){((Inn)screen.bz).d=state;JsonObject row=read(inn,screen);if(!row.get("state").getAsString().equals(states[index++])||state!=InnState.OFFER&&row.get("can_confirm").getAsBoolean())throw new AssertionError(row);}
  Class<?> actualEnum=Class.forName("U$a");Field actualOffer=actualEnum.getDeclaredField("a");actualOffer.setAccessible(true);Object originalState=actualOffer.get(null);
  if(((Enum<?>)originalState).ordinal()!=0)throw new AssertionError("Original offer ordinal changed");
  screen.bz=new ActualInn(originalState);JsonObject actual=read(inn,screen);if(!actual.get("can_confirm").getAsBoolean()||!actual.get("state").getAsString().equals("offer"))throw new AssertionError("Original obfuscated enum not read correctly: "+actual);
  screen.bz=new Missing();JsonObject unknownInn=read(inn,screen);if(unknownInn.get("telemetry_complete").getAsBoolean()||unknownInn.get("can_confirm").getAsBoolean())throw new AssertionError("Unknown inn eligible");
  System.out.println("Full party/reserve HP, purity, missing fields and currency verified.");
 }
}'''
class PartyStateTests(unittest.TestCase):
 def test_full_party_snapshot_is_pure_and_includes_reserves(self):
  with tempfile.TemporaryDirectory(prefix='dw3-party-') as directory:
   source=Path(directory)/'PartyCheck.java';source.write_text(SOURCE)
   cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar:{ROOT}/app/client.jar'
   subprocess.run(['javac','--release','17','-cp',cp,'-d',directory,str(ROOT/'linux/native/src/dw3/linux/ControlBridge.java'),str(source)],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',directory+':'+cp,'PartyCheck'],capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Full party/reserve HP',result.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
