#!/usr/bin/env python3
"""Check a game-required encoding in the actual bundled Java runtime."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = '''import java.nio.charset.Charset;
public final class CharsetCheck {
 public static void main(String[] args) {
  Charset charset=Charset.forName("x-windows-949");
  String decoded=new String(new byte[]{(byte)0xb0,(byte)0xa1},charset);
  if(!decoded.equals("\\uac00"))throw new AssertionError("Incorrect Korean text decoding");
  byte[] encoded="\\uac00".getBytes(charset);
  if(encoded.length!=2 || encoded[0]!=(byte)0xb0 || encoded[1]!=(byte)0xa1)
   throw new AssertionError("Incorrect Korean text encoding");
  System.out.println("Required game charset x-windows-949: encode/decode passed.");
 }
}'''


class RuntimeTests(unittest.TestCase):
 def test_bundled_runtime_supports_game_charset(self):
  with tempfile.TemporaryDirectory(prefix='dw3-charset-test-') as td:
   source=Path(td)/'CharsetCheck.java';source.write_text(SOURCE)
   subprocess.run(['javac','--release','17','-d',td,str(source)],check=True)
   result=subprocess.run([str(ROOT/'linux/runtime/bin/java'),'-cp',td,'CharsetCheck'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('encode/decode passed',result.stdout)


if __name__=='__main__':unittest.main(verbosity=2)
