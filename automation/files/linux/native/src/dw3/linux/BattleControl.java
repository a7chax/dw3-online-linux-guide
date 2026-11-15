package dw3.linux;

import com.google.gson.*;
import java.lang.reflect.*;
import java.util.*;

/** Read-only battle views plus guarded calls to the original normal menu UI. */
public final class BattleControl {
    private BattleControl() {}
    private static final String RUN=UUID.randomUUID().toString();
    private static long serial;
    private static final Map<Object,MenuState> MENUS=new WeakHashMap<>();
    private static final class MenuState {
        final String battleId=RUN+":"+(++serial);
        Object first;String fingerprint,token;
    }
    private static synchronized MenuState state(Object battle) {
        return MENUS.computeIfAbsent(battle,key->new MenuState());
    }
    private static synchronized String token(Object battle,Object first,String fingerprint) {
        MenuState state=state(battle);
        if(state.token==null || state.first!=first || !fingerprint.equals(state.fingerprint)) {
            state.first=first;state.fingerprint=fingerprint;state.token=state.battleId+":"+(++serial);
        }
        return state.token;
    }
    private static synchronized void invalidate(Object battle) {state(battle).token=null;}

    public static JsonObject snapshot(Object current) {
        JsonObject out=new JsonObject();out.addProperty("telemetry_complete",false);out.addProperty("command_ready",false);
        out.add("battle_id",JsonNull.INSTANCE);out.add("menu_token",JsonNull.INSTANCE);out.add("actor",JsonNull.INSTANCE);
        out.add("menu",JsonNull.INSTANCE);out.add("target_group",JsonNull.INSTANCE);out.add("selected_item_id",JsonNull.INSTANCE);
        for(String key:new String[]{"fighters","party","items","options","enemy_groups"})out.add(key,new JsonArray());
        try {
            Object battle=get(current,"ba");if(battle==null)return out;
            out.addProperty("battle_id",state(battle).battleId);
            List<?> groups=list(get(battle,"H")),rows=list(get(battle,"N"));
            int[] active=(int[])get(battle,"I");boolean[] controlled=(boolean[])get(battle,"K");
            List<?> turns=list(get(battle,"ay"));
            int actorGroup=turns.isEmpty()?0:number(turns.get(0));
            if(actorGroup<0 || actorGroup>=controlled.length)throw new IllegalStateException("Invalid actor group");
            if(!controlled[actorGroup])actorGroup=0;
            Object actor=fighter(groups,active,actorGroup);
            JsonObject actorView=fighterView(actor);actorView.addProperty("group",actorGroup);actorView.addProperty("active_index",active[actorGroup]);actorView.addProperty("controlled",controlled[actorGroup]);out.add("actor",actorView);
            JsonArray fighters=new JsonArray();
            for(int group=0;group<groups.size();group++) {
                List<?> members=list(groups.get(group));if(members.isEmpty())continue;
                if(group>=active.length || group>=controlled.length)throw new IllegalStateException("Invalid battle groups");
                JsonObject row=fighterView(fighter(groups,active,group));row.addProperty("group",group);
                row.addProperty("active_index",active[group]);row.addProperty("controlled",controlled[group]);fighters.add(row);
            }
            out.add("fighters",fighters);JsonArray party=new JsonArray();
            List<?> members=list(groups.get(actorGroup));
            for(int slot=0;slot<members.size();slot++) {JsonObject member=fighterView(members.get(slot));member.addProperty("slot",slot);party.add(member);}
            out.add("party",party);
            String menu=flag(battle,"bw")?(integer(battle,"bx")!=0?"item_target":"items"):
                    flag(battle,"bu")?"digivolve":flag(battle,"bt")?"switch":"main";
            out.addProperty("menu",menu);out.addProperty("selected_item_id",integer(battle,"bx"));out.addProperty("selected_option_index",integer(battle,"bA"));
            Map<?,?> definitions=(Map<?,?>)get(battle,"by");Map<Integer,Integer> quantities=new HashMap<>();
            for(Object quantity:list(get(battle,"bz")))quantities.merge(integer(quantity,"a"),Math.max(0,integer(quantity,"b")),Integer::sum);
            JsonArray items=new JsonArray();
            for(Object id:definitions.keySet().stream().sorted(Comparator.comparingInt(BattleControl::number)).toList()) {
                JsonObject item=itemView(definitions.get(id));item.addProperty("quantity",quantities.getOrDefault(number(id),0));items.add(item);
            }
            out.add("items",items);JsonArray options=new JsonArray();
            List<?> skills=list(get(get(actor,"a"),"d"));
            for(int index=0;index<rows.size();index++) {
                Object source=rows.get(index),command=get(source,"c");
                JsonObject option=new JsonObject();option.addProperty("index",index);
                option.addProperty("label",(String)get(source,"a"));option.addProperty("enabled",flag(source,"d"));
                String kind=commandKind(command,integer(source,"h"));option.addProperty("kind",kind);
                if(kind.equals("skill")) {
                    int skillIndex=integer(command,"a");
                    if(skillIndex<0 || skillIndex>=skills.size())throw new IllegalStateException("Unknown battle skill");
                    Object skill=skills.get(skillIndex);int cost=integer(skill,"b");
                    if(cost<0)throw new IllegalStateException("Invalid skill cost");
                    option.addProperty("skill_index",skillIndex);option.addProperty("ds_cost",cost);
                    option.addProperty("sequence",integer(skill,"c"));option.addProperty("range",((Number)get(skill,"d")).doubleValue());
                    option.addProperty("icon",integer(skill,"e"));
                }else if(kind.equals("item"))option.addProperty("item_id",integer(source,"i"));
                else if(kind.equals("item_target")) {
                    option.addProperty("item_id",integer(command,"a"));option.addProperty("target_slot",integer(command,"b"));
                    if(definitions.containsKey(integer(command,"a")))option.add("effect",itemView(definitions.get(integer(command,"a"))));
                }else if(kind.equals("switch_target"))option.addProperty("target_slot",integer(command,"a"));
                else if(kind.equals("digivolve_target"))option.addProperty("form_id",integer(command,"a"));
                options.add(option);
            }
            out.add("options",options);JsonArray enemies=new JsonArray();
            List<Integer> aliveEnemies=new ArrayList<>();
            for(int group:new int[]{1,4,5})
                if(group<groups.size() && !list(groups.get(group)).isEmpty() && integer(fighter(groups,active,group),"i")>0)aliveEnemies.add(group);
            int selectedTarget=integer(battle,"aC");
            if(!aliveEnemies.contains(selectedTarget))selectedTarget=aliveEnemies.isEmpty()?1:aliveEnemies.get(0);
            for(int group:aliveEnemies)if(flag(battle,"aB") || group==selectedTarget)enemies.add(group);
            out.add("enemy_groups",enemies);out.addProperty("target_group",selectedTarget);
            boolean ready=get(current,"bn")==null && ready(battle) && !rows.isEmpty();
            out.addProperty("command_ready",ready);out.addProperty("telemetry_complete",true);
            // Include numeric turn order as well as actor/resources/statuses.
            JsonArray turnView=new JsonArray();for(Object turn:turns)turnView.add(number(turn));
            out.add("turn_order",turnView);
            JsonObject fingerprint=out.deepCopy();fingerprint.remove("selected_option_index");
            out.addProperty("menu_token",token(battle,rows.isEmpty()?null:rows.get(0),fingerprint.toString()));
        }catch(Exception unknown) {out.addProperty("telemetry_complete",false);out.addProperty("command_ready",false);out.add("menu_token",JsonNull.INSTANCE);}
        return out;
    }

