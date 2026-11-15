package dw3.linux;

import com.google.gson.*;
import java.io.*;
import java.lang.reflect.*;
import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Locale;
import java.util.concurrent.*;
import java.util.function.Supplier;

/** Explicitly enabled local control socket; no credential requests are logged. */
public final class ControlBridge implements AutoCloseable {
    private static final String[] MOVEMENT_DIRECTIONS={
        "up","down","left","right","up_left","up_right","down_left","down_right"
    };
    private static final java.util.Set<String> INN_MAPS=java.util.Set.of(
        "s235","s236","s360","s361","s425","s426","s470","s471","s505","s506",
        "s560","s561","s650","s651","s660","s661","s700","s701","s750","s760",
        "s761","s928","s946","s957","s981");
    private final Path path;
    private final ServerSocketChannel server;
    private final Thread thread;
    private volatile boolean closed;
    private Object backgroundWindow;
    private static long nativeInputGeneration;
    private final Gson JSON = new Gson();

    private ControlBridge(Path path) throws IOException {
        this.path=path;
        Files.createDirectories(path.getParent());
        server=ServerSocketChannel.open(StandardProtocolFamily.UNIX);
        server.bind(UnixDomainSocketAddress.of(path));
        Files.setPosixFilePermissions(path,PosixFilePermissions.fromString("rw-------"));
        thread=new Thread(this::serve,"dw3-local-control");
        thread.setDaemon(true);thread.start();
    }

    static ControlBridge startIfRequested() throws IOException {
        String configured=System.getenv("DW3_CONTROL_SOCKET");
        if(configured==null || configured.isBlank())return null;
        return new ControlBridge(Path.of(configured).toAbsolutePath());
    }

    private void serve() {
        while(!closed) {
            try(SocketChannel channel=server.accept()) {
                BufferedReader input=new BufferedReader(Channels.newReader(channel,StandardCharsets.UTF_8));
                StringBuilder line=new StringBuilder();
                int character;
                while((character=input.read())!=-1 && character!='\n') {
                    if(line.length()>=8192)throw new IOException("Control request is too large");
                    line.append((char)character);
                }
                JsonObject reply;
                try {
                    JsonObject request=JsonParser.parseString(line.toString()).getAsJsonObject();
                    JsonElement result=dispatch(request);
                    reply=new JsonObject();reply.addProperty("ok",true);reply.add("result",result);
                    request=null;
                } catch(Exception error) {
                    reply=new JsonObject();reply.addProperty("ok",false);
                    Throwable cause=error instanceof InvocationTargetException ? error.getCause() : error;
                    // Exceptions contain operation/field errors, never request values.
                    reply.addProperty("error",cause.getClass().getSimpleName()+": "+cause.getMessage());
                }
                Writer output=Channels.newWriter(channel,StandardCharsets.UTF_8);
                output.write(JSON.toJson(reply)+"\n");output.flush();
            } catch(IOException error) {
                if(!closed)System.err.println("DW3_CONTROL: local connection ended.");
            }
        }
    }

