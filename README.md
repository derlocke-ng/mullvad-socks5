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
  then *Save*. This **replaces** your proxy list; your other settings stay.
- **Import Proxy List** — paste the lines of
  [foxyproxy.txt](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/foxyproxy.txt)
  (or just the countries you want), then *Save*. This **adds** to your proxies.

Each proxy shows its country's flag, *City, Country* and a colour per country,
and is titled like its server (`de-fra-wg-socks5-001`). *Proxy DNS* is on, so
names are looked up at the proxy's end, as Mullvad recommends.

The `-hostnames` variants use the proxies' names instead of their addresses, so
they keep working if Mullvad renumbers a proxy. They need a resolver that
answers those names with private addresses: public DNS does, the Kiwi Network
does once Pi-hole has the records below.

## Kiwi Network / Pi-hole

A kiwi master resolves through its VPN client, and gluetun's DNS drops answers
in private ranges (DNS rebinding protection) — so in the mesh the proxies' names
do not resolve, only their addresses work. Pi-hole answering them itself fixes
that. Nodes ask the master's Pi-hole first, so the master alone is enough.

The records are the Mullvad names and short aliases in the fleet's domain:

```
10.124.0.53 de-fra-wg-socks5-001.relays.mullvad.net
10.124.0.53 de-fra-001.mullvad.home
```

The aliases use the domain `home`; for another one set the repository variable
`KIWI_DOMAIN` (*Settings → Secrets and variables → Actions → Variables*).

### Records that stay current (recommended)

[contrib/pihole-mullvad-socks.sh](contrib/pihole-mullvad-socks.sh) puts the
current records into Pi-hole's dnsmasq directory, where dnsmasq picks up every
change by itself — no restart, no reload.

1. Let Pi-hole load `/etc/dnsmasq.d`. kiwi-server, in the master's role block of `fleet.yaml`:

   ```yaml
   master:
     dns:
       extra_env: { FTLCONF_misc_etc_dnsmasq_d: "true" }
   ```

   and apply the role again. Any other Pi-hole 6: `misc.etc_dnsmasq_d = true` in `pihole.toml`.

2. On the master, install the script and run it once; it writes
   `90-mullvad-socks.conf` the first time, so restart Pi-hole once after it:

   ```bash
   curl -fsSLo /tmp/pihole-mullvad-socks.sh https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/main/contrib/pihole-mullvad-socks.sh
   sudo install -m 755 /tmp/pihole-mullvad-socks.sh /usr/local/bin/pihole-mullvad-socks.sh
   sudo pihole-mullvad-socks.sh /home/user/docker/km-pihole/etc-dnsmasq.d   # <docker_dir>/km-pihole/etc-dnsmasq.d
   sudo docker restart km-pihole
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
   ExecStart=/usr/local/bin/pihole-mullvad-socks.sh /home/user/docker/km-pihole/etc-dnsmasq.d
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

A download that is not a hosts list (an error page, an empty file) never
replaces the records Pi-hole has.

### Fixed records

[kiwi-extra-records.yaml](https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/kiwi-extra-records.yaml)
holds the same records as a kiwi-server `extra_records` map: paste it into the
master's `dns:` block and apply the role. They stay as they were at render
time.

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