    public static JsonObject choose(Object current,JsonObject request)throws Exception {
        JsonObject before=guard(current,request);Object battle=get(current,"ba");
        int index=request.get("option_index").getAsInt();List<?> rows=list(get(battle,"N"));
        if(index<0 || index>=rows.size())throw new IllegalArgumentException("Unknown battle option");
        Object row=rows.get(index);if(!flag(row,"d"))throw new IllegalStateException("Battle option is disabled");
        JsonObject option=before.getAsJsonArray("options").get(index).getAsJsonObject();
        if("skill".equals(option.get("kind").getAsString()) && option.get("ds_cost").getAsInt()>before.getAsJsonObject("actor").get("ds").getAsInt())
            throw new IllegalStateException("Battle skill is not affordable");
        if(request.has("target_group")) {
            int desired=request.get("target_group").getAsInt();List<Integer> targets=new ArrayList<>();
            for(JsonElement target:before.getAsJsonArray("enemy_groups"))targets.add(target.getAsInt());
            if(!targets.contains(desired))throw new IllegalArgumentException("Invalid battle target");
            int selected=before.get("target_group").getAsInt();
            if(desired!=selected) {
                if(targets.size()<2)throw new IllegalStateException("Target cycling is unavailable");
                call(battle,"a",new Class<?>[]{int.class,boolean.class},targets.indexOf(desired)-targets.indexOf(selected),true);
                if(snapshot(current).get("target_group").getAsInt()!=desired)throw new IllegalStateException("Battle target changed");
            }
        }
        int selected=integer(battle,"bA");
        if(selected!=index)call(battle,"a",new Class<?>[]{int.class},index-selected);
        JsonObject selectedState=snapshot(current);
        if(get(current,"ba")!=battle || get(current,"bn")!=null || !selectedState.get("command_ready").getAsBoolean()
                || !before.get("actor").equals(selectedState.get("actor")) || !before.get("turn_order").equals(selectedState.get("turn_order")) || integer(battle,"bA")!=index
                || list(get(battle,"N")).get(index)!=row || !flag(row,"d"))
            throw new IllegalStateException("Battle changed during selection");
        try {call(battle,"b",new Class<?>[0]);}
        finally {invalidate(battle);}
        return result(before,snapshot(current));
    }

