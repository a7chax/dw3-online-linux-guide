package dw3.linux;

import com.google.gson.*;
import java.lang.reflect.*;
import java.util.*;

/** Pure views of the original aj/J fishing UI; sends no input or network messages. */
public final class FishingControl {
    private FishingControl() {}
    private static final String RUN=UUID.randomUUID().toString();
    private static final Map<Object,String> IDS=new WeakHashMap<>();
    private static long serial;
    private static synchronized String id(Object value) {
        return value==null?"none":IDS.computeIfAbsent(value,key->RUN+":"+(++serial));
    }

    public static JsonObject snapshot(Object current) {
        JsonObject out=new JsonObject();
        for(String key:new String[]{"active","telemetry_complete","at_spot","can_cast","can_reel","reel_good","exhausted"})out.addProperty(key,false);
        for(String key:new String[]{"state_token","rod_available","cast_facing","facing","fishing_type","timing_frame","cast_count"})out.add(key,JsonNull.INSTANCE);
        try {
            Object game=get(current,"ag");int spot=number(current,"ap"),facing=number(current,"az");
            float cast=decimal(current,"aq"),ending=decimal(current,"ar"),elapsed=decimal(current,"aV"),last=decimal(current,"as");
            boolean exhausted=flag(current,"at");
            boolean clear=(Boolean)call(current,"C",new Class<?>[0]);
            // C is the original pure world UI predicate; these additional
            // overlays/animations also suppress original world movement.
            for(String field:new String[]{"aC","ch","cF","cj","ck","cv","cz","cA","cB","cD","cE","cl","co","cm","cn","cx","bD","bE","ai"})clear&=get(current,field)==null;
            clear&=number(current,"bY")<0 && decimal(current,"ac")<0 && decimal(current,"G")<0;
            clear&=!(Boolean)call(get(current,"by"),"a",new Class<?>[0]);
            clear&=!(Boolean)call(get(current,"bs"),"a",new Class<?>[0]);
            clear&=!(Boolean)call(get(current,"cG"),"g",new Class<?>[0]);
            if(spot!=255 && (spot<0 || spot>7))throw new IllegalStateException("Unknown fishing facing");
            if(facing<0 || facing>7)throw new IllegalStateException("Unknown facing");
            int difference=Math.floorMod(facing-spot,8);
            boolean castReady=clear && spot!=255 && game==null && cast>=0 && ending<0 && elapsed-last>=1
                && (difference<=1 || difference==7);
            boolean reelReady=false,good=false;int type=-1;boolean submitted=false;
            if(game!=null) {
                type=number(game,"d");int frame=((Number)call(game,"a",new Class<?>[0])).intValue();
                reelReady=clear && (Boolean)call(game,"b",new Class<?>[0]);submitted=flag(game,"f");
                if(type!=255 && (type<0 || type>8))throw new IllegalStateException("Unknown fishing type");
                out.addProperty("fishing_type",type);out.addProperty("timing_frame",frame);out.addProperty("cast_count",number(game,"e"));
                exhausted|=type==8;
                if(reelReady && type!=8) {
                    Class<?> rules=Class.forName("bB");
                    int normal=((Number)staticCall(rules,"a",new Class<?>[]{int.class,boolean.class},frame,false)).intValue();
                    int alternate=((Number)staticCall(rules,"a",new Class<?>[]{int.class,boolean.class},frame,true)).intValue();
                    boolean normalGood=((Number)staticCall(rules,"b",new Class<?>[]{int.class,int.class},type,normal)).intValue()==2;
                    boolean alternateGood=((Number)staticCall(rules,"b",new Class<?>[]{int.class,int.class},type,alternate)).intValue()==2;
                    good=normalGood && (alternateGood || frame>=96);
                }
            }
            out.addProperty("active",game!=null || cast>=0);out.addProperty("at_spot",spot!=255);
            out.addProperty("cast_facing",spot);out.addProperty("facing",facing);out.addProperty("exhausted",exhausted);
            out.addProperty("can_cast",castReady && !exhausted);out.addProperty("can_reel",reelReady);
            out.addProperty("reel_good",good);out.addProperty("telemetry_complete",true);
            // Timer h and reel_good deliberately do not bind the generation:
            // they drift every render. Input must recheck fresh readiness and
            // good timing on the render thread, against this stable cast token.
            out.addProperty("state_token",id(current)+":"+id(game)+":"+spot+":"+facing+":"+(cast>=0)+":"+(ending>=0)+":"+type+":"+submitted+":"+clear+":"+exhausted);
        } catch(Exception unknown) {
            out.addProperty("telemetry_complete",false);out.addProperty("can_cast",false);out.addProperty("can_reel",false);out.addProperty("reel_good",false);out.add("state_token",JsonNull.INSTANCE);
        }
        return out;
    }

    /** Plan one ordinary Space; the caller owns render-thread input and release. */
    public static JsonObject plan(Object current,String mode,String expectedToken) {
        JsonObject state=snapshot(current),out=new JsonObject();out.add("key",JsonNull.INSTANCE);
        String reason="fishing_not_ready";
        if(mode==null || !Set.of("cast","reel","exhausted").contains(mode))reason="unsupported_fishing_action";
        else if(!state.get("telemetry_complete").getAsBoolean())reason="fishing_telemetry_unavailable";
        else if(expectedToken==null || !state.get("state_token").getAsString().equals(expectedToken))reason="fishing_state_changed";
        else {
            boolean ready=switch(mode) {
                case "cast" -> state.get("can_cast").getAsBoolean();
                case "reel" -> state.get("can_reel").getAsBoolean() && state.get("reel_good").getAsBoolean();
                default -> state.get("can_reel").getAsBoolean() && !state.get("fishing_type").isJsonNull() && state.get("fishing_type").getAsInt()==8;
            };
            if(ready) {out.addProperty("key","space");reason="fishing_"+mode+"_ready";}
        }
        out.addProperty("reason",reason);return out;
    }

    private static Object get(Object value,String name)throws Exception {
        if(value==null)throw new IllegalStateException("Missing fishing context");
        for(Class<?> type=value.getClass();type!=null;type=type.getSuperclass())try {Field field=type.getDeclaredField(name);field.setAccessible(true);return field.get(value);}catch(NoSuchFieldException next){}
        throw new NoSuchFieldException(name);
    }
    private static int number(Object value,String name)throws Exception {return ((Number)get(value,name)).intValue();}
    private static float decimal(Object value,String name)throws Exception {float result=((Number)get(value,name)).floatValue();if(!Float.isFinite(result))throw new IllegalStateException("Invalid fishing time");return result;}
    private static boolean flag(Object value,String name)throws Exception {return (Boolean)get(value,name);}
    private static Object call(Object value,String name,Class<?>[]types,Object...arguments)throws Exception {Method method=value.getClass().getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(value,arguments);}
    private static Object staticCall(Class<?> type,String name,Class<?>[]types,Object...arguments)throws Exception {Method method=type.getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(null,arguments);}
}
