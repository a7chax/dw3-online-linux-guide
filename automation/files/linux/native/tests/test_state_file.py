#!/usr/bin/env python3
from pathlib import Path
import json,os,subprocess,tempfile,time,unittest
ROOT=Path(__file__).resolve().parents[3]
SOURCES={
 'com/badlogic/gdx/Gdx.java':'package com.badlogic.gdx; public final class Gdx { public static final fake.App app=new fake.App(); }',
 'fake/App.java':'''package fake; public final class App {
 public void postRunnable(Runnable task){task.run();}
 public Game getApplicationListener(){return new Game();}
 }''',
 'fake/Game.java':'package fake; public final class Game { public Object getScreen(){return null;} }',
 'FileCheck.java':'''public final class FileCheck { public static void main(String[] args)throws Exception {
 var constructor=Class.forName("dw3.linux.StatePrinter").getDeclaredConstructor();constructor.setAccessible(true);
 try(AutoCloseable logger=(AutoCloseable)constructor.newInstance()){Thread.sleep(1500);}
 } }'''
}
class StateFileTests(unittest.TestCase):
 def test_latest_snapshot_updates_when_state_is_unchanged(self):
  with tempfile.TemporaryDirectory(prefix='dw3-state-file-test-') as td:
   paths=[]
   for name,source in SOURCES.items():
    p=Path(td)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source);paths.append(str(p))
   subprocess.run(['javac','--release','17','-d',td,*paths],check=True)
   state=Path(td)/'state.json'
   proc=subprocess.Popen([str(ROOT/'linux/runtime/bin/java'),f'-Duser.home={td}','-cp',f'{td}:{ROOT}/linux/lib/dw3-android-bridge.jar','FileCheck'],env=dict(os.environ,DW3_STATE_FILE=str(state)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   try:
    deadline=time.monotonic()+3
    while not state.exists() and time.monotonic()<deadline and proc.poll() is None:time.sleep(.02)
    self.assertTrue(state.exists(),'State logger did not create the latest state file')
    initial=json.loads(state.read_text())
    time.sleep(.35)
    newer=json.loads(state.read_text())
    self.assertEqual(newer['phase'],'starting')
    self.assertNotEqual(initial['time'],newer['time'])
    self.assertEqual(initial['pid'],newer['pid'])
    stdout,stderr=proc.communicate(timeout=5)
    self.assertEqual(proc.returncode,0,stderr)
    history=state.with_name('state-events.jsonl').read_text().splitlines()
    self.assertEqual(len(history),1)
    self.assertEqual(json.loads(history[0])['phase'],'starting')
   finally:
    if proc.poll() is None:proc.kill();proc.wait()
    for stream in [proc.stdout,proc.stderr]:stream.close()
if __name__=='__main__':unittest.main(verbosity=2)
