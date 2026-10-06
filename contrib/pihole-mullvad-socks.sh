#!/bin/sh
# Keep Pi-hole's DNS records for the Mullvad SOCKS5 proxies current.
#
#   pihole-mullvad-socks.sh <dir>
#
# <dir> is the host directory Pi-hole mounts at /etc/dnsmasq.d (or /etc/dnsmasq.d
# itself on a Pi-hole installed without docker). The first run writes
# <dir>/90-mullvad-socks.conf (hostsdir=/etc/dnsmasq.d/mullvad-socks): restart
# Pi-hole once to load it, with misc.etc_dnsmasq_d=true. Every run puts the
# current records into <dir>/mullvad-socks/, which dnsmasq watches and reloads
# by itself. Run it from a timer; see the README. kiwi-server 2.2.0 and later
# do all of this themselves (dns.mullvad_socks).
#
# Only *.relays.mullvad.net names at 10.x.x.x addresses are taken from the list,
# so it can never redirect another name; short names <cc>-<city>-<n>.<domain>
# are added here.
#   MULLVAD_SOCKS_HOSTS_URL  the list (default: this repository's list branch)
#   MULLVAD_SOCKS_DOMAIN     domain of the short names (default: mullvad.home; empty: none)
set -eu
umask 022

url="${MULLVAD_SOCKS_HOSTS_URL:-https://raw.githubusercontent.com/derlocke-ng/mullvad-socks5/list/mullvad-socks.hosts}"
short=$(printf '%s' "${MULLVAD_SOCKS_DOMAIN-mullvad.home}" | tr '[:upper:]' '[:lower:]' | sed 's/^\.*//; s/\.*$//')
base="${1:?usage: $0 <directory Pi-hole mounts at /etc/dnsmasq.d>}"
dir="$base/mullvad-socks"
conf=90-mullvad-socks.conf

# Pi-hole (its container, too) can write in <dir>: work in it by relative
# names, never through a link something put there
[ -d "$base" ] || { echo "$base: no such directory" >&2; exit 1; }
cd "$base"
if [ ! -e "$conf" ] && [ ! -L "$conf" ]; then
    tmp=$(mktemp .mullvad-socks-conf.XXXXXX)
    printf '# written by pihole-mullvad-socks.sh: the Mullvad SOCKS5 records, reloaded on change\nhostsdir=/etc/dnsmasq.d/mullvad-socks\n' >"$tmp"
    chmod 644 "$tmp"
    mv -fT "$tmp" "$conf"
    echo "wrote $base/$conf: restart Pi-hole once to load it"
fi
mkdir -p mullvad-socks
cd mullvad-socks
if [ "$(stat -c %d:%i .)" != "$(stat -c %d:%i "$dir")" ]; then
    echo "$dir is not a plain directory, leaving it alone" >&2
    exit 1
fi
# Pi-hole reads it as its own user, whatever the umask was when it was made
chmod 755 .

# dnsmasq ignores dotfiles in a hostsdir: nothing is visible before the rename
raw=$(mktemp .download.XXXXXX)
new=$(mktemp .hosts.XXXXXX)
trap 'rm -f "$raw" "$new"' EXIT INT TERM
curl -fsSL --proto-redir =https --retry 3 --max-time 120 --max-filesize 10000000 -o "$raw" "$url"

if ! awk -v short="$short" '
    { sub(/\r$/, "") }
    /^[ \t]*(#|$)/ { next }
    !/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[ \t]+[A-Za-z0-9.-]+[ \t]*$/ { bad = 1; exit }
    {
        ip = $1; name = tolower($2)
        if (ip !~ /^10\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/) next
        if (name !~ /^[a-z0-9-]+\.relays\.mullvad\.net$/) next
        split(ip, o, ".")
        if (o[2] > 255 || o[3] > 255 || o[4] > 255 || name in seen) next
        seen[name] = 1
        print ip " " name
        n++
        if (short != "" && match(name, /^[a-z][a-z]-[a-z0-9]+-wg-socks5-[0-9]+\./)) {
            label = substr(name, 1, RLENGTH - 1)
            sub(/-wg-socks5-/, "-", label)
            alias[n] = ip " " label "." short
        }
    }
    END {
        if (bad || n == 0) exit 1
        for (i = 1; i <= n; i++) if (i in alias) print alias[i]
    }' "$raw" >"$new"; then
    echo "$url: not a list of Mullvad SOCKS5 proxies, keeping the current records" >&2
    exit 1
fi

if cmp -s "$new" mullvad-socks.hosts; then
    exit 0
fi
chmod 644 "$new"
mv -fT "$new" mullvad-socks.hosts
echo "updated $dir/mullvad-socks.hosts: $(wc -l <mullvad-socks.hosts) records"
