#!/usr/bin/env python3
"""Check real coordinate reads without account access or keyboard simulation."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = {
 'aa.java': '''public final class aa { private final String d; public aa(String id){d=id;} String a(){return d;} }''',
 'aj.java': '''public final class aj { public float ax=10.5f, ay=20.5f; public int az=2; public int aA=1; private aa av=new aa("asuka"); private al cG=new al(); public void changeMap(){av=new aa("other");} }''',
 'al.java': '''public final class al {
 private Progress f=new Progress();
 private String x(){return "Step 1 of 6: Go to Swamp Inn.";}
 boolean a(){return true;} boolean b(){return false;} int f(){return 1;}
 int b(float x,float y){return 76;}
 float[] c(float x,float y,float spacing){return new float[]{14,20.5f,21,20.5f};}
 public static class Progress {
 public int a(){return 5;} public int b(){return 36;} public String c(){return "s470";}
 public int d(){return 1;} public int f(){return 121;} public int g(){return 1;} public int h(){return 6;}
 }
 }''',
 'a.java': '''public final class a {}''',
 'StatePrinterCheck.java': '''package dw3.linux;
import java.lang.reflect.*;
public final class StatePrinterCheck {
 public static void main(String[] args) throws Exception {
  Class<?> type=Class.forName("dw3.linux.StatePrinter$Reader");
  Constructor<?> constructor=type.getDeclaredConstructor();constructor.setAccessible(true);
  Object reader=constructor.newInstance();
  Method read=type.getDeclaredMethod("readScreen",Object.class);read.setAccessible(true);
  Object login=Class.forName("a").getConstructor().newInstance();
  Object world=Class.forName("aj").getConstructor().newInstance();
  emit(read.invoke(reader,login));
  emit(read.invoke(reader,world));
  world.getClass().getField("ax").setFloat(world,10.75f);
  emit(read.invoke(reader,world));
  emit(read.invoke(reader,world));
  world.getClass().getField("aA").setInt(world,5);
  emit(read.invoke(reader,world));
  world.getClass().getMethod("changeMap").invoke(world);
  emit(read.invoke(reader,world));
 }
 static void emit(Object state) throws Exception {
  Method json=state.getClass().getDeclaredMethod("toJson");json.setAccessible(true);
  System.out.println(json.invoke(state));
 }
}'''
}


class StatePrinterTests(unittest.TestCase):
 def test_reports_position_changes_and_idle_without_confusing_animation(self):
  with tempfile.TemporaryDirectory(prefix='dw3-state-test-') as td:
   temporary=Path(td)
   files=[]
   for name,source in FIXTURES.items():
    path=temporary/name;path.write_text(source);files.append(str(path))
   subprocess.run(['javac','--release','17','-d',td,*files],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',f'{td}:{ROOT}/linux/lib/dw3-android-bridge.jar','dw3.linux.StatePrinterCheck'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   states=[json.loads(line) for line in result.stdout.splitlines()]
   self.assertEqual(states[0]['phase'],'login')
   self.assertIsNone(states[0]['x'])
   self.assertIsNone(states[1]['moving'])
   self.assertEqual(states[1]['map'],'asuka')
   self.assertEqual(states[1]['x'],10.5)
   self.assertEqual(states[1]['tile_x'],10)
   self.assertEqual(states[1]['facing'],2)
   self.assertTrue(states[1]['trace']['enabled'])
   self.assertFalse(states[1]['trace']['auto_walk'])
   self.assertEqual(states[1]['trace']['steps_remaining'],76)
   self.assertEqual(states[1]['trace']['points'],[[14.0,20.5],[21.0,20.5]])
   self.assertIsNone(states[0]['trace'])
   self.assertIsNone(states[0]['main_quest'])
   self.assertEqual(states[1]['main_quest']['chapter'],5)
   self.assertEqual(states[1]['main_quest']['target_map'],'s470')
   self.assertEqual(states[1]['main_quest']['progress_value_f'],121)
   self.assertEqual(states[1]['main_quest']['objective_text'],'Step 1 of 6: Go to Swamp Inn.')
   self.assertTrue(states[2]['moving'])
   self.assertEqual(states[2]['x'],10.75)
   self.assertFalse(states[3]['moving'])
   self.assertFalse(states[4]['moving'])
   self.assertEqual(states[5]['map'],'other')
   self.assertIsNone(states[5]['moving'])


 def test_slow_output_cannot_block_the_render_thread(self):
  sources={
   'com/badlogic/gdx/Gdx.java': 'package com.badlogic.gdx; public final class Gdx { public static final fake.App app=new fake.App(); }',
   'fake/App.java': '''package fake;
import java.util.concurrent.*;
public final class App {
 public final ExecutorService render=Executors.newSingleThreadExecutor();
 public void postRunnable(Runnable task){render.submit(task);}
 public Game getApplicationListener(){return new Game();}
}''',
   'fake/Game.java': 'package fake; public final class Game { public Object getScreen(){return new Object();} }',
   'dw3/linux/OutputCheck.java': '''package dw3.linux;
import java.io.*;
import java.lang.reflect.*;
import java.util.concurrent.*;
public final class OutputCheck {
 public static void main(String[] args) throws Exception {
  PrintStream real=System.out;
  CountDownLatch entered=new CountDownLatch(1), release=new CountDownLatch(1);
  System.setOut(new PrintStream(new OutputStream(){
   public void write(int value){entered.countDown();try{release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}}
  }));
  AutoCloseable printer=null;
  try {
   Constructor<?> c=Class.forName("dw3.linux.StatePrinter").getDeclaredConstructor();c.setAccessible(true);
   printer=(AutoCloseable)c.newInstance();
   if(!entered.await(3,TimeUnit.SECONDS))throw new AssertionError("No state output attempted");
   com.badlogic.gdx.Gdx.app.render.submit(()->{}).get(500,TimeUnit.MILLISECONDS);
   real.println("Render thread remains responsive while state output is blocked.");
  } finally {
   release.countDown();
   if(printer!=null)printer.close();
   System.setOut(real);
   com.badlogic.gdx.Gdx.app.render.shutdownNow();
  }
 }
}'''
  }
  with tempfile.TemporaryDirectory(prefix='dw3-state-output-test-') as td:
   paths=[]
   for name,source in sources.items():
    path=Path(td)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source);paths.append(str(path))
   subprocess.run(['javac','--release','17','-d',td,*paths],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),f'-Duser.home={td}','-cp',f'{td}:{ROOT}/linux/lib/dw3-android-bridge.jar','dw3.linux.OutputCheck'],capture_output=True,text=True,timeout=8)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('Render thread remains responsive',result.stdout)


if __name__=='__main__':unittest.main(verbosity=2)
