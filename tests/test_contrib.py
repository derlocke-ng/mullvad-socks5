"""Tests for contrib/pihole-mullvad-socks.sh. Offline: the list is a file:// URL."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "contrib", "pihole-mullvad-socks.sh")

LIST = ("# Mullvad SOCKS5 proxies\n"
        "10.124.0.53 de-fra-wg-socks5-001.relays.mullvad.net\r\n"
        "10.124.0.53 de-fra-001.mullvad.home\n"                  # the list's own short names: made here instead
        "10.124.2.22 US-QAS-WG-SOCKS5-101.relays.mullvad.net\n"
        "10.124.0.53 de-fra-wg-socks5-001.relays.mullvad.net\n"
        "10.0.0.1 bank.example.com\n"                            # never another name
        "203.0.113.7 se-mma-wg-socks5-001.relays.mullvad.net\n"  # never a public address
        "010.124.0.1 se-sto-wg-socks5-001.relays.mullvad.net\n"  # octal to some resolvers
        "10.124.0.999 se-got-wg-socks5-001.relays.mullvad.net\n")


@unittest.skipUnless(shutil.which("curl") and shutil.which("sh"), "needs sh and curl")
class TestPiholeScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pihole-mullvad-socks-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "list.hosts")
        self.dir = os.path.join(self.tmp, "records")
        self.hosts = os.path.join(self.dir, "mullvad-socks.hosts")
        self.write(LIST)

    def write(self, text):
        with open(self.src, "w", newline="") as f:
            f.write(text)

    def run_script(self, **env):
        e = dict(os.environ, MULLVAD_SOCKS_HOSTS_URL="file://" + self.src)
        e.pop("MULLVAD_SOCKS_DOMAIN", None)
        e.update(env)
        return subprocess.run(["sh", SCRIPT, self.dir], capture_output=True, text=True, env=e, timeout=120)

    def read(self):
        with open(self.hosts) as f:
            return f.read()

    def test_takes_only_mullvad_names_and_makes_the_short_names(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(), "10.124.0.53 de-fra-wg-socks5-001.relays.mullvad.net\n"
                                      "10.124.2.22 us-qas-wg-socks5-101.relays.mullvad.net\n"
                                      "10.124.0.53 de-fra-001.mullvad.home\n"
                                      "10.124.2.22 us-qas-101.mullvad.home\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.hosts).st_mode), 0o644)
        self.assertEqual(os.listdir(self.dir), ["mullvad-socks.hosts"])   # no temp files left
        r = self.run_script(MULLVAD_SOCKS_DOMAIN="Socks.Example.")
        self.assertEqual(self.read().splitlines()[-1], "10.124.2.22 us-qas-101.socks.example")
        r = self.run_script(MULLVAD_SOCKS_DOMAIN="")
        self.assertEqual(len(self.read().splitlines()), 2)
        # a suffix that would add other names is refused, the records stay
        r = self.run_script(MULLVAD_SOCKS_DOMAIN="x example.com")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.read().splitlines()), 2)

    def test_a_bad_download_keeps_the_records(self):
        self.assertEqual(self.run_script().returncode, 0)
        before = self.read()
        for bad in ("<html>rate limited</html>\n", "", "# nothing\n", "10.0.0.1 bank.example.com\n"):
            self.write(bad)
            r = self.run_script()
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("keeping the current records", r.stderr)
            self.assertEqual(self.read(), before)
        r = subprocess.run(["sh", SCRIPT, self.dir], capture_output=True, text=True,
                           env=dict(os.environ, MULLVAD_SOCKS_HOSTS_URL="file://" + self.src + ".missing"))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.read(), before)

    def test_works_only_in_a_directory_nobody_else_can_write(self):
        target = os.path.join(self.tmp, "elsewhere")
        os.makedirs(target, mode=0o700)
        os.symlink(target, self.dir)
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("leaving it alone", r.stderr)
        self.assertEqual((os.listdir(target), stat.S_IMODE(os.stat(target).st_mode)), ([], 0o700))
        os.unlink(self.dir)
        os.makedirs(self.dir)
        os.chmod(self.dir, 0o775)
        self.assertEqual(self.run_script().returncode, 1)
        self.assertEqual(os.listdir(self.dir), [])
        os.chmod(self.dir, 0o755)
        # a FIFO where the list goes does not hang it, a directory there is not written into
        os.mkfifo(self.hosts)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertTrue(os.path.isfile(self.hosts))
        os.unlink(self.hosts)
        os.makedirs(self.hosts)
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(os.listdir(self.hosts), [])
        self.assertEqual(os.listdir(self.dir), ["mullvad-socks.hosts"])


if __name__ == "__main__":
    unittest.main()
