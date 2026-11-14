#!/usr/bin/env python3
"""Exercise real JVM processes and the game's POSIX lock convention."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import selectors
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
JAVA = ROOT / 'linux/runtime/bin/java'
BRIDGE = ROOT / 'linux/lib/dw3-android-bridge.jar'
FIXTURE = '''package dw.client;
import java.nio.channels.*;
import java.nio.file.*;
public final class ClientMain {
 public static void main(String[] args) throws Exception {
  Path home=Path.of(System.getProperty("user.home"));
  Path state=home.resolve(".dw3online");
  Files.createDirectories(state);
  try(FileChannel channel=FileChannel.open(state.resolve("aberto.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
      FileLock lock=channel.tryLock()) {
   if(lock==null) throw new IllegalStateException("Profile is already in use");
   System.out.println("PROFILE="+home.toAbsolutePath().normalize());
   System.out.flush();
   System.in.read();
  }
 }
}
'''


class InstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix='dw3-instance-fixture-')
        cls.addClassCleanup(cls.fixture_dir.cleanup)
        source = Path(cls.fixture_dir.name) / 'dw/client/ClientMain.java'
        source.parent.mkdir(parents=True)
        source.write_text(FIXTURE)
        subprocess.run(['javac', '--release', '17', '-d', cls.fixture_dir.name, str(source)], check=True)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='dw3-instance-test-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / '.linux-home'

    def start(self, legacy=False):
        main = 'dw.client.ClientMain' if legacy else 'dw3.linux.DesktopLauncher'
        process = subprocess.Popen(
            [str(JAVA), f'-Duser.home={self.home}', '-cp',
             f'{self.fixture_dir.name}:{BRIDGE}:{ROOT}/app/gson-2.11.0.jar', main],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.close_process, process)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while selector.select(timeout=5):
                line = process.stdout.readline()
                if line.startswith('PROFILE='):
                    return process, Path(line.removeprefix('PROFILE=').strip())
                if not line:
                    break
        finally:
            selector.close()
        self.stop(process)
        error = process.stderr.read()
        self.fail(f'{main} did not acquire a usable profile: {error}')

    @staticmethod
    def close_process(process):
        InstanceTests.stop(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def test_two_windows_use_separate_profiles_and_reuse_released_primary(self):
        first, first_home = self.start()
        second, second_home = self.start()
        self.assertEqual(first_home, self.home)
        self.assertNotEqual(first_home, second_home)
        self.assertIsNone(first.poll())
        self.assertIsNone(second.poll())
        self.stop(first)
        third, third_home = self.start()
        self.assertEqual(third_home, self.home)
        self.assertIsNone(second.poll())
        self.assertIsNone(third.poll())

    def test_existing_game_lock_preserves_the_running_window(self):
        legacy, legacy_home = self.start(legacy=True)
        new, new_home = self.start()
        self.assertEqual(legacy_home, self.home)
        self.assertNotEqual(new_home, legacy_home)
        self.assertIsNone(legacy.poll())
        self.assertIsNone(new.poll())

    def test_simultaneous_launches_do_not_share_profiles(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            processes = list(pool.map(lambda _: self.start(), range(4)))
        self.assertEqual(len({home for _, home in processes}), 4)
        self.assertTrue(all(process.poll() is None for process, _ in processes))


if __name__ == '__main__':
    unittest.main(verbosity=2)