    private JsonElement dispatch(JsonObject request) throws Exception {
        String operation=request.get("op").getAsString();
        if(operation.equals("battle_choose") || operation.equals("battle_back"))return onRender(()->{
            JsonObject before=guardAutomationInput(request);Object current=screen();
            JsonObject story=before.has("story")?before.getAsJsonObject("story"):null;
            if(story!=null && story.get("active").getAsBoolean() && !completedStory(story))
                throw new IllegalStateException("Story blocks battle input");
            if(operation.equals("battle_back"))BattleControl.back(current,request);else BattleControl.choose(current,request);
            JsonObject result=new JsonObject();result.add("before",before);result.add("after",status());return result;
        });
        if(operation.equals("fishing_step")) {
            int[] pressed={-1};JsonObject[] plan={null};JsonElement before;
            try {
                before=onRender(()->{
                    JsonObject snapshot=guardAutomationInput(request);
                    String map=snapshot.get("map").getAsString();
                    if(!java.util.Set.of("s380","s381","s950").contains(map))
                        throw new IllegalStateException("Fishing destination changed");
                    plan[0]=FishingControl.plan(screen(),request.get("mode").getAsString(),request.get("expected_state_token").getAsString());
                    if(plan[0].has("key") && !plan[0].get("key").isJsonNull()) {
                        pressed[0]=normalKey(plan[0].get("key").getAsString());key(pressed[0],1);
                    }
                    return snapshot;
                });
                if(pressed[0]>=0)Thread.sleep(80);
            } finally {
                if(pressed[0]>=0)onRender(()->{key(pressed[0],0);return JsonNull.INSTANCE;},false);
            }
            JsonObject result=new JsonObject();result.add("before",before);result.add("plan",plan[0]);result.add("after",onRender(this::status));return result;
        }
        if(operation.equals("supplies_step")) {
            int[] pressed={-1};JsonObject[] plan={null};JsonElement before;
            try {
                before=onRender(()->{
                    JsonObject snapshot=guardAutomationInput(request);Object current=screen();
                    JsonObject supplies=SuppliesControl.snapshot(current);
                    if(!request.has("expected_state_token") || !request.get("expected_state_token").equals(supplies.get("state_token")))
                        throw new IllegalStateException("Supplies state changed");
                    String mode=request.get("mode").getAsString();
                    plan[0]=switch(mode) {
                        case "inspect"->SuppliesControl.planInspect(current);
                        case "close"->SuppliesControl.planClose(current);
                        case "use"->SuppliesControl.planUse(current,request.get("item_id").getAsInt(),request.get("party_slot").getAsInt());
                        case "buy"->{guardSuppliesBudget(request,supplies);yield SuppliesControl.planBuy(current,request.get("item_id").getAsInt(),request.get("quantity").getAsInt(),request.get("expected_offer_token").getAsString());}
                        default->throw new IllegalArgumentException("Unsupported supplies action");
                    };
                    if(plan[0].has("key") && !plan[0].get("key").isJsonNull()) {
                        pressed[0]=normalKey(plan[0].get("key").getAsString());key(pressed[0],1);
                    }
                    return snapshot;
                });
                if(pressed[0]>=0)Thread.sleep(120);
            } finally {
                if(pressed[0]>=0)onRender(()->{key(pressed[0],0);return JsonNull.INSTANCE;},false);
            }
            Thread.sleep(35);JsonObject result=new JsonObject();result.add("before",before);result.add("plan",plan[0]);result.add("after",onRender(this::status));return result;
        }
        if(operation.equals("capture"))return onRender(()->capture(request));
        if(operation.equals("export_world")) {
            java.util.concurrent.atomic.AtomicReference<Object> assets=new java.util.concurrent.atomic.AtomicReference<>();
            onRender(()->{
                requireScreen(screen(),"aj");
                Object game=application().getClass().getMethod("getApplicationListener").invoke(application());
                assets.set(get(game,"t"));return JsonNull.INSTANCE;
            });
            // Asset reads and disk writes stay off the game's render thread.
            return WorldAtlas.export(assets.get(),Path.of(System.getProperty("user.dir"),"linux","world"));
        }
        if(operation.equals("press_key")) {
            int key=normalKey(request.get("key").getAsString());
            int milliseconds=uiInputDuration(request,120);
            JsonElement before;
            try {
                before=onRender(()->{JsonObject snapshot=guardUiInput(request);key(key,1);return snapshot;});
                Thread.sleep(milliseconds);
            } finally {
                onRender(()->{key(key,0);return JsonNull.INSTANCE;},false);
            }
            Thread.sleep(35);
            JsonObject result=new JsonObject();result.add("before",before);result.add("after",onRender(this::status));
            return result;
        }
        if(operation.equals("click")) {
            int x=request.get("x").getAsInt(),y=request.get("y").getAsInt();
            int milliseconds=uiInputDuration(request,80);
            Object[] mouseInput={null};JsonElement before;
            try {
                before=onRender(()->{
                    JsonObject snapshot=guardUiInput(request);
                    Object graphics=Class.forName("com.badlogic.gdx.Gdx").getField("graphics").get(null);
                    int width=(Integer)graphics.getClass().getMethod("getWidth").invoke(graphics);
                    int height=(Integer)graphics.getClass().getMethod("getHeight").invoke(graphics);
                    if(x<0 || y<0 || x>=width || y>=height)throw new IllegalArgumentException("Click is outside the game window");
                    Object input=Class.forName("com.badlogic.gdx.Gdx").getField("input").get(null);
                    mouseInput[0]=input;
                    mouse(input,x,y,1);return snapshot;
                });
                Thread.sleep(milliseconds);
            } finally {
                onRender(()->{
                    if(mouseInput[0]!=null)mouse(mouseInput[0],x,y,0);
                    return JsonNull.INSTANCE;
                },false);
            }
            Thread.sleep(35);
            JsonObject result=new JsonObject();result.add("before",before);result.add("after",onRender(this::status));
            return result;
        }
        if(operation.equals("move")) {
            int[] keys=movementKeys(request.get("direction").getAsString());
            int milliseconds=request.has("milliseconds")?request.get("milliseconds").getAsInt():250;
            if(milliseconds<50 || milliseconds>750)throw new IllegalArgumentException("Movement duration must be 50 to 750 milliseconds");
            JsonElement before;
            try {
                before=onRender(()->{
                    Object current=screen();requireScreen(current,"aj");
                    JsonObject snapshot=status().getAsJsonObject();
                    if(!"world".equals(snapshot.get("phase").getAsString()))throw new IllegalStateException("Map is loading");
                    if(!snapshot.get("movement_ready").getAsBoolean())
                        throw new IllegalStateException("World input is blocked by an interaction or battle");
                    if(request.has("expected_map") && !request.get("expected_map").equals(snapshot.get("map")))
                        throw new IllegalStateException("Map changed before movement");
                    guardProcess(request);
                    // Input is scoped to this process/window's backend callbacks;
                    // background operation never activates a desktop window.
                    for(int key:keys)key(key,1);
                    return snapshot;
                });
                Thread.sleep(milliseconds);
            } finally {
                // Cleanup must still execute if rendering resumes after the
                // caller's timeout. A key-up is safe even without a key-down.
                onRender(()->{releaseKeys(keys);return JsonNull.INSTANCE;},false);
            }
            Thread.sleep(35);
            JsonObject result=new JsonObject();result.add("before",before);result.add("after",onRender(this::status));
            return result;
        }
        return onRender(()->{
            Object current=screen();
            switch(operation) {
                case "status":return status();
                case "fill_login": {
                    requireScreen(current,"a");
                    if((Boolean)get(current,"m"))throw new IllegalStateException("Login is already in progress");
                    String username=request.get("username").getAsString();
                    String password=request.get("password").getAsString();
                    if(username.isEmpty() || username.length()>16 || password.isEmpty() || password.length()>64)
                        throw new IllegalArgumentException("Invalid credential lengths");
                    StringBuilder name=(StringBuilder)get(current,"e"), secret=(StringBuilder)get(current,"f");
                    name.setLength(0);name.append(username);secret.setLength(0);secret.append(password);
                    set(current,"n",false);set(current,"o",false);set(current,"g",4);set(current,"q",false);set(current,"i","");
                    return status();
                }
                case "clear_password": {
                    requireScreen(current,"a");((StringBuilder)get(current,"f")).setLength(0);return status();
                }
                case "submit_login": {
                    requireScreen(current,"a");invoke(current,"a",new Class<?>[0]);return status();
                }
                case "select_server": {
                    requireScreen(current,"a");
                    if(!(Boolean)get(current,"q"))throw new IllegalStateException("Server selection is not open");
                    String selected=request.get("server").getAsString().toLowerCase(Locale.ROOT);
                    String[] servers=(String[])getStatic("b","a");
                    for(int index=0;index<servers.length;index++)if(servers[index].toLowerCase(Locale.ROOT).contains(selected)) {
                        invoke(current,"a",new Class<?>[]{int.class},index);return status();
                    }
                    throw new IllegalArgumentException("Requested server is not available");
                }
                case "select_character": {
                    requireScreen(current,"r");
                    Object[] characters=(Object[])get(current,"g");
                    String wanted=request.get("character").getAsString();
                    for(int index=0;index<characters.length;index++)if(characters[index]!=null && wanted.equalsIgnoreCase((String)invoke(characters[index],"b",new Class<?>[0]))) {
                        set(current,"l",index);invoke(current,"a",new Class<?>[0]);return status();
                    }
                    throw new IllegalArgumentException("Requested character is not present");
                }
                default:throw new IllegalArgumentException("Unsupported control operation");
            }
        });
    }

