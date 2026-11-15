package dw3.linux;

import com.google.gson.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Pure snapshots and one-step plans for the original inventory/shop UI. */
public final class SuppliesControl {
    private SuppliesControl() {}
    private static Object get(Object object,String name)throws Exception {
        if(object==null)throw new IllegalStateException("Missing supplies field");
        for(Class<?> c=object.getClass();c!=null;c=c.getSuperclass())try {
            Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(object);
        }catch(NoSuchFieldException absent) {}
        throw new NoSuchFieldException(name);
    }
    private static Object optional(Object object,String name) {try{return get(object,name);}catch(Exception absent){return null;}}
    private static int number(Object object,String name)throws Exception {return ((Number)get(object,name)).intValue();}
    private static boolean flag(Object object,String name)throws Exception {return (Boolean)get(object,name);}
    private static Object call(Object object,String name,Class<?>[] types,Object...args)throws Exception {
        Method m=object.getClass().getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(object,args);
    }
    private static String token(String value)throws Exception {
        byte[] bytes=MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(bytes);
    }
    private static JsonObject unknown(String...fields) {
        JsonObject out=new JsonObject();out.addProperty("telemetry_complete",false);
        for(String field:fields)out.add(field,JsonNull.INSTANCE);return out;
    }
    private static String name(Object game,int id) {
        Object cache=optional(game,"af");
        if(cache instanceof Map<?,?> map && map.get("items") instanceof String[] names && id>=0 && id<names.length)return names[id];
        return null;
    }
    private static Map<?,?> rules(Object game) {
        Object table=optional(optional(game,"O"),"a");return table instanceof Map<?,?> map?map:null;
    }
    private static JsonObject effect(Object game,int id) {
        JsonObject out=unknown("kind","heal_hp","heal_ds","buy_bits","sell_bits");
        out.addProperty("id",id);String name=name(game,id);if(name!=null)out.addProperty("name",name);else out.add("name",JsonNull.INSTANCE);
        Map<?,?> table=rules(game);Object rule=table==null?null:table.get(id);
        out.addProperty("rule_source","loaded_client_itemrules");
        if(rule==null)return out;
        try {
            Enum<?> kind=(Enum<?>)get(rule,"a");int ordinal=kind.ordinal();
            String[] kinds={"key","use","weapon","armour","accessory"};
            int hp=number(rule,"d"),ds=number(rule,"f"),buy=number(rule,"b"),sell=number(rule,"c");
            if(ordinal<0 || ordinal>=kinds.length || hp<0 || ds<0 || buy<0 || sell<0)return out;
            out.addProperty("kind",kinds[ordinal]);out.addProperty("heal_hp",hp);out.addProperty("heal_ds",ds);
            out.addProperty("buy_bits",buy);out.addProperty("sell_bits",sell);out.addProperty("telemetry_complete",true);
        }catch(Exception absent) {}return out;
    }
    private static List<?> visible(Object current)throws Exception {
        Object menu=get(current,"by");List<?> inventory=(List<?>)get(current,"bv");
        // Original G's filter/sort and timed-row expansion only read state.
        List<?> filtered=(List<?>)call(menu,"a",new Class<?>[]{List.class},inventory);
        return (List<?>)call(menu,"a",new Class<?>[]{List.class,List.class},filtered,new ArrayList<Long>());
    }
    private static JsonObject menu(Object current) {
        JsonObject out=unknown("mode","selected_index","target_item","target_slot");
        try {
            Object menu=get(current,"by");int mode=number(menu,"t");
            out.addProperty("mode",mode);out.addProperty("active",mode!=-1);
            out.addProperty("selected_index",number(menu,"u"));out.addProperty("target_item",number(menu,"v"));
            out.addProperty("target_slot",number(menu,"y"));out.addProperty("search_active",flag(menu,"k"));
            out.addProperty("search_length",get(menu,"j").toString().length());
            boolean nested=number(menu,"w")!=0 || number(menu,"aj")!=0 || flag(menu,"z") || flag(menu,"K") || flag(menu,"A") || get(menu,"S")!=null;
            Object context=get(menu,"ac");if(context!=null && call(context,"a",new Class<?>[0])!=null)nested=true;
            out.addProperty("nested_modal",nested);
            JsonArray rows=new JsonArray();
            if(mode==1) {
                if(rules(optional(current,"M"))==null)throw new IllegalStateException("Rules await normal inventory render");
                for(Object row:visible(current))rows.add(number(row,"a"));
            }
            out.add("visible_ids",rows);out.addProperty("telemetry_complete",true);
        }catch(Exception absent) {}return out;
    }
    private static JsonObject shop(Object current,Object game) {
        JsonObject out=new JsonObject();JsonArray offers=new JsonArray();out.add("offers",offers);
        out.addProperty("active",false);out.addProperty("telemetry_complete",false);out.add("offer_token",JsonNull.INSTANCE);
        try {
            Object shop=get(current,"bA");
            if(shop==null){out.addProperty("telemetry_complete",true);return out;}
            out.addProperty("active",true);Object offer=get(shop,"c");int id=number(offer,"a");
            out.addProperty("shop_id",id);out.addProperty("mode",flag(shop,"f")?"sell":"buy");
            out.addProperty("submitting",flag(shop,"j"));out.addProperty("closed",flag(shop,"m"));
            out.addProperty("selected_index",number(shop,"g"));out.addProperty("quantity",number(shop,"i"));
            out.addProperty("confirmation_item",number(shop,"n"));out.addProperty("confirmation_quantity",number(shop,"p"));
            out.addProperty("confirmation_sell",flag(shop,"o"));
            out.addProperty("confirmation_active",((Number)get(shop,"q")).doubleValue()<3);
            int index=0;boolean complete=true;
            for(Object entry:(List<?>)get(offer,"b")) {
                int item=number(entry,"a"),price=number(entry,"b");
                JsonObject row=effect(game,item);row.addProperty("index",index++);row.addProperty("unit_bits",price);
                row.addProperty("currency","bits");offers.add(row);
                if(item<=0 || price<=0)complete=false;
            }
            out.addProperty("offer_token",token(System.identityHashCode(shop)+":"+id+":"+offers));
            out.addProperty("telemetry_complete",complete);
        }catch(Exception absent) {}return out;
    }
    public static JsonObject snapshot(Object current) {
        JsonObject out=new JsonObject();out.addProperty("telemetry_complete",false);
        JsonArray inventory=new JsonArray(),party=new JsonArray();out.add("inventory",inventory);out.add("party",party);
        Object game=optional(current,"M");boolean complete=rules(game)!=null;
        out.addProperty("rules_loaded",complete);
        try {
            for(Object entry:(List<?>)get(current,"bv")) {
                int id=number(entry,"a"),quantity=number(entry,"b");JsonObject row=effect(game,id);
                row.addProperty("quantity",quantity);inventory.add(row);if(id<=0 || quantity<0)complete=false;
            }
        }catch(Exception absent){complete=false;}
        try {
            int slot=0;for(Object entry:(List<?>)get(get(current,"bu"),"d")) {
                JsonObject row=new JsonObject();Object stats=get(entry,"g");
                int hp=number(entry,"e"),maxHp=number(stats,"a"),ds=number(entry,"f"),maxDs=number(stats,"b");
                row.addProperty("slot",slot++);row.addProperty("id",number(entry,"a"));
                row.addProperty("hp",hp);row.addProperty("max_hp",maxHp);row.addProperty("ds",ds);row.addProperty("max_ds",maxDs);party.add(row);
                if(hp<0 || maxHp<=0 || hp>maxHp || ds<0 || maxDs<0 || ds>maxDs)complete=false;
            }if(party.isEmpty())complete=false;
        }catch(Exception absent){complete=false;}
        JsonObject wallet=unknown("bits","cash");
        try {int bits=number(get(current,"bt"),"a"),cash=number(get(current,"bt"),"b");
            wallet.addProperty("bits",bits);wallet.addProperty("cash",cash);wallet.addProperty("telemetry_complete",bits>=0 && cash>=0);
            if(bits<0 || cash<0)complete=false;
        }catch(Exception absent){complete=false;}out.add("wallet",wallet);
        JsonObject menu=menu(current),shop=shop(current,game);out.add("menu",menu);out.add("shop",shop);
        out.addProperty("inventory_open",menu.has("mode") && !menu.get("mode").isJsonNull() && menu.get("mode").getAsInt()==1);
        complete&=menu.get("telemetry_complete").getAsBoolean() && shop.get("telemetry_complete").getAsBoolean();
        boolean blocked=false;for(String field:new String[]{"ba","bn","aC","aX","aZ","aM","bz"})if(optional(current,field)!=null)blocked=true;
        out.addProperty("world_modal",blocked);out.addProperty("telemetry_complete",complete);
        try {out.addProperty("state_token",token(out.toString()));}catch(Exception impossible){out.add("state_token",JsonNull.INSTANCE);}
        return out;
    }
    private static JsonObject plan(String key,String reason) {
        return plan(key,reason,false);
    }
    private static JsonObject plan(String key,String reason,boolean submit) {
        JsonObject out=new JsonObject();if(key==null)out.add("key",JsonNull.INSTANCE);else out.addProperty("key",key);
        out.addProperty("reason",reason);out.addProperty("submit",submit);return out;
    }
    private static int integer(JsonObject object,String field) {return object.get(field).getAsInt();}
    private static boolean yes(JsonObject object,String field) {return object.has(field) && !object.get(field).isJsonNull() && object.get(field).getAsBoolean();}
    private static JsonObject item(JsonArray rows,int id) {
        for(JsonElement entry:rows)if(integer(entry.getAsJsonObject(),"id")==id)return entry.getAsJsonObject();return null;
    }
    private static boolean heals(JsonObject item) {
        return item!=null && yes(item,"telemetry_complete") && "use".equals(item.get("kind").getAsString()) &&
            (integer(item,"heal_hp")>0 || integer(item,"heal_ds")>0);
    }
    private static String step(int selected,int target,int size,boolean grid) {
        int delta=Math.floorMod(target-selected,size);if(delta>size/2)delta-=size;
        if(grid && Math.abs(delta)>=10)return delta>0?"down":"up";
        return delta>0?(grid?"right":"down"):(grid?"left":"up");
    }
    public static JsonObject planUse(Object current,int id,int slot) {
        try {
            JsonObject state=snapshot(current),menu=state.getAsJsonObject("menu");
            if(!yes(state,"telemetry_complete") || yes(state,"world_modal") || yes(state.getAsJsonObject("shop"),"active"))return plan(null,"supplies_unavailable");
            JsonObject item=item(state.getAsJsonArray("inventory"),id);JsonArray party=state.getAsJsonArray("party");
            if(!heals(item) || integer(item,"quantity")<=0 || slot<0 || slot>=party.size())return plan(null,"item_unavailable");
            JsonObject member=party.get(slot).getAsJsonObject();
            if(integer(member,"hp")<=0 || !((integer(item,"heal_hp")>0 && integer(member,"hp")<integer(member,"max_hp")) ||
                    (integer(item,"heal_ds")>0 && integer(member,"ds")<integer(member,"max_ds"))))return plan(null,"item_target_ineligible");
            if(integer(menu,"mode")!=1)return plan("i","open_inventory");
            if(yes(menu,"search_active") || yes(menu,"nested_modal"))return plan(null,"inventory_modal");
            int targetItem=integer(menu,"target_item");
            if(targetItem!=0) {
                if(targetItem!=id)return plan("x","close_other_item_target");
                int selected=integer(menu,"target_slot");return plan(selected==slot?"space":step(selected,slot,party.size(),false),"use_item",selected==slot);
            }
            JsonArray visible=menu.getAsJsonArray("visible_ids");int target=-1;
            for(int i=0;i<visible.size();i++)if(visible.get(i).getAsInt()==id){target=i;break;}
            if(target<0)return plan(null,"item_not_visible");
            int selected=integer(menu,"selected_index"),size=Math.max(60,((visible.size()+59)/60)*60);
            return plan(selected==target?"space":step(selected,target,size,true),"select_item");
        }catch(Exception unavailable){return plan(null,"supplies_unavailable");}
    }
    public static JsonObject planBuy(Object current,int id,int quantity,String expectedOffer) {
        try {
            JsonObject state=snapshot(current),shop=state.getAsJsonObject("shop");
            if(!yes(state,"telemetry_complete") || yes(state,"world_modal") || !yes(shop,"active") || yes(shop,"closed") || yes(shop,"submitting"))return plan(null,"shop_unavailable");
            if(!"buy".equals(shop.get("mode").getAsString()) || expectedOffer==null || !expectedOffer.equals(shop.get("offer_token").getAsString()))return plan(null,"shop_offer_changed");
            JsonObject offer=item(shop.getAsJsonArray("offers"),id);if(!heals(offer) || quantity<1 || quantity>5)return plan(null,"purchase_not_allowed");
            JsonObject owned=item(state.getAsJsonArray("inventory"),id);int count=owned==null?0:integer(owned,"quantity");
            long total=(long)quantity*integer(offer,"unit_bits");
            if(count+quantity>999 || total>integer(state.getAsJsonObject("wallet"),"bits"))return plan(null,"purchase_unaffordable");
            int selected=integer(shop,"selected_index"),target=integer(offer,"index");
            if(selected!=target)return plan(step(selected,target,shop.getAsJsonArray("offers").size(),false),"select_shop_item");
            int currentQuantity=integer(shop,"quantity");
            if(currentQuantity!=quantity)return plan(currentQuantity<quantity?"right":"left","select_shop_quantity");
            boolean second=integer(shop,"confirmation_item")==id && integer(shop,"confirmation_quantity")==quantity &&
                !yes(shop,"confirmation_sell") && yes(shop,"confirmation_active");
            boolean submits=quantity<10 && total<10000 || second;
            return plan("space",submits?"confirm_purchase":"confirm_large_purchase",submits);
        }catch(Exception unavailable){return plan(null,"shop_unavailable");}
    }
    public static JsonObject planInspect(Object current) {
        try {
            JsonObject state=snapshot(current),shop=state.getAsJsonObject("shop");
            if(yes(state,"world_modal") || yes(shop,"active"))return plan(null,"supplies_modal");
            Object menu=get(current,"by");int mode=number(menu,"t");
            if(mode==1)return plan(null,yes(state,"telemetry_complete")?"inventory_ready":"inventory_rules_loading");
            if(flag(menu,"k") || number(menu,"v")!=0 || number(menu,"w")!=0 || number(menu,"aj")!=0)return plan(null,"inventory_modal");
            return plan("i","inspect_inventory");
        }catch(Exception unavailable){return plan(null,"supplies_unavailable");}
    }
    public static JsonObject planClose(Object current) {
        try {
            JsonObject state=snapshot(current),shop=state.getAsJsonObject("shop"),menu=state.getAsJsonObject("menu");
            if(yes(state,"world_modal"))return plan(null,"supplies_modal");
            if(yes(shop,"active"))return yes(shop,"submitting")?plan(null,"purchase_pending"):plan("x","close_shop");
            if(!yes(menu,"telemetry_complete"))return plan(null,"inventory_unavailable");
            if(integer(menu,"target_item")!=0)return plan("x","close_item_target");
            if(yes(menu,"nested_modal") || yes(menu,"search_active"))return plan(null,"inventory_modal");
            if(integer(menu,"mode")==1)return plan("i","close_inventory");
            if(integer(menu,"mode")!=-1)return plan("i","switch_inventory");
            return plan(null,"supplies_closed");
        }catch(Exception unavailable){return plan(null,"supplies_unavailable");}
    }
}
