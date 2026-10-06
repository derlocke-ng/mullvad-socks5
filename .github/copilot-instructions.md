# Copilot Instructions for the Mullvad SOCKS5 proxy lists

## Project Overview
- Builds lists of Mullvad's SOCKS5 proxies (one per WireGuard relay) and publishes them to the `list` branch and the `latest-proxies` release, every 6 hours.
- A proxy's name (`xx-yyy-wg-socks5-NNN.relays.mullvad.net`) resolves in public DNS to its address in `10.124.0.0/16`, so building needs no VPN; the addresses only answer through a Mullvad connection.
- Based on [maximko/mullvad-socks-list](https://github.com/maximko/mullvad-socks-list).

## Key Components
- `mullvad_socks_list.py`: the generator. Python 3.9+, standard library only. Reads `https://api.mullvad.net/www/relays/wireguard/` (or `--relays FILE`), keeps active relays with a `socks_name`, resolves the names, optionally checks a SOCKS5 greeting (`--check`), writes every output into `--out`.
- `.github/workflows/mullvad-proxy-scan.yml`: schedule, keepalive (enables itself through the API), tests, optional WireGuard tunnel for `--check`, publish to `list` through a separate git worktree, release upload.
- `contrib/pihole-mullvad-socks.sh`: keeps a Pi-hole's records current (dnsmasq `hostsdir`, reloaded by inotify).
- `tests/`: `python3 -m unittest discover -s tests`; offline, DNS and the SOCKS5 check are mocked; `tests/relays.json` is a sample of the API.

## Outputs (`list` branch)
- `mullvad-socks-list.txt` / `mullvad-socks.json`: detailed table / data.
- `foxyproxy.json` / `foxyproxy.txt` (+ `-hostnames` variants): FoxyProxy 8 "Import from URL" (`{"data": [...]}` only) and "Import Proxy List" (`socks5://host:port?title=&cc=&city=&color=&proxyDNS=`). FoxyProxy draws the flag from `cc`.
- `mullvad-socks.hosts`, `kiwi-extra-records.yaml`: DNS records, Mullvad name plus alias `<cc>-<city>-<n>.mullvad.<KIWI_DOMAIN>`.
- `mullvad_proxies_proxy.txt`: same as `foxyproxy.txt`, kept for old links.

## Conventions
- Country codes, names and cities come from the API, never from a hardcoded table; colours are derived from the country code.
- Outputs are deterministic except `README.md` (build time): the workflow commits only when something else changed.
- Guards: fewer than half the names resolving fails the run; fewer than half the proxies answering `--check` means the tunnel is broken and the lists are published unchecked.
- Adding an output: write it in `main()`'s `files`, list it in `readme()` and `README.md`, add a test.