    private JsonElement status() throws Exception {
        Object current=screen();
        JsonObject output=JsonParser.parseString(new StatePrinter.Reader().readScreen(current).toJson()).getAsJsonObject();
        JsonArray directions=new JsonArray();
        for(String direction:MOVEMENT_DIRECTIONS)directions.add(direction);
        output.add("movement_directions",directions);
        JsonArray nativeKeys=new JsonArray();
        for(String name:new String[]{"space","enter","g","x"})nativeKeys.add(name);
        output.add("native_key_input",nativeKeys);output.addProperty("native_click_input",true);
        output.addProperty("native_background_input",backgroundWindow!=null);
        output.addProperty("native_capture",true);
        output.addProperty("native_inn_recovery",true);
        output.addProperty("native_battle_control",true);output.addProperty("native_supplies_control",true);output.addProperty("native_fishing_control",true);
        output.add("window_focused",windowAttribute(0x00020001));
        output.add("window_minimized",windowAttribute(0x00020002));
        output.addProperty("movement_ready","world".equals(output.get("phase").getAsString())
                && current!=null && current.getClass().getName().equals("aj") && movementReady(current));
        if(current!=null && current.getClass().getName().equals("aj") && output.has("main_quest") && !output.get("main_quest").isJsonNull()) {
            JsonObject quest=output.getAsJsonObject("main_quest");
            if(quest.has("target_map") && quest.get("target_map").equals(output.get("map"))) {
                int wanted=questNpc(quest);
                if(wanted>=0) {
                    quest.addProperty("target_npc_id",wanted);
                    quest.addProperty("target_npc_source","bundled_quest_steps");
                }
                for(Object npc:(java.util.List<?>)get(current,"Y")) {
                    if((Integer)invoke(npc,"g",new Class<?>[0])!=wanted)continue;
                    JsonObject position=new JsonObject();
                    position.addProperty("x",(Integer)invoke(npc,"c",new Class<?>[0]));
                    position.addProperty("y",(Integer)invoke(npc,"d",new Class<?>[0]));
                    position.addProperty("entity_id",(Integer)invoke(npc,"b",new Class<?>[0]));
                    position.addProperty("interaction_id",(Integer)invoke(npc,"g",new Class<?>[0]));
                    quest.add("target_npc_position",position);break;
                }
            }
        }
        if(current!=null && current.getClass().getName().equals("aj")) {
            output.add("party",partySnapshot(current));
            output.add("wallet",walletSnapshot(current));
            output.add("inn",innSnapshot(current));
            output.add("supplies",SuppliesControl.snapshot(current));
            output.add("fishing",FishingControl.snapshot(current));
            String map=output.has("map") && !output.get("map").isJsonNull()?output.get("map").getAsString():null;
            JsonObject inns=nearbyInnsSnapshot(current,map);
            output.add("nearby_inns",inns.get("npcs"));output.add("nearby_inns_complete",inns.get("telemetry_complete"));
            JsonObject shops=nearbyShopsSnapshot(current,map);
            output.add("nearby_shops",shops.get("npcs"));output.add("nearby_shops_complete",shops.get("telemetry_complete"));
            JsonObject dialogue=dialogueSnapshot(current);
            if(dialogue!=null)output.add("dialogue",dialogue);
            JsonObject story=storySnapshot(current);
            if(story!=null)output.add("story",story);
            JsonObject battle=battleSnapshot(current);
            if(battle!=null)output.add("battle",battle);
            if(output.has("trace") && output.get("trace").isJsonObject()) {
                Boolean reply=gpsHasReply(current);
                if(reply==null)output.getAsJsonObject("trace").add("has_reply",JsonNull.INSTANCE);
                else output.getAsJsonObject("trace").addProperty("has_reply",reply);
            }
        }
        if(current!=null && current.getClass().getName().equals("a")) {
            output.addProperty("username",((StringBuilder)get(current,"e")).toString());
            output.addProperty("password_length",((StringBuilder)get(current,"f")).length());
            output.addProperty("remember_password",(Boolean)get(current,"n"));
            output.addProperty("server_selection",(Boolean)get(current,"q"));
            output.addProperty("connecting",(Boolean)get(current,"m"));
            output.addProperty("message",(String)get(current,"i"));
            output.add("servers",JSON.toJsonTree(getStatic("b","a")));
        }
        if(current!=null && current.getClass().getName().equals("r")) {
            JsonArray names=new JsonArray();
            for(Object character:(Object[])get(current,"g"))if(character!=null)
                names.add((String)invoke(character,"b",new Class<?>[0]));
            output.add("characters",names);
        }
        return output;
    }