    public static JsonObject back(Object current,JsonObject request)throws Exception {
        JsonObject before=guard(current,request);String menu=before.get("menu").getAsString();
        if(menu.equals("main") || (menu.equals("switch") && before.getAsJsonObject("actor").get("hp").getAsInt()<=0))
            throw new IllegalStateException("No supported battle submenu to close");
        Object battle=get(current,"ba");
        try {call(battle,"d",new Class<?>[0]);}finally{invalidate(battle);}
        return result(before,snapshot(current));
    }
    private static JsonObject guard(Object current,JsonObject request) {
        JsonObject before=snapshot(current);
        if(!before.get("telemetry_complete").getAsBoolean() || !before.get("command_ready").getAsBoolean())
            throw new IllegalStateException("Battle command is not ready");
        if(!request.has("expected_token") || !request.get("expected_token").equals(before.get("menu_token")))
            throw new IllegalStateException("Battle menu changed");
        return before;
    }
    private static JsonObject result(JsonObject before,JsonObject after) {JsonObject result=new JsonObject();result.add("before",before);result.add("after",after);return result;}
    private static boolean ready(Object battle)throws Exception {
        return flag(battle,"bs") && !flag(battle,"br") && !flag(battle,"bB") && !flag(battle,"bD") && !flag(battle,"bK")
                && ((Number)get(battle,"aY")).doubleValue()<=0 && get(battle,"bC")==null && get(battle,"bc")==null && ((Collection<?>)get(battle,"M")).isEmpty();
    }
    private static Object fighter(List<?> groups,int[] active,int group) {
        List<?> members=list(groups.get(group));return members.get(active[group]);
    }
    private static JsonObject fighterView(Object source)throws Exception {
        JsonObject row=new JsonObject();row.addProperty("form_id",integer(source,"b"));row.addProperty("base_id",integer(source,"c"));
        row.addProperty("hp",integer(source,"i"));row.addProperty("max_hp",integer(source,"e"));
        row.addProperty("ds",integer(source,"j"));row.addProperty("max_ds",integer(source,"f"));
        if(integer(source,"i")<0 || integer(source,"e")<=0 || integer(source,"i")>integer(source,"e")
                || integer(source,"j")<0 || integer(source,"f")<0 || integer(source,"j")>integer(source,"f"))
            throw new IllegalStateException("Invalid battle resources");
        JsonArray statuses=new JsonArray();
        for(Object status:(Collection<?>)get(source,"k")) {
            if(!(status instanceof Enum<?> value))throw new IllegalStateException("Unknown battle status");statuses.add(value.ordinal());
        }
        row.add("statuses",statuses);return row;
    }
    private static JsonObject itemView(Object item)throws Exception {
        JsonObject row=new JsonObject();row.addProperty("item_id",integer(item,"a"));
        row.addProperty("heal_hp",integer(item,"b"));row.addProperty("heal_hp_percent",integer(item,"c"));
        row.addProperty("heal_ds",integer(item,"g"));row.addProperty("heal_ds_percent",integer(item,"d"));
        row.addProperty("revive_available",integer(item,"f")>0);row.addProperty("revival_value",integer(item,"f"));
        row.add("revive_percent",JsonNull.INSTANCE);return row;
    }
    private static String commandKind(Object command,int submenu) {
        if(command==null)return switch(submenu){case 1->"switch";case 2->"digivolve";case 3->"items";case 4->"item";default->"unknown";};
        return switch(command.getClass().getName()) {
            case "bv$a"->"attack";case "bv$f"->"skill";case "bv$e"->"item_target";
            case "bv$d"->"switch_target";case "bv$b"->"digivolve_target";case "bv$c"->"escape";default->"unknown";
        };
    }
    private static List<?> list(Object value){return (List<?>)value;}
    private static int number(Object value){return ((Number)value).intValue();}
    private static int integer(Object object,String name)throws Exception{return number(get(object,name));}
    private static boolean flag(Object object,String name)throws Exception{return (Boolean)get(object,name);}
    private static Object get(Object object,String name)throws Exception {Field field=object.getClass().getDeclaredField(name);field.setAccessible(true);return field.get(object);}
    private static Object call(Object object,String name,Class<?>[] types,Object...args)throws Exception {Method method=object.getClass().getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(object,args);}
}
