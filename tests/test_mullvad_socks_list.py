"""Unit tests for mullvad_socks_list. Run: python3 -m unittest discover -s tests

No test touches the network: DNS and the SOCKS5 check are replaced.
"""
import http.client
import io
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import mullvad_socks_list as msl  # noqa: E402

with open(os.path.join(HERE, "relays.json"), encoding="utf-8") as f:
    RELAYS = json.load(f)

# what public DNS answers for the fixture's proxies
ADDRESSES = {
    "al-tia-wg-socks5-001.relays.mullvad.net": "10.124.1.240",
    "ar-bue-wg-socks5-001.relays.mullvad.net": "10.124.0.15",
    "gb-lon-wg-socks5-001.relays.mullvad.net": "10.124.0.120",
    "se-mma-wg-socks5-001.relays.mullvad.net": "10.124.0.2",
    "us-qas-wg-socks5-101.relays.mullvad.net": "10.124.2.22",
    "us-nyc-wg-socks5-503.relays.mullvad.net": "10.124.0.76",
}


def fake_getaddrinfo(answers):
    def getaddrinfo(name, *args, **kwargs):
        name.encode("idna")   # what the real one does first: UnicodeError for an empty or over-long label
        if name not in answers:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (answers[name], 0))]
    return getaddrinfo


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mullvad-socks-test-")
        self.relays = os.path.join(self.tmp, "relays.json")
        shutil.copy(os.path.join(HERE, "relays.json"), self.relays)
        self.out = os.path.join(self.tmp, "out")
        patches = [mock.patch.object(msl.time, "sleep"), mock.patch.dict(os.environ, {}, clear=False)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ.pop("GITHUB_STEP_SUMMARY", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, *args, answers=ADDRESSES, reachable=None):
        argv = ["--relays", self.relays, "--out", self.out, "--repo", "owner/repo", *args]
        with mock.patch.object(msl.socket, "getaddrinfo", fake_getaddrinfo(answers)), \
             mock.patch.object(msl, "socks5_answers", lambda ip, port: reachable(ip) if reachable else True), \
             redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as stdout:
            code = msl.main(argv)
        self.stdout = stdout.getvalue()
        return code

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as f:
            return f.read()


class TestRelays(Base):
    def test_only_active_relays_with_a_proxy(self):
        names = [p.socks_name for p in msl.socks_proxies(RELAYS)]
        self.assertEqual(len(names), 6)
        self.assertNotIn("de-fra-wg-socks5-001.relays.mullvad.net", names)   # inactive
        self.assertEqual(len(msl.socks_proxies(RELAYS, include_inactive=True)), 7)

    def test_country_codes_come_from_the_api(self):
        # the old scanner mapped country names and got XX for "USA" and "UK"
        codes = {p.country_name: p.country_code for p in msl.socks_proxies(RELAYS)}
        self.assertEqual(codes["USA"], "US")
        self.assertEqual(codes["UK"], "GB")
        self.assertEqual(codes["Argentina"], "AR")
        relay = dict(RELAYS[0], country_code=None)
        self.assertEqual(msl.socks_proxies([relay])[0].country_code, "AL")   # from the hostname

    def test_api_answer_that_is_no_relay_list(self):
        def urlopen(req, timeout):
            return io.BytesIO(b'{"error": "rate limited"}')
        with mock.patch.object(msl.urllib.request, "urlopen", urlopen), redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError):
                msl.fetch_relays(attempts=2)
        with mock.patch.object(msl.urllib.request, "urlopen", lambda req, timeout: io.BytesIO(b'[{"a": 1}]')):
            self.assertEqual(msl.fetch_relays(), [{"a": 1}])

    def test_cut_off_api_answer_is_retried(self):
        answers = [http.client.IncompleteRead(b"[{"), io.BytesIO(b'[{"a": 1}]')]

        def urlopen(req, timeout):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        with mock.patch.object(msl.urllib.request, "urlopen", urlopen), redirect_stderr(io.StringIO()):
            self.assertEqual(msl.fetch_relays(), [{"a": 1}])

    def test_sorted_by_country_city_name(self):
        order = [(p.country_name, p.city_name) for p in msl.socks_proxies(RELAYS)]
        self.assertEqual(order, sorted(order, key=lambda t: (t[0].casefold(), t[1].casefold())))
        self.assertEqual(order[0][0], "Albania")


