#!/usr/bin/env python3
"""A delayed render must still execute a queued key release after timeout."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SOURCES={
'com/badlogic/gdx/Gdx.java':'''package com.badlogic.gdx; public class Gdx { public static final fake.App app=new fake.App(); }''',
'fake/App.java':'''package fake; public class App {public volatile Runnable queued; public void postRunnable(Runnable r){queued=r;} }''',
'dw3/linux/ReleaseCheck.java':'''package dw3.linux;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicBoolean;
public class ReleaseCheck {
 public static void main(String[] args)throws Exception {
  Constructor<?> ctor=ControlBridge.class.getDeclaredConstructor(Path.class);ctor.setAccessible(true);
  try(ControlBridge bridge=(ControlBridge)ctor.newInstance(Path.of(args[0]))) {
   Class<?> action=Class.forName("dw3.linux.ControlBridge$CheckedAction");
   AtomicBoolean released=new AtomicBoolean();
   Object callback=Proxy.newProxyInstance(action.getClassLoader(),new Class<?>[]{action},(p,m,a)->{released.set(true);return com.google.gson.JsonNull.INSTANCE;});
   Method render;
   try {render=ControlBridge.class.getDeclaredMethod("onRender",action,boolean.class);}
   catch(NoSuchMethodException e){throw new AssertionError("No uncancellable render cleanup support",e);}
   render.setAccessible(true);
   try {render.invoke(bridge,callback,false);throw new AssertionError("Expected timeout");}
   catch(InvocationTargetException e){if(!(e.getCause() instanceof java.util.concurrent.TimeoutException))throw e;}
   com.badlogic.gdx.Gdx.app.queued.run();
   if(!released.get())throw new AssertionError("Delayed key release was discarded after timeout");
   System.out.println("Delayed release executed after timeout.");
  }
 }
}'''
}
class ReleaseTests(unittest.TestCase):
 def test_delayed_release_survives_timeout(self):
  with tempfile.TemporaryDirectory(prefix='dw3-release-') as td:
   files=[]
   for name,source in SOURCES.items():
    p=Path(td)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source);files.append(str(p))
   cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
   subprocess.run(['javac','--release','17','-cp',cp,'-d',td,*files],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',f'{td}:{cp}','dw3.linux.ReleaseCheck',td+'/control.sock'],capture_output=True,text=True,timeout=12)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('Delayed release executed',result.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
