#!/bin/sh
# Keep Pi-hole's DNS records for the Mullvad SOCKS5 proxies current.
#
#   pihole-mullvad-socks.sh <dir>
#
# <dir> is the host directory Pi-hole mounts at /etc/dnsmasq.d, for a kiwi-server
# master ${DOCKERDIR}/km-pihole/etc-dnsmasq.d. The first run writes
# <dir>/90-mullvad-socks.conf (hostsdir=/etc/dnsmasq.d/mullvad-socks): restart
# Pi-hole once to load it, with misc.etc_dnsmasq_d=true (kiwi-server:
# dns: { extra_env: { FTLCONF_misc_etc_dnsmasq_d: "true" } }). Every run puts
# the current list into <dir>/mullvad-socks/, which dnsmasq watches and reloads
# by itself. Run it from a timer; see the README.
#
# MULLVAD_SOCKS_HOSTS_URL overrides where the list comes from.
set -eu

url="${MULLVAD_SOCKS_HOSTS_URL:-https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad-socks.hosts}"
dir="${1:?usage: $0 <directory Pi-hole mounts at /etc/dnsmasq.d>}"
hostsdir="$dir/mullvad-socks"
conf="$dir/90-mullvad-socks.conf"

[ -d "$dir" ] || { echo "$dir: no such directory" >&2; exit 1; }
mkdir -p "$hostsdir"

if [ ! -f "$conf" ]; then
    printf '# written by pihole-mullvad-socks.sh: the Mullvad SOCKS5 records, reloaded on change\nhostsdir=/etc/dnsmasq.d/mullvad-socks\n' >"$conf"
    chmod 644 "$conf"
    echo "wrote $conf: restart Pi-hole once to load it"
fi

# dnsmasq ignores dotfiles in a hostsdir, so the download lands next to the
# list and replaces it in one rename
tmp=$(mktemp "$hostsdir/.mullvad-socks.XXXXXX")
trap 'rm -f "$tmp"' EXIT INT TERM
curl -fsSL --retry 3 --max-time 60 -o "$tmp" "$url"

# only comments and "IPv4 name" lines, and at least one record: never hand
# dnsmasq an error page or an empty list
if grep -Eqv '^(#.*|[0-9]{1,3}(\.[0-9]{1,3}){3} [A-Za-z0-9.-]+)?$' "$tmp" ||
   ! grep -Eq '^[0-9]' "$tmp"; then
    echo "$url: not a hosts list, keeping the current one" >&2
    exit 1
fi

if cmp -s "$tmp" "$hostsdir/mullvad-socks.hosts"; then
    exit 0
fi
chmod 644 "$tmp"
mv -f "$tmp" "$hostsdir/mullvad-socks.hosts"
echo "updated $hostsdir/mullvad-socks.hosts: $(grep -c '^[0-9]' "$hostsdir/mullvad-socks.hosts") records"
