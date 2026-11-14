#!/usr/bin/env python3
"""Exercise direction mapping and key cleanup with isolated input stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    'com/badlogic/gdx/Gdx.java': '''package com.badlogic.gdx;
public class Gdx {public static fake.Input input=new fake.Input();public static Object app=null;}''',
    'fake/Input.java': '''package fake;
import java.util.*;
public class Input {
 private Window window=new Window();
 public List<String> calls=new ArrayList<>();public int failRelease=-1;
 public void keyCallback(long window,int key,int scan,int action,int mods){
  calls.add(key+":"+action);
  if(action==0 && key==failRelease)throw new IllegalStateException("fixture release failure");
 }
 public static class Window {public long getWindowHandle(){return 123;}}
}''',
    'DiagonalCheck.java': '''import java.lang.reflect.*;import java.util.*;
public class DiagonalCheck {
 public static void main(String[] args)throws Exception {
  Class<?> bridge=Class.forName("dw3.linux.ControlBridge");Method mapping;
  try{mapping=bridge.getDeclaredMethod("movementKeys",String.class);}
  catch(NoSuchMethodException e){throw new AssertionError("Missing eight-direction movement mapping",e);}
  mapping.setAccessible(true);
  Map<String,int[]> expected=new LinkedHashMap<>();
  expected.put("up",new int[]{265});expected.put("down",new int[]{264});
  expected.put("left",new int[]{263});expected.put("right",new int[]{262});
  expected.put("up_left",new int[]{265,263});expected.put("up_right",new int[]{265,262});
  expected.put("down_left",new int[]{264,263});expected.put("down_right",new int[]{264,262});
  for(var entry:expected.entrySet()){
   int[] keys=(int[])mapping.invoke(null,entry.getKey());
   if(!Arrays.equals(keys,entry.getValue()))throw new AssertionError(entry.getKey()+Arrays.toString(keys));
  }
  try{mapping.invoke(null,"sideways");throw new AssertionError("Unknown direction accepted");}
  catch(InvocationTargetException e){if(!(e.getCause() instanceof IllegalArgumentException))throw e;}
  Field supported=bridge.getDeclaredField("MOVEMENT_DIRECTIONS");supported.setAccessible(true);
  if(!new HashSet<>(Arrays.asList((String[])supported.get(null))).equals(expected.keySet()))throw new AssertionError("Capability list differs from mapping");
  // Allocate the bridge without its socket constructor: status on a null
  // stub application needs no initialized server and performs no game action.
  Class<?> unsafeClass=Class.forName("sun.misc.Unsafe");
  Field unsafeField=unsafeClass.getDeclaredField("theUnsafe");unsafeField.setAccessible(true);
  Object instance=unsafeClass.getMethod("allocateInstance",Class.class).invoke(unsafeField.get(null),bridge);
  Method status=bridge.getDeclaredMethod("status");status.setAccessible(true);
  com.google.gson.JsonObject snapshot=(com.google.gson.JsonObject)status.invoke(instance);
  Set<String> capabilities=new HashSet<>();
  for(var item:snapshot.getAsJsonArray("movement_directions"))capabilities.add(item.getAsString());
  if(!capabilities.equals(expected.keySet()))throw new AssertionError("Status omitted movement capabilities");
  Method release=bridge.getDeclaredMethod("releaseKeys",int[].class);release.setAccessible(true);
  int[] diagonal=(int[])mapping.invoke(null,"down_right");
  com.badlogic.gdx.Gdx.input.failRelease=264;
  try{release.invoke(null,(Object)diagonal);throw new AssertionError("Expected fixture failure");}
  catch(InvocationTargetException e){if(!(e.getCause() instanceof InvocationTargetException))throw e;}
  if(!com.badlogic.gdx.Gdx.input.calls.equals(List.of("264:0","262:0")))throw new AssertionError("Not every held key was released: "+com.badlogic.gdx.Gdx.input.calls);
  System.out.println("Eight directions and complete diagonal cleanup verified.");
 }
}''',
}


class DiagonalControlTests(unittest.TestCase):
    def test_mapping_capabilities_and_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='dw3-diagonal-') as directory:
            root = Path(directory)
            files = []
            for name, content in SOURCES.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                files.append(str(path))
            classpath = f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
            subprocess.run(['javac', '--release', '17', '-cp', classpath, '-d', directory,
                            str(ROOT / 'linux/native/src/dw3/linux/ControlBridge.java'), *files], check=True)
            result = subprocess.run([str(ROOT / 'linux/runtime/bin/java'), '-cp', directory + ':' + classpath,
                                     'DiagonalCheck', str(root / 'control.sock')], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('complete diagonal cleanup verified', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