class TestNamesAndColours(Base):
    def test_flag(self):
        self.assertEqual(msl.flag("US"), "🇺🇸")
        self.assertEqual(msl.flag("GB"), "🇬🇧")
        self.assertEqual(msl.flag("XX"), "🇽🇽")
        self.assertEqual(msl.flag(""), "🏳")

    def test_colour(self):
        self.assertRegex(msl.color("DE"), r"^[0-9a-f]{6}$")
        self.assertEqual(msl.color("DE"), msl.color("DE"))
        self.assertNotEqual(msl.color("DE"), msl.color("DK"))
        self.assertEqual(msl.color(""), "888888")

    def test_short_label(self):
        self.assertEqual(msl.short_label("de-fra-wg-socks5-001.relays.mullvad.net"), "de-fra-001")
        self.assertEqual(msl.short_label("us-nyc-wg-socks5-503.relays.mullvad.net"), "us-nyc-503")
        self.assertEqual(msl.short_label("xx-odd-socks5-7.relays.mullvad.net"), "xx-odd-7")

    def test_aliases_never_collide(self):
        a = dict(RELAYS[0])
        b = dict(RELAYS[0], hostname="al-tia-wg-901", socks_name="al-tia-socks5-001.relays.mullvad.net")
        proxies = msl.socks_proxies([a, b])
        msl.assign_aliases(proxies, "home")
        self.assertEqual(len({p.alias for p in proxies}), 2)
        msl.assign_aliases(proxies[:1], "kiwi.")
        self.assertEqual(proxies[0].alias, "al-tia-001.mullvad.kiwi")


