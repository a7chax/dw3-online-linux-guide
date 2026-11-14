#!/usr/bin/env python3
"""Native UI inputs use only isolated libGDX/GLFW callbacks, never desktop APIs."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SOURCES={
'com/badlogic/gdx/Gdx.java':'''package com.badlogic.gdx; public class Gdx {public static fake.App app=new fake.App();public static fake.Input input=new fake.Input();public static fake.Graphics graphics=new fake.Graphics();}''',
'fake/State.java':'''package fake; public class State {public static String phase="world",map="s370";public static int focused=1,minimized=0;public static Object screen,processor=new Processor();}''',
'fake/App.java':'''package fake; public class App {public boolean delayed,queueApp;public java.util.List<Runnable> afterFrame=new java.util.ArrayList<>();public Runnable queued;public void postRunnable(Runnable r){if(delayed)queued=r;else if(queueApp)afterFrame.add(r);else r.run();}public void flushFrame(){var copy=new java.util.ArrayList<>(afterFrame);afterFrame.clear();for(Runnable r:copy)r.run();}public Game getApplicationListener(){return new Game();}public static class Game{public Object getScreen(){return State.screen;}}}''',
'fake/Input.java':'''package fake; import java.util.*;public class Input {private Window window=new Window();public List<String> calls=new ArrayList<>(),mouseCalls=new ArrayList<>();public boolean failDown,failMouseDown;public int mouseX,mouseY;private Cursor cursorPosCallback=new Cursor();private Mouse mouseButtonCallback=new Mouse();public class Cursor{public void invoke(long window,double x,double y){mouseX=(int)x;mouseY=(int)y;mouseCalls.add("cursor:"+mouseX+":"+mouseY);}}public class Mouse{public void invoke(long window,int button,int action,int mods){mouseCalls.add("button:"+button+":"+action);fake.Processor processor=(fake.Processor)fake.State.processor;if(action==1){processor.touchDown(mouseX,mouseY,0,button);if(failMouseDown)throw new IllegalStateException("fixture mouse failure");}else processor.touchUp(mouseX,mouseY,0,button);}}public void keyCallback(long w,int key,int scan,int action,int mods){calls.add(key+":"+action);if(action==1)justKey=true;if(action==1&&failDown)throw new IllegalStateException("fixture press failure");}public Object getInputProcessor(){return State.processor;}public boolean justKey,sawJustKey;public int updates,prepares;public void update(){updates++;sawJustKey=justKey;}public void prepareNext(){prepares++;justKey=false;}public Window testWindow(){return window;}public static class Window{public boolean iconified;public Runnable pending;public long getWindowHandle(){return 123;}public void postRunnable(Runnable r){pending=r;}public void frame(){Runnable r=pending;pending=null;if(r!=null)r.run();}}}''',
'fake/Graphics.java':'''package fake; public class Graphics {public int getWidth(){return 640;}public int getHeight(){return 480;}public int backWidth=2;public int getBackBufferWidth(){return backWidth;}public int getBackBufferHeight(){return 2;}public boolean continuous;public void setContinuousRendering(boolean value){continuous=value;}}''',
'fake/Processor.java':'''package fake;import java.util.*;public class Processor{public List<String> calls=new ArrayList<>();public boolean popupClosed;public boolean touchDown(int x,int y,int p,int b){calls.add("down:"+x+":"+y+":"+p+":"+b);popupClosed=com.badlogic.gdx.Gdx.input.mouseX==x&&com.badlogic.gdx.Gdx.input.mouseY==y;return true;}public boolean touchUp(int x,int y,int p,int b){calls.add("up:"+x+":"+y+":"+p+":"+b);return true;}}''',
'org/lwjgl/glfw/GLFW.java':'''package org.lwjgl.glfw;public class GLFW {public static int glfwGetWindowAttrib(long h,int a){return a==0x00020001?fake.State.focused:fake.State.minimized;}}''',
'org/lwjgl/opengl/GL11.java':'''package org.lwjgl.opengl;public class GL11{public static int buffer=1029;public static int glGetInteger(int key){return buffer;}public static void glReadBuffer(int value){buffer=value;}}''',
'com/badlogic/gdx/utils/ScreenUtils.java':'''package com.badlogic.gdx.utils;public class ScreenUtils{public static boolean fail;public static byte[] getFrameBufferPixels(int x,int y,int w,int h,boolean flip){if(fail)throw new IllegalStateException("fixture capture failure");if(!flip||org.lwjgl.opengl.GL11.buffer!=1028)throw new AssertionError("Expected completed front buffer and top-down pixels");return new byte[]{(byte)255,0,0,(byte)255,0,(byte)255,0,(byte)255,0,0,(byte)255,(byte)255,0,0,0,(byte)255};}}''',
'aj.java':'''public class aj {private Object aM,aO,aX,aC,ba,bn;boolean C(){return true;}}''',
'dw3/linux/StatePrinter.java':'''package dw3.linux;public class StatePrinter{static class Reader{Snapshot readScreen(Object o){return new Snapshot();}}static class Snapshot{String toJson(){return "{\\\"phase\\\":\\\""+fake.State.phase+"\\\",\\\"map\\\":\\\""+fake.State.map+"\\\",\\\"pid\\\":"+ProcessHandle.current().pid()+",\\\"main_quest\\\":null,\\\"trace\\\":null}";}}}''',
'NativeKeyCheck.java':'''import java.lang.reflect.*;import java.util.*;import com.google.gson.*;
public class NativeKeyCheck{
 static Method dispatch;static Object bridge;
 static JsonObject call(String json)throws Exception{return (JsonObject)dispatch.invoke(bridge,JsonParser.parseString(json).getAsJsonObject());}
 static void rejects(String json,Class<?> expected)throws Exception{try{call(json);throw new AssertionError("Accepted invalid input");}catch(InvocationTargetException error){Throwable cause=error.getCause();while(cause instanceof java.util.concurrent.ExecutionException)cause=cause.getCause();if(!expected.isInstance(cause))throw error;}}
 public static void main(String[] args)throws Exception{
  Class<?> type=Class.forName("dw3.linux.ControlBridge"),unsafeClass=Class.forName("sun.misc.Unsafe");Field f=unsafeClass.getDeclaredField("theUnsafe");f.setAccessible(true);bridge=unsafeClass.getMethod("allocateInstance",Class.class).invoke(f.get(null),type);
  fake.State.screen=Class.forName("aj").getConstructor().newInstance();dispatch=type.getDeclaredMethod("dispatch",JsonObject.class);dispatch.setAccessible(true);
  Method mapping;try{mapping=type.getDeclaredMethod("normalKey",String.class);}catch(NoSuchMethodException error){throw new AssertionError("Missing native game-key input",error);}mapping.setAccessible(true);
  String[] names={"space","enter","g","x"};int[] codes={32,257,71,88};
  for(int i=0;i<names.length;i++){
   if((Integer)mapping.invoke(null,names[i])!=codes[i])throw new AssertionError("Wrong key mapping");
   com.badlogic.gdx.Gdx.input.calls.clear();JsonObject result=call("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\""+names[i]+"\\\",\\\"milliseconds\\\":50,\\\"expected_map\\\":\\\"s370\\\",\\\"expected_pid\\\":"+ProcessHandle.current().pid()+"}");
   if(!result.has("before")||!result.has("after"))throw new AssertionError("No verified snapshots");
   if(!com.badlogic.gdx.Gdx.input.calls.equals(List.of(codes[i]+":1",codes[i]+":0")))throw new AssertionError(com.badlogic.gdx.Gdx.input.calls);
   if(result.getAsJsonObject("after").getAsJsonArray("native_key_input").size()!=4||!result.getAsJsonObject("after").get("native_click_input").getAsBoolean())throw new AssertionError("Capabilities missing");
  }
  rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"a\\\"}",IllegalArgumentException.class);
  rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\",\\\"milliseconds\\\":500}",IllegalArgumentException.class);
  rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\",\\\"expected_map\\\":\\\"wrong\\\"}",java.lang.IllegalStateException.class);
  rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\",\\\"expected_pid\\\":-1}",java.lang.IllegalStateException.class);
  fake.State.focused=0;/*old focus rejection removed*/call("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\"}");fake.State.focused=1;
  fake.State.focused=0;fake.State.minimized=1;
  JsonObject background=call("{\\\"op\\\":\\\"status\\\"}");
  if(!background.get("native_background_input").getAsBoolean()||!background.get("native_capture").getAsBoolean()||background.get("window_focused").getAsBoolean()||!background.get("window_minimized").getAsBoolean())throw new AssertionError("Background/window telemetry mismatch");
  com.badlogic.gdx.Gdx.input.testWindow().iconified=true;com.badlogic.gdx.Gdx.input.justKey=true;com.badlogic.gdx.Gdx.input.testWindow().frame();
  if(!com.badlogic.gdx.Gdx.input.sawJustKey)throw new AssertionError("Minimized prepareNext cleared new input before frame consumed it");
  if(com.badlogic.gdx.Gdx.input.updates!=1||com.badlogic.gdx.Gdx.input.prepares!=1||!com.badlogic.gdx.Gdx.graphics.continuous||com.badlogic.gdx.Gdx.input.testWindow().pending==null)throw new AssertionError("Minimized input not pumped and requeued");
  com.badlogic.gdx.Gdx.input.testWindow().iconified=false;com.badlogic.gdx.Gdx.input.testWindow().frame();
  if(com.badlogic.gdx.Gdx.input.updates!=1)throw new AssertionError("Input double drained while visible");
  JsonObject capture=call("{\\\"op\\\":\\\"capture\\\",\\\"expected_pid\\\":"+ProcessHandle.current().pid()+"}");
  if(capture.get("width").getAsInt()!=2||capture.get("height").getAsInt()!=2||capture.get("pid").getAsLong()!=ProcessHandle.current().pid())throw new AssertionError("Capture metadata mismatch");
  java.awt.image.BufferedImage image=javax.imageio.ImageIO.read(new java.io.ByteArrayInputStream(java.util.Base64.getDecoder().decode(capture.get("png_base64").getAsString())));
  if(image.getRGB(0,0)!=0xffff0000||image.getRGB(1,0)!=0xff00ff00||image.getRGB(0,1)!=0xff0000ff||org.lwjgl.opengl.GL11.buffer!=1029)throw new AssertionError("Capture pixels or GL state mismatch");
  rejects("{\\\"op\\\":\\\"capture\\\",\\\"expected_pid\\\":-1}",java.lang.IllegalStateException.class);
  rejects("{\\\"op\\\":\\\"move\\\",\\\"direction\\\":\\\"down_right\\\",\\\"expected_pid\\\":-1}",java.lang.IllegalStateException.class);
  call("{\\\"op\\\":\\\"move\\\",\\\"direction\\\":\\\"down_right\\\",\\\"milliseconds\\\":50,\\\"expected_pid\\\":"+ProcessHandle.current().pid()+"}");
  com.badlogic.gdx.Gdx.graphics.backWidth=0;
  rejects("{\\\"op\\\":\\\"capture\\\"}",java.lang.IllegalStateException.class);com.badlogic.gdx.Gdx.graphics.backWidth=2;
  com.badlogic.gdx.utils.ScreenUtils.fail=true;
  rejects("{\\\"op\\\":\\\"capture\\\"}",java.lang.reflect.InvocationTargetException.class);com.badlogic.gdx.utils.ScreenUtils.fail=false;
  if(org.lwjgl.opengl.GL11.buffer!=1029)throw new AssertionError("Failed readback changed GL read buffer");
  fake.State.focused=1;fake.State.minimized=0;
  fake.State.phase="loading_map";rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\"}",java.lang.IllegalStateException.class);fake.State.phase="world";
  com.badlogic.gdx.Gdx.input.calls.clear();com.badlogic.gdx.Gdx.input.failDown=true;
  rejects("{\\\"op\\\":\\\"press_key\\\",\\\"key\\\":\\\"space\\\"}",java.lang.reflect.InvocationTargetException.class);
  if(!com.badlogic.gdx.Gdx.input.calls.equals(List.of("32:1","32:0")))throw new AssertionError("Press failure left key held");com.badlogic.gdx.Gdx.input.failDown=false;
  call("{\\\"op\\\":\\\"click\\\",\\\"x\\\":12,\\\"y\\\":34,\\\"milliseconds\\\":50,\\\"expected_map\\\":\\\"s370\\\"}");
  if(!((fake.Processor)fake.State.processor).calls.equals(List.of("down:12:34:0:0","up:12:34:0:0")))throw new AssertionError("Click callback missing");
  if(!((fake.Processor)fake.State.processor).popupClosed)throw new AssertionError("Queued click did not update the polled game cursor");
  if(!com.badlogic.gdx.Gdx.input.mouseCalls.equals(List.of("cursor:12:34","button:0:1","cursor:12:34","button:0:0")))throw new AssertionError("Backend cursor/button callback order incorrect");
  rejects("{\\\"op\\\":\\\"click\\\",\\\"x\\\":640,\\\"y\\\":34}",IllegalArgumentException.class);
  com.badlogic.gdx.Gdx.app.queueApp=true;com.badlogic.gdx.Gdx.input.testWindow().iconified=true;
  com.badlogic.gdx.Gdx.input.testWindow().frame();
  Method key=type.getDeclaredMethod("key",int.class,int.class);key.setAccessible(true);key.invoke(null,32,1);
  com.badlogic.gdx.Gdx.app.flushFrame();
  if(!com.badlogic.gdx.Gdx.input.justKey)throw new AssertionError("After-frame cleanup discarded next-frame callback flags");
  com.badlogic.gdx.Gdx.input.testWindow().frame();com.badlogic.gdx.Gdx.app.flushFrame();
  if(!com.badlogic.gdx.Gdx.input.sawJustKey||com.badlogic.gdx.Gdx.input.justKey)throw new AssertionError("Next frame did not consume then clear callback flags");
  com.badlogic.gdx.Gdx.app.queueApp=false;
  // The same uncancellable render queue used by press_key finally must retain
  // key-up even when its caller times out before rendering resumes.
  Class<?> action=Class.forName("dw3.linux.ControlBridge$CheckedAction");
  Object release=Proxy.newProxyInstance(action.getClassLoader(),new Class<?>[]{action},(p,m,a)->{com.badlogic.gdx.Gdx.input.keyCallback(123,32,0,0,0);return JsonNull.INSTANCE;});
  Method render=type.getDeclaredMethod("onRender",action,boolean.class);render.setAccessible(true);com.badlogic.gdx.Gdx.app.delayed=true;
  try{render.invoke(bridge,release,false);throw new AssertionError("Expected delayed timeout");}catch(InvocationTargetException error){if(!(error.getCause() instanceof java.util.concurrent.TimeoutException))throw error;}
  com.badlogic.gdx.Gdx.input.calls.clear();com.badlogic.gdx.Gdx.app.queued.run();
  if(!com.badlogic.gdx.Gdx.input.calls.equals(List.of("32:0")))throw new AssertionError("Timed-out cleanup was discarded");
  System.out.println("Native keys, clicks, guards and delayed cleanup verified.");
 }
}'''
}
class NativeKeyTests(unittest.TestCase):
 def test_native_callbacks_allowlist_guards_and_release(self):
  with tempfile.TemporaryDirectory(prefix='dw3-native-input-') as directory:
   files=[]
   for name,source in SOURCES.items():
    path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source);files.append(str(path))
   cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
   subprocess.run(['javac','--release','17','-cp',cp,'-d',directory,str(ROOT/'linux/native/src/dw3/linux/ControlBridge.java'),*files],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',directory+':'+cp,'NativeKeyCheck'],capture_output=True,text=True,timeout=16)
   self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Native keys, clicks, guards and delayed cleanup verified.',result.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
