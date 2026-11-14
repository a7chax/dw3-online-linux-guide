#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
class AtlasTests(unittest.TestCase):
 def test_exports_map_coordinates_and_collision_without_graphics(self):
  with tempfile.TemporaryDirectory(prefix='dw3-atlas-') as td:
   p=Path(td);assets=p/'assets';maps=assets/'maps';(maps/'s450').mkdir(parents=True)
   (maps/'s450/map.json').write_text(json.dumps(dict(room='Bulk Bridge',width=2048,height=1024,place=7,collision='mask.png')))
   (maps/'s450/mask.png').write_bytes(b'fixture collision bytes')
   source=p/'AtlasCheck.java';source.write_text('''import java.io.*;import java.nio.file.*;
public class AtlasCheck {
 public static class Handle {
  private final Path path;public Handle(Path p){path=p;}
  public Handle child(String name){return new Handle(path.resolve(name));}
  public String name(){return path.getFileName().toString();}
  public boolean isDirectory(){return Files.isDirectory(path);}
  public boolean exists(){return Files.exists(path);}
  public Handle[] list()throws Exception{try(var s=Files.list(path)){return s.map(Handle::new).toArray(Handle[]::new);}}
  public String readString()throws Exception{return Files.readString(path);}
  public byte[] readBytes()throws Exception{return Files.readAllBytes(path);}
 }
 public static void main(String[] args)throws Exception{
  Class<?> atlas;
  try{atlas=Class.forName("dw3.linux.WorldAtlas");}catch(ClassNotFoundException e){throw new AssertionError("World atlas exporter is missing",e);}
  var export=atlas.getMethod("export",Object.class,Path.class);
  System.out.println(export.invoke(null,new Handle(Path.of(args[0])),Path.of(args[1])));
 }
}''')
   cp=f'{ROOT}/linux/lib/dw3-android-bridge.jar:{ROOT}/app/gson-2.11.0.jar'
   subprocess.run(['javac','--release','17','-cp',cp,'-d',td,str(source)],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',td+':'+cp,'AtlasCheck',str(assets),str(p/'out')],capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr)
   index=json.loads((p/'out/atlas.json').read_text());self.assertEqual(len(index['maps']),1)
   m=index['maps'][0];self.assertEqual(m['id'],'s450');self.assertEqual(m['width'],2048);self.assertEqual(m['height'],1024)
   self.assertEqual(m['name'],'Bulk Bridge');self.assertEqual((p/'out'/m['collision']).read_bytes(),b'fixture collision bytes')
   self.assertEqual(index['failures'],[])
if __name__=='__main__':unittest.main(verbosity=2)