class TestBuild(Base):
    def test_outputs(self):
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(sorted(os.listdir(self.out)), sorted([
            "README.md", "foxyproxy-hostnames.json", "foxyproxy-hostnames.txt", "foxyproxy.json", "foxyproxy.txt",
            "kiwi-extra-records.yaml", "mullvad-socks-list.txt", "mullvad-socks.hosts", "mullvad-socks.json",
            "mullvad_proxies_proxy.txt"]))
        self.assertEqual(self.read("mullvad_proxies_proxy.txt"), self.read("foxyproxy.txt"))

        table = self.read("mullvad-socks-list.txt")
        self.assertIn("Mullvad SOCKS5 proxies: 6", table)
        self.assertRegex(table, r"🇺🇸 +USA +Ashburn, VA +10\.124\.2\.22 +1080 +us-qas-wg-socks5-101\.relays\.mullvad\.net")
        self.assertIn("🇬🇧", table)

        data = json.loads(self.read("mullvad-socks.json"))
        self.assertEqual(len(data), 6)
        self.assertEqual({d["country_code"] for d in data}, {"AL", "AR", "GB", "SE", "US"})

    def test_foxyproxy_json(self):
        self.run_main()
        doc = json.loads(self.read("foxyproxy.json"))
        self.assertEqual(list(doc), ["data"])   # FoxyProxy keeps the user's other settings
        us = next(p for p in doc["data"] if p["title"] == "us-qas-wg-socks5-101")
        self.assertEqual(us["type"], "socks5")
        self.assertEqual(us["hostname"], "10.124.2.22")
        self.assertEqual(us["port"], "1080")
        self.assertEqual(us["cc"], "US")
        self.assertEqual(us["city"], "Ashburn, VA")
        self.assertRegex(us["color"], r"^#[0-9a-f]{6}$")
        self.assertIs(us["proxyDNS"], True)
        for p in doc["data"]:
            self.assertRegex(p["cc"], r"^[A-Z]{2}$")   # FoxyProxy's schema; it draws the flag from it
        names = json.loads(self.read("foxyproxy-hostnames.json"))["data"]
        self.assertEqual(names[0]["hostname"], "al-tia-wg-socks5-001.relays.mullvad.net")

    def test_foxyproxy_list_parses_like_foxyproxy(self):
        self.run_main()
        lines = self.read("foxyproxy.txt").splitlines()
        self.assertEqual(len(lines), 6)
        for line in lines:
            url = urlsplit(line)
            self.assertEqual(url.scheme, "socks5")
            self.assertEqual(url.port, 1080)
            # FoxyProxy lower-cases the parameter names; cc or countrycode, city, color without #
            q = {k.lower(): v for k, v in parse_qsl(url.query)}
            self.assertRegex(q["cc"], r"^[A-Z]{2}$")
            self.assertRegex(q["color"], r"^[0-9a-f]{6}$")
            self.assertEqual(q["proxydns"], "true")
        malmo = next(line for line in lines if "se-mma" in line)
        self.assertIn("city=Malm%C3%B6", malmo)
        self.assertEqual(dict(parse_qsl(urlsplit(malmo).query))["city"], "Malmö")
        self.assertIn("city=Ashburn%2C%20VA", next(line for line in lines if "us-qas" in line))
        self.run_main("--no-proxy-dns")
        self.assertIn("proxyDNS=false", self.read("foxyproxy.txt"))

    def test_dns_records(self):
        self.run_main("--kiwi-domain", "home")
        hosts = self.read("mullvad-socks.hosts")
        records = [line for line in hosts.splitlines() if not line.startswith("#")]
        self.assertEqual(len(records), 12)
        for line in records:
            self.assertRegex(line, r"^10\.124\.\d+\.\d+ [a-z0-9.-]+$")
        self.assertIn("10.124.0.76 us-nyc-wg-socks5-503.relays.mullvad.net", records)
        self.assertIn("10.124.0.76 us-nyc-503.mullvad.home", records)
        # the Mullvad name first, so it is what a reverse lookup answers
        self.assertLess(records.index("10.124.0.76 us-nyc-wg-socks5-503.relays.mullvad.net"),
                        records.index("10.124.0.76 us-nyc-503.mullvad.home"))

        kiwi = self.read("kiwi-extra-records.yaml")
        self.assertIn("\nextra_records:\n", kiwi)
        entries = re.findall(r'^  ([a-z0-9.-]+): "([0-9.]+)"$', kiwi, re.M)
        self.assertEqual(len(entries), 12)
        self.assertIn(("us-nyc-503.mullvad.home", "10.124.0.76"), entries)
        try:
            import yaml
        except ImportError:
            return
        self.assertEqual(yaml.safe_load(kiwi)["extra_records"]["gb-lon-001.mullvad.home"], "10.124.0.120")

    def test_no_aliases(self):
        self.run_main("--kiwi-domain", "")
        self.assertNotIn(".mullvad.home", self.read("mullvad-socks.hosts"))
        self.assertEqual(len([line for line in self.read("mullvad-socks.hosts").splitlines()
                              if not line.startswith("#")]), 6)

    def test_unresolved_names_are_reported_not_listed(self):
        answers = dict(ADDRESSES)
        del answers["ar-bue-wg-socks5-001.relays.mullvad.net"]
        self.assertEqual(self.run_main(answers=answers), 0)
        self.assertNotIn("ar-bue", self.read("foxyproxy.txt"))
        self.assertNotIn("ar-bue", self.read("mullvad-socks.hosts"))
        table = self.read("mullvad-socks-list.txt")
        self.assertIn("Failed to resolve (1):", table)
        self.assertIn("ar-bue-wg-socks5-001", table.split("Failed to resolve")[1])

    def test_public_addresses_are_not_proxies(self):
        answers = dict(ADDRESSES, **{"al-tia-wg-socks5-001.relays.mullvad.net": "93.184.216.34"})
        self.run_main(answers=answers)
        self.assertNotIn("93.184.216.34", self.read("foxyproxy.txt"))
        self.assertIn("Failed to resolve (1):", self.read("mullvad-socks-list.txt"))

    def test_a_malformed_name_is_unresolved_not_fatal(self):
        with open(self.relays, "w") as f:
            json.dump(RELAYS + [dict(RELAYS[0], hostname="al-tia-wg-009",
                                     socks_name="al-tia-wg-socks5-009..relays.mullvad.net")], f)
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(len(self.read("foxyproxy.txt").splitlines()), 6)
        self.assertIn("Failed to resolve (1):", self.read("mullvad-socks-list.txt"))

    def test_dns_trouble_writes_nothing(self):
        self.assertEqual(self.run_main(answers={}), 1)
        self.assertFalse(os.path.exists(self.out))

    def test_check_drops_proxies_that_do_not_answer(self):
        code = self.run_main("--check", reachable=lambda ip: ip != "10.124.0.15")
        self.assertEqual(code, 0)
        self.assertNotIn("10.124.0.15", self.read("foxyproxy.txt"))
        self.assertEqual(len(json.loads(self.read("foxyproxy.json"))["data"]), 5)
        # a proxy that is down keeps its DNS records
        self.assertIn("10.124.0.15 ar-bue-wg-socks5-001.relays.mullvad.net", self.read("mullvad-socks.hosts"))
        table = self.read("mullvad-socks-list.txt")
        self.assertIn("answered a SOCKS5 greeting", table)
        self.assertIn("Not answering (1):", table)
        self.assertIn("each answered a SOCKS5 greeting", self.read("README.md"))

    def test_a_broken_tunnel_does_not_empty_the_lists(self):
        self.assertEqual(self.run_main("--check", reachable=lambda ip: False), 0)
        self.assertEqual(len(self.read("foxyproxy.txt").splitlines()), 6)
        self.assertIn("the tunnel is not working", self.stdout)
        self.assertIn("reachability not checked", self.read("README.md"))

    def test_no_proxies_at_all(self):
        with open(self.relays, "w") as f:
            json.dump([dict(r, socks_name=None) for r in RELAYS], f)
        self.assertEqual(self.run_main(), 1)


class TestSocks5Greeting(unittest.TestCase):
    def serve(self, reply):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)

        import threading

        def answer():
            conn, _ = srv.accept()
            with conn:
                conn.recv(3)
                conn.sendall(reply)
        threading.Thread(target=answer, daemon=True).start()
        return srv.getsockname()

    def test_answers(self):
        ip, port = self.serve(b"\x05\x00")
        self.assertTrue(msl.socks5_answers(ip, port, timeout=2, attempts=1))

    def test_wants_authentication(self):
        ip, port = self.serve(b"\x05\xff")
        self.assertFalse(msl.socks5_answers(ip, port, timeout=2, attempts=1))

    def test_closed_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        self.assertFalse(msl.socks5_answers("127.0.0.1", port, timeout=2, attempts=1))


if __name__ == "__main__":
    unittest.main()