    private static boolean movementReady(Object current) {
        try {
            // C() is the original client's pure world-readiness predicate;
            // transport animations separately suppress movement in aj.f(float).
            return (Boolean)invoke(current,"C",new Class<?>[0]) && get(current,"aC")==null;
        } catch(Exception unavailable) {return false;}
    }

    private static Boolean gpsHasReply(Object current) {
        try {return get(get(current,"cG"),"K")!=null;}
        catch(Exception unavailable) {return null;}
    }

    private static JsonObject battleSnapshot(Object current) {
        Object battle,transition;
        try {battle=get(current,"ba");transition=get(current,"bn");}
        catch(Exception unavailable) {return null;}
        if(battle==null && transition==null)return null;
        JsonObject state=new JsonObject();state.addProperty("active",true);
        state.addProperty("transitioning",transition!=null);
        state.addProperty("result_ready",false);state.addProperty("can_advance",false);
        state.addProperty("submitted",false);state.add("result",JsonNull.INSTANCE);
        state.addProperty("telemetry_complete",battle==null);
        if(battle==null)return state;
        try {
            boolean visible=(Boolean)get(battle,"bD"),submitted=(Boolean)get(battle,"bK");
            Object result=get(battle,"bC");
            String outcome=null;
            if(result!=null)outcome=(Boolean)get(result,"a") ? "victory"
                    : ((Boolean)get(battle,"aw") ? "escape" : "defeat");
            // g.b() sends battle commands during combat. Only a visible
            // result panel makes normal Space a result skip/acknowledgement.
            state.addProperty("result_ready",visible && !submitted);
            state.addProperty("can_advance",visible && !submitted);
            state.addProperty("submitted",submitted);
            if(outcome!=null)state.addProperty("result",outcome);
            state.addProperty("telemetry_complete",true);
        } catch(Exception unavailable) { /* Keep unknown battle input disabled. */ }
        for(java.util.Map.Entry<String,JsonElement> entry:BattleControl.snapshot(current).entrySet())state.add(entry.getKey().equals("telemetry_complete")?"command_telemetry_complete":entry.getKey(),entry.getValue());
        return state;
    }

    private static JsonObject storySnapshot(Object current) {
        Object scene;
        try {scene=get(current,"aX");}
        catch(Exception unavailable) {return null;}
        if(scene==null)return null;
        JsonObject story=new JsonObject();story.addProperty("active",true);
        story.addProperty("can_advance",false);story.addProperty("telemetry_complete",false);
        for(String name:new String[]{"typing","awaiting_choice","choice_count","selected_choice","submitted","script_complete"})
            story.add(name,JsonNull.INSTANCE);
        try {
            int choices=(Integer)get(scene,"v"),selected=(Integer)get(scene,"w");
            boolean submitted=(Boolean)get(scene,"x"),complete=(Boolean)get(scene,"t");
            boolean typing=false;int bubbles=0;
            for(Object slot:(Object[])get(scene,"p")) {
                if(slot==null)continue;
                // at.e.a() is a record accessor. d.a()/at.l()/at.f() are
                // actions and must never be called while sampling status.
                Object bubble=invoke(slot,"a",new Class<?>[0]);
                Object writer=get(bubble,"e");
                typing|=(Boolean)invoke(writer,"b",new Class<?>[0]);
                bubbles++;
            }
            story.addProperty("typing",typing);
            story.addProperty("awaiting_choice",choices>0 && !submitted);
            story.addProperty("choice_count",choices);story.addProperty("selected_choice",selected);
            story.addProperty("submitted",submitted);story.addProperty("script_complete",complete);
            story.addProperty("can_advance",bubbles>0 && !typing && choices==0 && !submitted);
            story.addProperty("telemetry_complete",true);
        } catch(Exception unavailable) {
            // Optional telemetry must not break position/GPS status. Unknown
            // scene details keep can_advance false instead of guessing input.
        }
        return story;
    }

    private static JsonObject dialogueSnapshot(Object current)throws Exception {
        Object bubble=get(current,"aM"),packet=get(current,"aO");
        if(bubble==null || packet==null)return null;
        Object writer=get(bubble,"e");
        // d.a()/aN.e() are ADVANCE actions, not predicates. Only inspect
        // verified aN.b() and fields here; polling must never turn a page.
        boolean typing=(Boolean)invoke(writer,"b",new Class<?>[0]);
        int page=(Integer)get(writer,"c"),count=((java.util.List<?>)get(writer,"a")).size();
        JsonObject dialogue=new JsonObject();
        dialogue.addProperty("entity_id",(Integer)invoke(packet,"a",new Class<?>[0]));
        dialogue.addProperty("text_file",(Integer)invoke(packet,"b",new Class<?>[0]));
        dialogue.addProperty("text_index",(Integer)invoke(packet,"c",new Class<?>[0]));
        dialogue.addProperty("text",(String)invoke(current,"a",new Class<?>[]{packet.getClass()},packet));
        dialogue.addProperty("page_index",page);dialogue.addProperty("page_count",count);
        dialogue.addProperty("typing",typing);dialogue.addProperty("can_advance",!typing);
        dialogue.addProperty("ready_to_close",!typing && page+1>=count);
        return dialogue;
    }

    private static int questNpc(JsonObject quest)throws Exception {
        try(InputStream input=ControlBridge.class.getClassLoader().getResourceAsStream("quests/steps.json")) {
            if(input==null)return -1;
            JsonArray chapters=JsonParser.parseReader(new InputStreamReader(input,StandardCharsets.UTF_8))
                    .getAsJsonObject().getAsJsonArray("chapters");
            int chapter=quest.get("chapter").getAsInt()-1,step=quest.get("step").getAsInt()-1;
            if(chapter<0 || chapter>=chapters.size())return -1;
            JsonArray steps=chapters.get(chapter).getAsJsonArray();
            if(step<0 || step>=steps.size())return -1;
            JsonObject definition=steps.get(step).getAsJsonObject();
            if(!definition.has("npc") || !definition.get("stage").equals(quest.get("target_map")))return -1;
            return definition.get("npc").getAsInt();
        }
    }

