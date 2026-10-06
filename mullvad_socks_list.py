#!/usr/bin/env python3
"""Build the Mullvad SOCKS5 proxy lists.

Every Mullvad WireGuard relay runs a SOCKS5 proxy that is reachable from inside
any Mullvad tunnel. Its name (xx-yyy-wg-socks5-NNN.relays.mullvad.net) resolves
in public DNS to the proxy's address in 10.124.0.0/16, so building the lists
needs no VPN connection. --check also verifies that every proxy answers a
SOCKS5 greeting, which only works while connected to Mullvad.

Writes into --out:
  mullvad-socks-list.txt     detailed table: flag, country, city, proxy, relay
  mullvad-socks.json         the same as data
  foxyproxy.json             FoxyProxy 8 "Import from URL" / file import (IPs)
  foxyproxy.txt              FoxyProxy 8 "Import Proxy List" (IPs)
  foxyproxy-hostnames.json   the same with the proxies' DNS names
  foxyproxy-hostnames.txt
  mullvad-socks.hosts        DNS records, hosts format: Pi-hole, dnsmasq, /etc/hosts
  kiwi-extra-records.yaml    DNS records as kiwi-server dns.extra_records
  mullvad_proxies_proxy.txt  = foxyproxy.txt, the name earlier versions published
  README.md                  index of the files, with the time of the build

Python 3.9+, standard library only.
"""

import argparse
import colorsys
import http.client
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote, urlencode

API_URL = "https://api.mullvad.net/www/relays/wireguard/"
DEFAULT_REPO = "derlocke-ng/mullvad-socks5"
LIST_BRANCH = "list"

# Below these shares something is broken (DNS, the tunnel), not the proxies
MIN_RESOLVED_SHARE = 0.5
MIN_REACHABLE_SHARE = 0.5


@dataclass
class Proxy:
    relay: str            # de-fra-wg-001
    socks_name: str       # de-fra-wg-socks5-001.relays.mullvad.net
    socks_port: int
    country_code: str     # DE
    country_name: str
    city_code: str
    city_name: str
    ipv4_addr_in: str
    ipv6_addr_in: str
    provider: str
    owned: bool
    speed: int            # network port speed, Gbit/s
    socks_ip: str = ""
    alias: str = ""       # de-fra-001.mullvad.<kiwi domain>
    reachable: Optional[bool] = None

    @property
    def label(self) -> str:
        return self.socks_name.split(".", 1)[0]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def warn(msg: str) -> None:
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "warning: "
    print(prefix + msg, flush=True)


# ---------- relays -----------------------------------------------------------

def fetch_relays(url: str = API_URL, attempts: int = 4) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "mullvad-socks-list"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                relays = json.load(resp)
            if not isinstance(relays, list):
                raise ValueError(f"expected a list of relays, got {type(relays).__name__}")
            return relays
        except (OSError, ValueError, http.client.HTTPException) as e:   # HTTPException: a cut-off body
            if attempt == attempts:
                raise
            log(f"relay list: {e}, retrying")
            time.sleep(2 ** attempt)
    return []


def country_code(relay: dict) -> str:
    cc = (relay.get("country_code") or relay.get("hostname", "")[:2]).upper()
    return cc if re.fullmatch(r"[A-Z]{2}", cc) else ""


def socks_proxies(relays: Iterable[dict], include_inactive: bool = False) -> List[Proxy]:
    proxies = []
    for r in relays:
        if not r.get("socks_name") or not (include_inactive or r.get("active")):
            continue
        if r.get("type", "wireguard") != "wireguard":
            continue
        proxies.append(Proxy(
            relay=r.get("hostname", ""),
            socks_name=r["socks_name"].strip().lower().rstrip("."),
            socks_port=int(r.get("socks_port") or 1080),
            country_code=country_code(r),
            country_name=r.get("country_name", ""),
            city_code=r.get("city_code", ""),
            city_name=r.get("city_name", ""),
            ipv4_addr_in=r.get("ipv4_addr_in") or "",
            ipv6_addr_in=r.get("ipv6_addr_in") or "",
            provider=r.get("provider") or "",
            owned=bool(r.get("owned")),
            speed=int(r.get("network_port_speed") or 0),
        ))
    proxies.sort(key=lambda p: (p.country_name.casefold(), p.city_name.casefold(), p.socks_name))
    return proxies


# ---------- DNS --------------------------------------------------------------

def resolve(name: str, attempts: int = 3) -> str:
    """The name's private IPv4 address, or "" when it has none."""
    for attempt in range(1, attempts + 1):
        try:
            infos = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
            for info in infos:
                ip = info[4][0]
                if ipaddress.ip_address(ip).is_private:
                    return ip
            log(f"{name}: no private address in {sorted({i[4][0] for i in infos})}")
            return ""
        except UnicodeError:   # an empty or over-long label: not a name, retrying will not help
            log(f"{name}: not a valid host name")
            return ""
        except OSError:
            if attempt < attempts:
                time.sleep(attempt)
    return ""


