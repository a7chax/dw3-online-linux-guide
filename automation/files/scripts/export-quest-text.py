#!/usr/bin/env python3
"""Export English quest-name text through the original client reader, offline.

Reads only text/en/places.json and talk0.json through talk10.json. It does not
read .env, log in, attach to the running game, or unlock protected asset groups.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CLIENT_SHA256='7a5c04ffa8bc186756dc4b8a5c630b4ba4e2193b2d395eadeacc045687ccc5fe'


def resource_paths():
    return ['text/en/places.json',*[f'text/en/talk{i}.json' for i in range(11)]]


def child_environment(environment):
    return {key:value for key,value in environment.items() if key!='DW3_PASSWORD'}


JAVA_SOURCE=r'''import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import com.badlogic.gdx.files.FileHandle;
import com.google.gson.*;

public final class ExportQuestText {
 public static void main(String[] args)throws Exception {
  FileHandle assets=new bo(new File(args[0]),true).d();
  Path output=Path.of(args[1]);Files.createDirectories(output);
  JsonArray exported=new JsonArray(),missing=new JsonArray();
  for(int index=2;index<args.length;index++) {
   String name=args[index];FileHandle resource=assets.child(name);
   if(!resource.exists()){missing.add(name);continue;}
   String text=resource.readString();JsonArray rows=JsonParser.parseString(text).getAsJsonArray();
   for(JsonElement row:rows)if(!row.isJsonPrimitive() || !row.getAsJsonPrimitive().isString())
    throw new IllegalArgumentException("Expected a string array: "+name);
   Path destination=output.resolve(Path.of(name).getFileName());
   Path temporary=Files.createTempFile(output,".quest-text-",".tmp");
   try {
    Files.writeString(temporary,text,StandardCharsets.UTF_8);
    Files.move(temporary,destination,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
   } finally {Files.deleteIfExists(temporary);}
   JsonObject entry=new JsonObject();entry.addProperty("resource",name);entry.addProperty("entries",rows.size());exported.add(entry);
  }
  JsonObject result=new JsonObject();result.addProperty("output_dir",output.toAbsolutePath().toString());
  result.addProperty("exported",exported.size());result.add("resources",exported);result.add("missing",missing);
  System.out.println(new Gson().toJson(result));
 }
}'''


def export(output):
    client=ROOT/'app/client.jar'
    if hashlib.sha256(client.read_bytes()).hexdigest()!=CLIENT_SHA256:
        raise RuntimeError('This exporter supports only the inspected client version 0.1.95.')
    compiler=shutil.which('javac')
    if not compiler:raise RuntimeError('A JDK with javac is required for the standalone reader.')
    java=ROOT/'linux/runtime/bin/java'
    if not java.is_file():raise RuntimeError('The bundled Linux Java runtime is missing.')
    jars=[ROOT/'linux/lib/dw3-android-bridge.jar',*sorted((ROOT/'app').glob('*.jar'))]
    classpath=':'.join(map(str,jars));environment=child_environment(os.environ)
    with tempfile.TemporaryDirectory(prefix='dw3-quest-text-') as temporary:
        source=Path(temporary)/'ExportQuestText.java';source.write_text(JAVA_SOURCE)
        subprocess.run([compiler,'--release','17','-cp',classpath,'-d',temporary,str(source)],check=True,env=environment)
        result=subprocess.run([str(java),'-XX:-UsePerfData','-Djava.library.path='+str(ROOT/'linux/lib'),'-cp',temporary+':'+classpath,'ExportQuestText',str(ROOT),str(Path(output).resolve()),*resource_paths()],capture_output=True,text=True,timeout=40,env=environment)
        if result.returncode:
            raise RuntimeError('Original asset reader failed: '+result.stderr.strip())
        return json.loads(result.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'linux/world/auxiliary/text/en')
    args=parser.parse_args();print(json.dumps(export(args.output),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