    private static Object application() throws Exception {return Class.forName("com.badlogic.gdx.Gdx").getField("app").get(null);}
    private static Object screen() throws Exception {
        Object app=application();if(app==null)return null;
        Object listener=app.getClass().getMethod("getApplicationListener").invoke(app);
        return listener.getClass().getMethod("getScreen").invoke(listener);
    }
    private static void requireScreen(Object screen,String expected) {
        if(screen==null || !screen.getClass().getName().equals(expected))throw new IllegalStateException("Operation is not valid on this screen");
    }
    private static int normalKey(String name) {
        return switch(name) {
            case "space"->32;case "enter"->257;case "g"->71;case "x"->88;
            case "i"->73;case "up"->265;case "down"->264;case "left"->263;case "right"->262;
            default->throw new IllegalArgumentException("Unsupported normal game key");
        };
    }
    private static int uiInputDuration(JsonObject request,int fallback) {
        int milliseconds=request.has("milliseconds")?request.get("milliseconds").getAsInt():fallback;
        if(milliseconds<50 || milliseconds>175)throw new IllegalArgumentException("UI input duration must be 50 to 175 milliseconds");
        return milliseconds;
    }
    private JsonObject guardUiInput(JsonObject request)throws Exception {
        requireScreen(screen(),"aj");JsonObject snapshot=status().getAsJsonObject();
        if(!"world".equals(snapshot.get("phase").getAsString()))throw new IllegalStateException("Map is loading");
        if(request.has("expected_map") && !request.get("expected_map").equals(snapshot.get("map")))
            throw new IllegalStateException("Map changed before UI input");
        if(request.has("expected_pid") && request.get("expected_pid").getAsLong()!=snapshot.get("pid").getAsLong())
            throw new IllegalStateException("Game process changed before UI input");
        guardProcess(request);
        return snapshot;
    }
    private JsonObject guardAutomationInput(JsonObject request)throws Exception {
        if(!request.has("expected_map") || !request.has("expected_pid"))throw new IllegalArgumentException("Expected game identity is required");
        JsonObject snapshot=guardUiInput(request);
        if(request.has("expected_quest")) {
            JsonObject expected=request.getAsJsonObject("expected_quest"),quest=snapshot.getAsJsonObject("main_quest");
            if(quest==null || !expected.get("chapter").equals(quest.get("chapter")) || !expected.get("step").equals(quest.get("step")))
                throw new IllegalStateException("Quest changed before input");
        }
        return snapshot;
    }
    private static boolean completedStory(JsonObject story) {
        return truth(story,"telemetry_complete") && truth(story,"script_complete")
                && falsity(story,"typing") && falsity(story,"awaiting_choice") && falsity(story,"submitted")
                && story.has("choice_count") && !story.get("choice_count").isJsonNull() && story.get("choice_count").getAsInt()==0;
    }
    private static boolean truth(JsonObject object,String field) {return object.has(field) && !object.get(field).isJsonNull() && object.get(field).getAsBoolean();}
    private static boolean falsity(JsonObject object,String field) {return object.has(field) && !object.get(field).isJsonNull() && !object.get(field).getAsBoolean();}
    private static void guardSuppliesBudget(JsonObject request,JsonObject supplies) {
        int count=request.get("quantity").getAsInt(),price=request.get("unit_bits").getAsInt();
        long reserve=request.get("reserve_bits").getAsLong(),budget=request.get("max_total_bits").getAsLong(),total=(long)count*price;
        if(count<1 || count>5 || price<=0 || reserve<5000 || budget<0 || budget>5000 || total>budget)
            throw new IllegalArgumentException("Supplies purchase exceeds its bounds");
        JsonObject wallet=supplies.getAsJsonObject("wallet");
        if(!truth(wallet,"telemetry_complete") || wallet.get("bits").getAsLong()-total<reserve)
            throw new IllegalStateException("Supplies purchase would use the reserve");
        boolean matched=false;
        for(JsonElement value:supplies.getAsJsonObject("shop").getAsJsonArray("offers")) {
            JsonObject offer=value.getAsJsonObject();
            if(offer.get("id").equals(request.get("item_id")) && offer.get("unit_bits").getAsInt()==price)matched=true;
        }
        if(!matched)throw new IllegalStateException("Shop price changed");
    }
    private static JsonObject nearbyShopsSnapshot(Object current,String map) {
        JsonObject result=new JsonObject();JsonArray rows=new JsonArray();result.add("npcs",rows);result.addProperty("telemetry_complete",false);
        try {
            // Merchant identity uses the original bundled map/sprite catalog.
            // Runtime interaction IDs are a separate namespace.
            java.util.Set<String> maps=java.util.Set.of("s245","s246","s250","s251","s425","s426","s500","s501","s660","s661","s760","s761","s931","s932","s957");
            if(maps.contains(map))for(Object npc:(java.util.List<?>)get(current,"Y")) {
                int interaction=((Number)get(npc,"g")).intValue();
                if(!"p038wiza".equals(get(npc,"a")) || interaction<0)continue;
                JsonObject row=new JsonObject();row.addProperty("map",map);row.addProperty("shop_candidate",true);
                row.addProperty("entity_id",((Number)get(npc,"b")).intValue());row.addProperty("interaction_id",interaction);
                int x=((Number)get(npc,"c")).intValue(),y=((Number)get(npc,"d")).intValue();row.addProperty("x",x);row.addProperty("y",y);
                int radius=((Number)get(npc,"f")).intValue();
                int px=(int)Math.floor(((Number)get(current,"ax")).doubleValue()),py=(int)Math.floor(((Number)get(current,"ay")).doubleValue()),facing=((Number)get(current,"az")).intValue();
                Method check=Class.forName("bF").getDeclaredMethod("a",int.class,int.class,int.class,int.class,int.class,int.class);check.setAccessible(true);
                row.addProperty("can_interact",(Boolean)check.invoke(null,px,py,facing,x,y,radius));JsonArray facings=new JsonArray();
                for(int f=0;f<8;f++)if((Boolean)check.invoke(null,px,py,f,x,y,radius))facings.add(f);
                row.add("interaction_facings",facings);rows.add(row);
            }
            result.addProperty("telemetry_complete",true);
        }catch(Exception unknown){}
        return result;
    }
    private static JsonObject nearbyInnsSnapshot(Object current,String map) {
        JsonObject output=new JsonObject();JsonArray npcs=new JsonArray();
        output.add("npcs",npcs);output.addProperty("telemetry_complete",false);
        if(map==null)return output;
        // These maps also bundle quest NPC121 with the same sprite. Expose
        // candidates without assigning an inn identity; only an actual server
        // inn offer can verify that a normal interaction reached the service.
        boolean ambiguous=map.equals("s470") || map.equals("s471");
        try {
            java.util.List<?> live=(java.util.List<?>)get(current,"Y");boolean complete=true;
            if(INN_MAPS.contains(map))for(Object npc:live) {
                try {
                    // bg.a is the sprite key; bg.g is the server's current
                    // interaction ID used by aj.p(), not the bundled NPC ID.
                    int interaction=((Number)get(npc,"g")).intValue();
                    if(!"p039tail".equals(get(npc,"a")) || interaction==-1)continue;
                    JsonObject row=new JsonObject();row.addProperty("map",map);
                    if(ambiguous) {
                        row.add("logical_id",JsonNull.INSTANCE);row.addProperty("inn_candidate",true);
                        row.addProperty("source","inn_sprite_candidate_requires_offer");
                    }else {
                        row.addProperty("logical_id",20);row.addProperty("source","bundled_inn_catalog");
                    }
                    row.addProperty("interaction_id",interaction);
                    row.addProperty("entity_id",((Number)get(npc,"b")).intValue());
                    int x=((Number)get(npc,"c")).intValue(),y=((Number)get(npc,"d")).intValue();
                    row.addProperty("x",x);row.addProperty("y",y);
                    int radius=((Number)get(npc,"f")).intValue();
                    int playerX=(int)Math.floor(((Number)get(current,"ax")).doubleValue());
                    int playerY=(int)Math.floor(((Number)get(current,"ay")).doubleValue());
                    int facing=((Number)get(current,"az")).intValue();
                    // Exact pure hit test used by aj.p() before normal talk.
                    // It checks a facing-directed segment against the NPC's
                    // rectangular interaction area, not a fixed radial range.
                    Method predicate=Class.forName("bF").getMethod("a",int.class,int.class,int.class,int.class,int.class,int.class);
                    JsonArray facings=new JsonArray();
                    for(int candidate=0;candidate<8;candidate++)
                        if((Boolean)predicate.invoke(null,playerX,playerY,candidate,x,y,radius))facings.add(candidate);
                    row.addProperty("interaction_radius",radius);row.add("interaction_facings",facings);
                    row.addProperty("can_interact",(Boolean)predicate.invoke(null,playerX,playerY,facing,x,y,radius));
                    npcs.add(row);
                }catch(Exception unavailable){complete=false;}
            }
            output.addProperty("telemetry_complete",complete);
        }catch(Exception unavailable){/* Missing live NPCs never invent coordinates. */}
        return output;
    }
    private static JsonObject partySnapshot(Object current) {
        JsonObject output=new JsonObject();JsonArray members=new JsonArray();
        output.addProperty("source","server_party_snapshot");output.addProperty("telemetry_complete",false);
        output.add("count",JsonNull.INSTANCE);output.add("any_fainted",JsonNull.INSTANCE);output.add("members",members);
        try {
            Object snapshot=get(current,"bu");if(snapshot==null)return output;
            java.util.List<?> party=(java.util.List<?>)get(snapshot,"d");
            boolean complete=true,anyFainted=false;int slot=0;
            for(Object member:party) {
                JsonObject row=new JsonObject();row.addProperty("slot",slot++);row.addProperty("telemetry_complete",false);
                for(String field:new String[]{"id","name","hp","max_hp","fainted"})row.add(field,JsonNull.INSTANCE);
                try {
                    // bI.bm is the complete party row used by G's party menu:
                    // a=Digimon ID, e=current HP, g=bw stats whose a=max HP.
                    int id=((Number)get(member,"a")).intValue(),hp=((Number)get(member,"e")).intValue();
                    int maximum=((Number)get(get(member,"g"),"a")).intValue();
                    row.addProperty("id",id);row.addProperty("hp",hp);row.addProperty("max_hp",maximum);
                    String name=partyName(current,id);if(name!=null)row.addProperty("name",name);
                    if(hp<0 || maximum<=0 || hp>maximum)complete=false;
                    else {
                        row.addProperty("fainted",hp==0);row.addProperty("telemetry_complete",true);
                        anyFainted|=hp==0;
                    }
                }catch(Exception unavailable){complete=false;}
                members.add(row);
            }
            output.addProperty("count",members.size());output.addProperty("telemetry_complete",complete);
            if(complete)output.addProperty("any_fainted",anyFainted);
        }catch(Exception unavailable){/* Unknown party never means all healthy. */}
        return output;
    }
    private static String partyName(Object current,int id) {
        try {
            Object game=get(current,"M");
            // F.g resolves nicknames before species names. Read only existing
            // caches, never call F.b/F.g (which may lazily load asset files).
            for(String field:new String[]{"x","H"}) {
                Object names=get(game,field);
                if(names instanceof java.util.Map<?,?> map) {
                    Object name=map.get(id);
                    if(name instanceof String text && !text.isEmpty())return text;
                }
            }
        }catch(Exception unavailable){/* An uncached name remains unknown. */}
        return null;
    }
    private static JsonObject walletSnapshot(Object current) {
        JsonObject output=new JsonObject();output.addProperty("telemetry_complete",false);
        output.add("bits",JsonNull.INSTANCE);output.add("cash",JsonNull.INSTANCE);
        try {
            Object wallet=get(current,"bt");
            int bits=((Number)get(wallet,"a")).intValue(),cash=((Number)get(wallet,"b")).intValue();
            if(bits<0 || cash<0)return output;
            // Original aj.i(P) and G inventory footer label these BIT / Cash.
            output.addProperty("bits",bits);output.addProperty("cash",cash);output.addProperty("telemetry_complete",true);
        }catch(Exception unavailable){/* Optional wallet fields must not break status. */}
        return output;
    }
    private static JsonObject innSnapshot(Object current) {
        JsonObject output=new JsonObject();output.addProperty("active",false);
        output.addProperty("telemetry_complete",false);output.addProperty("can_confirm",false);output.addProperty("submitted",false);
        for(String field:new String[]{"state","selected_option","cost_bits","party_count","name_index"})output.add(field,JsonNull.INSTANCE);
        try {
            Object inn=get(current,"bz");
            if(inn==null){output.addProperty("telemetry_complete",true);return output;}
            output.addProperty("active",true);
            // U$a's static initializer assigns these exact ordinals to its
            // a..e fields. Runtime Enum.name strings are separately obfuscated.
            String state=switch(((Enum<?>)get(inn,"d")).ordinal()) {
                case 0->"offer";case 1->"submitted";case 2->"rejected";
                case 3->"resting";case 4->"closed";default->throw new IllegalStateException("Unknown inn state");
            };
            Object offer=get(inn,"c");int selected=((Number)get(inn,"e")).intValue();
            int cost=((Number)get(offer,"d")).intValue(),count=((Number)get(offer,"c")).intValue(),name=((Number)get(offer,"a")).intValue();
            output.addProperty("state",state);output.addProperty("selected_option",selected);
            output.addProperty("cost_bits",cost);output.addProperty("party_count",count);output.addProperty("name_index",name);
            if(cost<0 || count<0 || selected<0 || selected>1)return output;
            output.addProperty("active",!state.equals("closed"));output.addProperty("telemetry_complete",true);
            output.addProperty("submitted",state.equals("submitted") || state.equals("resting"));
            JsonObject wallet=walletSnapshot(current);
            output.addProperty("can_confirm",state.equals("offer") && selected==0
                    && wallet.get("telemetry_complete").getAsBoolean() && wallet.get("bits").getAsInt()>=cost);
        }catch(Exception unavailable){/* Incomplete inn state never authorizes payment. */}
        return output;
    }
    private static void guardProcess(JsonObject request) {
        if(request.has("expected_pid") && request.get("expected_pid").getAsLong()!=ProcessHandle.current().pid())
            throw new IllegalStateException("Game process changed before native operation");
    }
    private static JsonElement windowAttribute(int attribute) {
        try {
            int value=(Integer)Class.forName("org.lwjgl.glfw.GLFW")
                    .getMethod("glfwGetWindowAttrib",long.class,int.class).invoke(null,windowHandle(),attribute);
            return new JsonPrimitive(value==1);
        }catch(Exception unavailable){return JsonNull.INSTANCE;}
    }
    private void installBackgroundInput() throws Exception {
        Object input=Class.forName("com.badlogic.gdx.Gdx").getField("input").get(null);
        Object window=get(input,"window");
        if(backgroundWindow==window)return;
        Object graphics=Class.forName("com.badlogic.gdx.Gdx").getField("graphics").get(null);
        // The shipped LWJGL backend renders continuous windows while minimized,
        // but skips input.update/prepareNext. Its window runnables execute before
        // render, so drain callbacks there only while the backend skips them.
        graphics.getClass().getMethod("setContinuousRendering",boolean.class).invoke(graphics,true);
        Method post=window.getClass().getMethod("postRunnable",Runnable.class);
        Runnable pump=new Runnable(){public void run(){
            if(closed || backgroundWindow!=window)return;
            try {
                if((Boolean)get(window,"iconified")) {
                    invoke(input,"update",new Class<?>[0]);
                    long consumedGeneration=nativeInputGeneration;
                    // Clear one-frame flags after rendering, as the ordinary
                    // backend does. A later native callback in the app queue
                    // belongs to the next frame and must retain its flags.
                    Object app=application();
                    app.getClass().getMethod("postRunnable",Runnable.class).invoke(app,(Runnable)()->{
                        try {
                            if(nativeInputGeneration==consumedGeneration && (Boolean)get(window,"iconified"))
                                invoke(input,"prepareNext",new Class<?>[0]);
                        }catch(Exception unavailable){backgroundWindow=null;}
                    });
                }
                post.invoke(window,this);
            }catch(Exception unavailable){backgroundWindow=null;}
        }};
        backgroundWindow=window;
        try{post.invoke(window,pump);}catch(Exception error){backgroundWindow=null;throw error;}
    }
    private JsonObject capture(JsonObject request)throws Exception {
        guardProcess(request);
        Object graphics=Class.forName("com.badlogic.gdx.Gdx").getField("graphics").get(null);
        int width=(Integer)graphics.getClass().getMethod("getBackBufferWidth").invoke(graphics);
        int height=(Integer)graphics.getClass().getMethod("getBackBufferHeight").invoke(graphics);
        if(width<=0 || height<=0 || width>8192 || height>8192 || (long)width*height>16777216)
            throw new IllegalStateException("No valid game framebuffer dimensions");
        // Application postRunnable executes after window.update's render/swap.
        // Read the completed front buffer, never the undefined next back buffer.
        Class<?> gl=Class.forName("org.lwjgl.opengl.GL11");
        Method readBuffer=gl.getMethod("glReadBuffer",int.class);
        int previous=(Integer)gl.getMethod("glGetInteger",int.class).invoke(null,0x0C02);
        byte[] pixels;
        try {
            readBuffer.invoke(null,0x0404); // GL_FRONT
            pixels=(byte[])Class.forName("com.badlogic.gdx.utils.ScreenUtils")
                    .getMethod("getFrameBufferPixels",int.class,int.class,int.class,int.class,boolean.class)
                    .invoke(null,0,0,width,height,true);
        }finally{readBuffer.invoke(null,previous);}
        if(pixels.length!=(long)width*height*4)throw new IllegalStateException("Incomplete game framebuffer");
        java.awt.image.BufferedImage image=new java.awt.image.BufferedImage(width,height,java.awt.image.BufferedImage.TYPE_INT_ARGB);
        int[] argb=new int[width*height];
        for(int index=0,offset=0;index<argb.length;index++,offset+=4)
            argb[index]=((pixels[offset+3]&255)<<24)|((pixels[offset]&255)<<16)|((pixels[offset+1]&255)<<8)|(pixels[offset+2]&255);
        image.setRGB(0,0,width,height,argb,0,width);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        if(!javax.imageio.ImageIO.write(image,"png",bytes))throw new IOException("PNG encoder unavailable");
        JsonObject result=new JsonObject();result.addProperty("png_base64",java.util.Base64.getEncoder().encodeToString(bytes.toByteArray()));
        result.addProperty("width",width);result.addProperty("height",height);result.addProperty("pid",ProcessHandle.current().pid());return result;
    }
    private static void mouse(Object input,int x,int y,int action)throws Exception {
        // Follow the backend's normal event path: the UI polls getX/getY each
        // frame, so calling InputProcessor.touchDown alone loses the position.
        // These callbacks update only this game's input state/event queue; they
        // never move the host pointer or generate a desktop mouse event.
        nativeInputGeneration++;
        Object cursor=get(input,"cursorPosCallback"),button=get(input,"mouseButtonCallback");
        Method position=cursor.getClass().getMethod("invoke",long.class,double.class,double.class);
        Method click=button.getClass().getMethod("invoke",long.class,int.class,int.class,int.class);
        position.setAccessible(true);click.setAccessible(true);
        long handle=windowHandle();
        try {position.invoke(cursor,handle,(double)x,(double)y);}
        finally {
            // Even a failed cursor update must not strand a previously queued
            // mouse-down. Release remains on the uncancellable render queue.
            if(action==0)click.invoke(button,handle,0,0,0);
        }
        if(action==1)click.invoke(button,handle,0,1,0);
    }
    private static int[] movementKeys(String direction) {
        return switch(direction) {
            case "up"->new int[]{265};case "down"->new int[]{264};
            case "left"->new int[]{263};case "right"->new int[]{262};
            case "up_left"->new int[]{265,263};case "up_right"->new int[]{265,262};
            case "down_left"->new int[]{264,263};case "down_right"->new int[]{264,262};
            default->throw new IllegalArgumentException("Unsupported movement direction");
        };
    }
    private static void releaseKeys(int[] keys)throws Exception {
        Exception failure=null;
        for(int key:keys) {
            try {key(key,0);}
            catch(Exception error) {
                if(failure==null)failure=error;
                else failure.addSuppressed(error);
            }
        }
        if(failure!=null)throw failure;
    }
    private static void key(int key,int action) throws Exception {
        nativeInputGeneration++;
        Object input=Class.forName("com.badlogic.gdx.Gdx").getField("input").get(null);
        long handle=windowHandle();
        invoke(input,"keyCallback",new Class<?>[]{long.class,int.class,int.class,int.class,int.class},handle,key,0,action,0);
    }
    private static long windowHandle() throws Exception {
        Object input=Class.forName("com.badlogic.gdx.Gdx").getField("input").get(null);
        Object window=get(input,"window");
        return (Long)window.getClass().getMethod("getWindowHandle").invoke(window);
    }
    private static Object getStatic(String type,String field)throws Exception {Field f=Class.forName(type).getDeclaredField(field);f.setAccessible(true);return f.get(null);}
    private static Object get(Object object,String field)throws Exception {Field f=object.getClass().getDeclaredField(field);f.setAccessible(true);return f.get(object);}
    private static void set(Object object,String field,Object value)throws Exception {Field f=object.getClass().getDeclaredField(field);f.setAccessible(true);f.set(object,value);}
    private static Object invoke(Object object,String name,Class<?>[] types,Object...args)throws Exception {
        Method method=object.getClass().getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(object,args);
    }
    private interface CheckedAction {JsonElement run()throws Exception;}
    private JsonElement onRender(CheckedAction action)throws Exception {
        return onRender(action,true);
    }
    private JsonElement onRender(CheckedAction action,boolean cancelOnTimeout)throws Exception {
        Object app=application();if(app==null)throw new IllegalStateException("Game is still starting");
        CompletableFuture<JsonElement> result=new CompletableFuture<>();
        app.getClass().getMethod("postRunnable",Runnable.class).invoke(app,(Runnable)()->{
            if(result.isCancelled())return;
            try {
                try{installBackgroundInput();}catch(Exception unavailable){backgroundWindow=null;}
                result.complete(action.run());}catch(Throwable error){result.completeExceptionally(error);}
        });
        try {return result.get(8,TimeUnit.SECONDS);}
        catch(TimeoutException error){if(cancelOnTimeout)result.cancel(false);throw error;}
    }
    @Override public void close()throws IOException {
        closed=true;server.close();thread.interrupt();Files.deleteIfExists(path);
    }
}