def resolve_all(proxies: List[Proxy], workers: int = 16) -> None:
    with ThreadPoolExecutor(workers) as pool:
        for p, ip in zip(proxies, pool.map(resolve, [p.socks_name for p in proxies])):
            p.socks_ip = ip


# ---------- reachability -----------------------------------------------------

def socks5_answers(ip: str, port: int, timeout: float = 5.0, attempts: int = 3) -> bool:
    """True when ip:port completes a SOCKS5 greeting (no authentication)."""
    for _ in range(attempts):
        try:
            with socket.create_connection((ip, port), timeout=timeout) as s:
                s.settimeout(timeout)
                s.sendall(b"\x05\x01\x00")
                if s.recv(2) == b"\x05\x00":
                    return True
        except OSError:
            pass
    return False


def check_all(proxies: List[Proxy], workers: int = 32) -> None:
    with ThreadPoolExecutor(workers) as pool:
        results = pool.map(lambda p: socks5_answers(p.socks_ip, p.socks_port), proxies)
        for p, ok in zip(proxies, results):
            p.reachable = ok


# ---------- names, flags, colours --------------------------------------------

def flag(cc: str) -> str:
    if not re.fullmatch(r"[A-Z]{2}", cc):
        return "🏳"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)


def color(cc: str) -> str:
    """A stable colour per country: golden-angle hues over the country code,
    so neighbouring codes (DE, DK) get clearly different colours."""
    if not re.fullmatch(r"[A-Z]{2}", cc):
        return "888888"
    index = (ord(cc[0]) - 65) * 26 + (ord(cc[1]) - 65)
    r, g, b = colorsys.hls_to_rgb((index * 137.508) % 360 / 360, 0.5, 0.65)
    return "%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def short_label(socks_name: str) -> str:
    """de-fra-wg-socks5-001.relays.mullvad.net -> de-fra-001"""
    label = socks_name.split(".", 1)[0]
    m = re.fullmatch(r"([a-z]{2}-[a-z0-9]+)-wg-socks5-(\d+)", label)
    return f"{m.group(1)}-{m.group(2)}" if m else label.replace("-socks5", "")


def assign_aliases(proxies: List[Proxy], domain: str) -> None:
    domain = domain.strip(".").lower()
    if not domain:
        return
    labels: Dict[str, int] = {}
    for p in proxies:
        labels[short_label(p.socks_name)] = labels.get(short_label(p.socks_name), 0) + 1
    for p in proxies:
        label = short_label(p.socks_name)
        if labels[label] > 1:   # never two proxies behind one short name
            label = p.label
        p.alias = f"{label}.mullvad.{domain}"


# ---------- output -----------------------------------------------------------

def table(rows: List[List[str]]) -> str:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows) + "\n"


def detailed_list(listed: List[Proxy], unresolved: List[Proxy], down: List[Proxy], checked: bool) -> str:
    head = ["flag", "country", "city", "socks5", "port", "hostname", "relay",
            "ipv4_in", "ipv6_in", "speed", "owned", "provider"]

    def row(p: Proxy, addr: str) -> List[str]:
        return [flag(p.country_code), p.country_name, p.city_name, addr, str(p.socks_port),
                p.socks_name, p.relay, p.ipv4_addr_in, p.ipv6_addr_in, str(p.speed),
                "yes" if p.owned else "no", p.provider]

    out = [f"Mullvad SOCKS5 proxies: {len(listed)}"
           + (" (answered a SOCKS5 greeting)" if checked else " (active relays, resolved names)"),
           "Reachable only through a Mullvad VPN connection.", ""]
    out.append(table([head] + [row(p, p.socks_ip) for p in listed]))
    if down:
        out += ["", f"Not answering ({len(down)}):", ""]
        out.append(table([head] + [row(p, p.socks_ip) for p in down]))
    if unresolved:
        out += ["", f"Failed to resolve ({len(unresolved)}):", ""]
        out.append(table([head] + [row(p, "-") for p in unresolved]))
    return "\n".join(out)


def proxy_data(p: Proxy) -> dict:
    d = asdict(p)
    d["flag"] = flag(p.country_code)
    return d


def foxyproxy_entry(p: Proxy, host: str, proxy_dns: bool) -> dict:
    # FoxyProxy 8 proxy object; it draws the flag from cc and shows
    # "city, country" under the title
    return {
        "active": True,
        "title": p.label,
        "type": "socks5",
        "hostname": host,
        "port": str(p.socks_port),
        "username": "",
        "password": "",
        "cc": p.country_code,
        "city": p.city_name,
        "color": "#" + color(p.country_code),
        "pac": "",
        "pacString": "",
        "proxyDNS": proxy_dns,
        "include": [],
        "exclude": [],
        "tabProxy": [],
    }


