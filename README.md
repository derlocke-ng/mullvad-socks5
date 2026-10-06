# Mullvad SOCKS5 proxy lists

[![Mullvad SOCKS5 proxy lists](https://github.com/derlocke-ng/mullvad-socks5/actions/workflows/mullvad-proxy-scan.yml/badge.svg)](https://github.com/derlocke-ng/mullvad-socks5/actions/workflows/mullvad-proxy-scan.yml)

Every Mullvad WireGuard server runs a SOCKS5 proxy that any Mullvad connection
can use: connect to one server, browse out of another. This repository lists
them, rebuilt every 6 hours by GitHub Actions and published to the
[`list` branch](https://github.com/derlocke-ng/mullvad-socks5/tree/list):

- **FoxyProxy** imports, with country flags, cities and a colour per country
- a **detailed table** — flag, country, city, proxy address and name, relay
- **DNS records** for **Pi-hole** and the **[Kiwi Network](https://github.com/derlocke-ng/kiwi-server)**, so the proxies have names inside your own network

It works like [maximko/mullvad-socks-list](https://github.com/maximko/mullvad-socks-list):
a proxy's name (`de-fra-wg-socks5-001.relays.mullvad.net`) resolves in public
DNS to its address (`10.124.0.53`), so building the lists needs no VPN and no
secrets. Nothing to do by hand: the schedule keeps itself enabled (below).

## The lists

Always current, from the `list` branch:

| file | what |
|---|---|
| [mullvad-socks-list.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad-socks-list.txt) | table: flag, country, city, proxy, relay |
| [mullvad-socks.json](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad-socks.json) | the same as data |
| [foxyproxy.json](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy.json) | FoxyProxy *Import from URL* |
| [foxyproxy.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy.txt) | FoxyProxy *Import Proxy List* |
| [foxyproxy-hostnames.json](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy-hostnames.json) | as foxyproxy.json, with names instead of addresses |
| [foxyproxy-hostnames.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy-hostnames.txt) | as foxyproxy.txt, with names instead of addresses |
| [mullvad-socks.hosts](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad-socks.hosts) | DNS records, hosts format: Pi-hole, dnsmasq, `/etc/hosts` |
| [kiwi-extra-records.yaml](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/kiwi-extra-records.yaml) | the same records as kiwi-server `dns.extra_records` |
| [mullvad_proxies_proxy.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad_proxies_proxy.txt) | = foxyproxy.txt, under the file name earlier versions published |

The same files are attached to the [latest-proxies release](https://github.com/derlocke-ng/mullvad-socks5/releases/tag/latest-proxies).

The addresses (`10.124.0.0/16`) answer only through a Mullvad VPN connection —
any Mullvad server will do.

## FoxyProxy

FoxyProxy 8 (Firefox, Chrome), *Options → Import*:

- **Import from URL** — paste
  `https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy.json`,
  click *Import*, then *Save* on the *Proxies* tab it opens. This **replaces**
  your proxy list; your other settings stay.
- **Import Proxy List** — paste the lines of
  [foxyproxy.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy.txt)
  (or just the countries you want), click *Import*, then *Save* on the
  *Proxies* tab. This **adds** to your proxies.

With FoxyProxy's *Sync* on, keep to the countries you use: the browser syncs at
most 512 entries / 100 KB, about 390 of these proxies (350 with hostnames). On
a bigger list FoxyProxy reports a Sync error and switches *Sync* off.

Each proxy shows its country's flag, *City, Country* and a colour per country,
and is titled like its server (`de-fra-wg-socks5-001`). *Proxy DNS* is on, so
names are looked up at the proxy's end, as Mullvad recommends.

The `-hostnames` variants use the proxies' names instead of their addresses, so
they keep working if Mullvad renumbers a proxy. They need a resolver that
answers those names with private addresses: public DNS does, and so does the
Kiwi Network reliably once Pi-hole has the records below.

## Kiwi Network / Pi-hole

A kiwi master's Pi-hole asks its VPN client (gluetun) first, and gluetun refuses
DNS answers in private ranges (DNS rebinding protection). So the proxies' names
only resolve in the mesh when Pi-hole moves on to its fallback resolvers, and
not at all without them. Pi-hole answering them itself fixes that, with short
names in the fleet's domain as well:

```
10.124.0.53 de-fra-wg-socks5-001.relays.mullvad.net
10.124.0.53 de-fra-001.mullvad.home
```

Only `*.relays.mullvad.net` names at `10.x` addresses are ever taken from the
list, so it can never redirect another name; the short names are made locally.

### kiwi-server

[kiwi-server](https://github.com/derlocke-ng/kiwi-server) 2.2.0 and later do
it themselves: the dns module's `mullvad_socks` is on in the master preset. A
host timer (`km-mullvad-socks.timer`) fetches this list every 6 hours and
dnsmasq reloads the records without a restart; nodes ask the master. Render and
apply the master again after upgrading. To turn it off, or to use a fork's list:

```yaml
master:
  dns:
    mullvad_socks: false
    # mullvad_socks_url: https://raw.githubusercontent.com/<you>/mullvad-socks5/list/mullvad-socks.hosts
```

### Any other Pi-hole 6

[contrib/pihole-mullvad-socks.sh](contrib/pihole-mullvad-socks.sh) does the
same for a Pi-hole you run yourself: it puts the current records into Pi-hole's
dnsmasq directory, where dnsmasq picks up every change by itself.

1. Let Pi-hole load `/etc/dnsmasq.d`: `misc.etc_dnsmasq_d = true` in `pihole.toml`
   (in docker: `FTLCONF_misc_etc_dnsmasq_d: "true"`).

2. Install the script and run it once with the directory Pi-hole mounts at
   `/etc/dnsmasq.d` (`/etc/dnsmasq.d` itself without docker). The first run
   writes `90-mullvad-socks.conf`, so restart Pi-hole once after it:

   ```bash
   curl -fsSLo /tmp/pihole-mullvad-socks.sh https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/main/contrib/pihole-mullvad-socks.sh
   sudo install -m 755 /tmp/pihole-mullvad-socks.sh /usr/local/bin/pihole-mullvad-socks.sh
   sudo pihole-mullvad-socks.sh /srv/pihole/etc-dnsmasq.d
   sudo docker restart pihole
   ```

3. Keep it current with a timer:

   ```bash
   sudo tee /etc/systemd/system/pihole-mullvad-socks.service >/dev/null <<'EOF'
   [Unit]
   Description=Update Pi-hole's Mullvad SOCKS5 records
   Wants=network-online.target
   After=network-online.target

   [Service]
   Type=oneshot
   # Environment=MULLVAD_SOCKS_DOMAIN=mullvad.home
   # Environment=MULLVAD_SOCKS_HOSTS_URL=https://raw.githubusercontent.com/<you>/mullvad-socks5/list/mullvad-socks.hosts
   ExecStart=/usr/local/bin/pihole-mullvad-socks.sh /srv/pihole/etc-dnsmasq.d
   EOF
   sudo tee /etc/systemd/system/pihole-mullvad-socks.timer >/dev/null <<'EOF'
   [Unit]
   Description=Update Pi-hole's Mullvad SOCKS5 records every 6 hours

   [Timer]
   OnBootSec=5min
   OnUnitActiveSec=6h
   RandomizedDelaySec=30min

   [Install]
   WantedBy=timers.target
   EOF
   sudo systemctl daemon-reload && sudo systemctl enable --now pihole-mullvad-socks.timer
   ```

The short names go under `mullvad.home` (`MULLVAD_SOCKS_DOMAIN`, empty for
none). A download that is not a list of Mullvad proxies (an error page, an
empty file) never replaces the records Pi-hole has.

### The files themselves

`mullvad-socks.hosts` also works as an `/etc/hosts` addition, and
[kiwi-extra-records.yaml](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/kiwi-extra-records.yaml)
holds the same records as a kiwi-server `extra_records` map for kiwi-server
before 2.2.0 (fixed at render time). Their short names use the domain `home`;
set the repository variable `KIWI_DOMAIN` (*Settings → Secrets and variables →
Actions → Variables*) for another.

## How the lists are built

[`.github/workflows/mullvad-proxy-scan.yml`](.github/workflows/mullvad-proxy-scan.yml)
runs every 6 hours, on a push to the script, and from *Actions → Run workflow*:

1. **keeps the schedule alive** — GitHub suspends the schedule of a public
   repository's workflow after 60 days without activity; the workflow enables
   itself through the API on every run
2. runs the tests
3. [`mullvad_socks_list.py`](mullvad_socks_list.py) reads Mullvad's relay list
   (`api.mullvad.net/www/relays/wireguard/`), takes the active relays with a
   SOCKS5 proxy, resolves their names and writes the lists. Country codes,
   names and cities come from the API, so flags are right for every country
   Mullvad has, including new ones.
4. commits them to the `list` branch when they changed, and updates the release

It refuses to publish when fewer than half of the names resolve (DNS trouble),
so a bad run never replaces good lists.

### Checking the proxies (optional)

With a Mullvad WireGuard configuration in the repository secrets, the workflow
connects to Mullvad and lists only the proxies that answer a SOCKS5 greeting.
Without them, or when the tunnel does not come up, it lists every proxy on an
active relay — the lists are built either way.

Generate a WireGuard configuration in your [Mullvad account](https://mullvad.net/account)
(a device of its own for this), then add as *Actions secrets*:

| secret | from the configuration |
|---|---|
| `MULLVAD_PRIVATE_KEY` | `[Interface] PrivateKey` |
| `MULLVAD_ADDRESS` | `[Interface] Address`, e.g. `10.64.0.2/32` |
| `MULLVAD_SERVER_PUBLIC_KEY` | `[Peer] PublicKey` |
| `MULLVAD_SERVER_ENDPOINT` | `[Peer] Endpoint`, e.g. `185.65.135.1:51820` |

Only Mullvad's internal network (`10.64.0.0/10`) goes through the tunnel.

## Run it yourself

Python 3.9 or newer, nothing to install:

```bash
python3 mullvad_socks_list.py -o list            # the lists into ./list
python3 mullvad_socks_list.py -o list --check    # while connected to Mullvad: only proxies that answer
python3 mullvad_socks_list.py --help             # --kiwi-domain, --no-proxy-dns, …
python3 -m unittest discover -s tests            # the tests, offline
```

## License

MIT