def foxyproxy_url(p: Proxy, host: str, proxy_dns: bool) -> str:
    # FoxyProxy 8 "Import Proxy List", extended format
    query = urlencode({
        "title": p.label,
        "cc": p.country_code,
        "city": p.city_name,
        "color": color(p.country_code),
        "proxyDNS": str(proxy_dns).lower(),
    }, quote_via=quote)
    return f"socks5://{host}:{p.socks_port}?{query}"


def foxyproxy_json(proxies: List[Proxy], hostnames: bool, proxy_dns: bool) -> str:
    # only "data": FoxyProxy keeps every other setting on import
    data = [foxyproxy_entry(p, p.socks_name if hostnames else p.socks_ip, proxy_dns) for p in proxies]
    return json.dumps({"data": data}, indent=2, ensure_ascii=False) + "\n"


def foxyproxy_list(proxies: List[Proxy], hostnames: bool, proxy_dns: bool) -> str:
    return "".join(foxyproxy_url(p, p.socks_name if hostnames else p.socks_ip, proxy_dns) + "\n"
                   for p in proxies)


def dns_records(proxies: List[Proxy]) -> List[tuple]:
    """(name, ip) for every proxy: the Mullvad name, then the kiwi alias."""
    records = []
    for p in sorted(proxies, key=lambda p: p.socks_name):
        records.append((p.socks_name, p.socks_ip))
    for p in sorted(proxies, key=lambda p: p.alias):
        if p.alias:
            records.append((p.alias, p.socks_ip))
    return records


def hosts_file(proxies: List[Proxy], repo: str) -> str:
    out = [
        "# Mullvad SOCKS5 proxies, hosts format (Pi-hole, dnsmasq hostsdir/addn-hosts, /etc/hosts)",
        "# The addresses are reachable only through a Mullvad VPN connection.",
        f"# https://github.com/{repo}",
    ]
    out += [f"{ip} {name}" for name, ip in dns_records(proxies)]
    return "\n".join(out) + "\n"


def kiwi_yaml(proxies: List[Proxy], repo: str) -> str:
    out = [
        "# Mullvad SOCKS5 proxies as kiwi-server DNS records.",
        "# Paste the extra_records map into the dns block of the host that runs",
        "# Pi-hole (the master), e.g. hosts: gate: master: dns: extra_records: ...",
        "# and render again. These are fixed at render time; for records that follow",
        f"# the list by themselves see https://github.com/{repo}#kiwi-network--pi-hole",
        "extra_records:",
    ]
    out += [f'  {name}: "{ip}"' for name, ip in dns_records(proxies)]
    return "\n".join(out) + "\n"


def readme(listed: List[Proxy], records: int, repo: str, checked: bool, built: str) -> str:
    raw = f"https://raw.githubusercontent.com/{repo}/{LIST_BRANCH}"
    by_country: Dict[str, List[Proxy]] = {}
    for p in listed:
        by_country.setdefault(p.country_code, []).append(p)
    out = [
        "# Mullvad SOCKS5 proxy lists",
        "",
        f"Built {built} by [{repo}](https://github.com/{repo}) — "
        f"**{len(listed)} proxies** in {len(by_country)} countries, "
        + ("each answered a SOCKS5 greeting through a Mullvad tunnel."
           if checked else "taken from Mullvad's active relays (reachability not checked)."),
        "",
        "The proxies are reachable only through a Mullvad VPN connection.",
        "",
        "| file | what |",
        "|---|---|",
        f"| [mullvad-socks-list.txt]({raw}/mullvad-socks-list.txt) | table: flag, country, city, proxy, relay |",
        f"| [mullvad-socks.json]({raw}/mullvad-socks.json) | the same as data |",
        f"| [foxyproxy.json]({raw}/foxyproxy.json) | FoxyProxy: *Import from URL* (replaces your proxies) |",
        f"| [foxyproxy.txt]({raw}/foxyproxy.txt) | FoxyProxy: *Import Proxy List* (adds to your proxies) |",
        f"| [foxyproxy-hostnames.json]({raw}/foxyproxy-hostnames.json) | as foxyproxy.json, with DNS names instead of addresses |",
        f"| [foxyproxy-hostnames.txt]({raw}/foxyproxy-hostnames.txt) | as foxyproxy.txt, with DNS names instead of addresses |",
        f"| [mullvad-socks.hosts]({raw}/mullvad-socks.hosts) | {records} DNS records, hosts format: Pi-hole, dnsmasq, /etc/hosts |",
        f"| [kiwi-extra-records.yaml]({raw}/kiwi-extra-records.yaml) | the same records as kiwi-server `dns.extra_records` |",
        f"| [mullvad_proxies_proxy.txt]({raw}/mullvad_proxies_proxy.txt) | = foxyproxy.txt, the old file name |",
        "",
        "| | country | proxies |",
        "|---|---|---:|",
    ]
    for cc, ps in sorted(by_country.items(), key=lambda kv: kv[1][0].country_name.casefold()):
        out.append(f"| {flag(cc)} | {ps[0].country_name} | {len(ps)} |")
    return "\n".join(out) + "\n"


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------- main -------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--out", default="list", help="output directory (default: ./list)")
    ap.add_argument("--relays", help="read the relay list from this JSON file instead of the Mullvad API")
    ap.add_argument("--check", action="store_true",
                    help="keep only proxies that answer a SOCKS5 greeting (needs a Mullvad connection)")
    ap.add_argument("--kiwi-domain", default="home",
                    help="add DNS aliases <cc>-<city>-<n>.mullvad.<domain>; empty for none (default: home)")
    ap.add_argument("--no-proxy-dns", dest="proxy_dns", action="store_false",
                    help="FoxyProxy resolves names locally instead of through the proxy")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO,
                    help="owner/name, for the links in the outputs")
    ap.add_argument("--include-inactive", action="store_true", help="also list relays Mullvad marks inactive")
    args = ap.parse_args(argv)

    if args.relays:
        with open(args.relays, encoding="utf-8") as f:
            relays = json.load(f)
    else:
        relays = fetch_relays()
    proxies = socks_proxies(relays, args.include_inactive)
    if not proxies:
        log("no relay with a SOCKS5 proxy in the relay list")
        return 1
    log(f"{len(proxies)} SOCKS5 proxies on {'' if args.include_inactive else 'active '}relays, resolving")

    resolve_all(proxies)
    resolved = [p for p in proxies if p.socks_ip]
    unresolved = [p for p in proxies if not p.socks_ip]
    log(f"resolved {len(resolved)}, failed {len(unresolved)}")
    if len(resolved) < len(proxies) * MIN_RESOLVED_SHARE:
        log(f"only {len(resolved)} of {len(proxies)} names resolved: DNS trouble, not writing the lists")
        return 1
    if unresolved:
        warn(f"{len(unresolved)} proxy names did not resolve: {', '.join(p.label for p in unresolved[:10])}"
             + (" …" if len(unresolved) > 10 else ""))

    listed, down, checked = resolved, [], False
    if args.check:
        log("checking SOCKS5 greetings")
        check_all(resolved)
        up = [p for p in resolved if p.reachable]
        if len(up) < len(resolved) * MIN_REACHABLE_SHARE:
            warn(f"only {len(up)} of {len(resolved)} proxies answered: the tunnel is not working, "
                 "listing every resolved proxy unchecked")
            for p in resolved:
                p.reachable = None
        else:
            listed, down, checked = up, [p for p in resolved if not p.reachable], True
            log(f"{len(up)} answered, {len(down)} did not")

    assign_aliases(resolved, args.kiwi_domain)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(args.out, exist_ok=True)
    files = {
        "mullvad-socks-list.txt": detailed_list(listed, unresolved, down, checked),
        "mullvad-socks.json": json.dumps([proxy_data(p) for p in listed], indent=2, ensure_ascii=False) + "\n",
        "foxyproxy.json": foxyproxy_json(listed, False, args.proxy_dns),
        "foxyproxy.txt": foxyproxy_list(listed, False, args.proxy_dns),
        "foxyproxy-hostnames.json": foxyproxy_json(listed, True, args.proxy_dns),
        "foxyproxy-hostnames.txt": foxyproxy_list(listed, True, args.proxy_dns),
        # the DNS records cover every resolved proxy: a proxy that is down
        # now keeps its name and address
        "mullvad-socks.hosts": hosts_file(resolved, args.repo),
        "kiwi-extra-records.yaml": kiwi_yaml(resolved, args.repo),
        "README.md": readme(listed, len(dns_records(resolved)), args.repo, checked, built),
    }
    files["mullvad_proxies_proxy.txt"] = files["foxyproxy.txt"]
    for name, text in files.items():
        write(os.path.join(args.out, name), text)
    log(f"wrote {len(files)} files to {args.out}: {len(listed)} proxies")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### {len(listed)} Mullvad SOCKS5 proxies\n\n"
                    f"- relays with a proxy: {len(proxies)}\n- resolved: {len(resolved)}\n"
                    f"- checked: {'yes, ' + str(len(down)) + ' did not answer' if checked else 'no'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
