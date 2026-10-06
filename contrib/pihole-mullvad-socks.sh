#!/bin/sh
# Keep Pi-hole's DNS records for the Mullvad SOCKS5 proxies current.
#
#   pihole-mullvad-socks.sh <dir>
#
# <dir> holds the records, mullvad-socks.hosts: a directory of root's, outside
# Pi-hole's own writable directories — this runs as root, so nothing Pi-hole
# runs may write where it works. Point Pi-hole at it once with a dnsmasq line,
# hostsdir=<dir as Pi-hole sees it>, and dnsmasq reloads every change by
# itself. In docker, mount <dir> read-only (see the README). kiwi-server 2.2.0
# and later do all of this themselves (dns.mullvad_socks).
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
dir="${1:?usage: $0 <directory for the records, read-only for Pi-hole>}"
hosts=mullvad-socks.hosts

# Work only in a directory that is exactly this path (not a link to another),
# belongs to whoever runs this and is writable by nobody else, by relative
# names: no one else can swap a file under root's hands.
mkdir -p "$dir"
cd "$dir"
case $(stat -c %A .) in ?????w*|????????w*) writable=1 ;; *) writable=0 ;; esac
if [ "$(stat -c %d:%i .)" != "$(stat -c %d:%i "$dir")" ] || [ "$(stat -c %u .)" != "$(id -u)" ] ||
   [ "$writable" = 1 ]; then
    echo "$dir must be a directory of $(id -un)'s that nobody else can write to — leaving it alone" >&2
    exit 1
fi

# dnsmasq ignores dotfiles in a hostsdir: nothing is visible before the rename
raw=$(mktemp .download.XXXXXX)
new=$(mktemp .hosts.XXXXXX)
trap 'rm -f "$raw" "$new"' EXIT INT TERM
curl -fsSL --proto-redir =https --max-filesize 10000000 --retry 3 --retry-delay 5 --max-time 120 -o "$raw" "$url"

if ! awk -v short="$short" '
    BEGIN { if (short !~ /^([a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*)?$/) { bad = 1; exit } }
    { sub(/\r$/, "") }
    /^[ \t]*(#|$)/ { next }
    !/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[ \t]+[A-Za-z0-9.-]+[ \t]*$/ { bad = 1; exit }
    {
        ip = $1; name = tolower($2)
        # no leading zeros: some resolvers read 010 as octal
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

if [ -f "$hosts" ] && [ ! -L "$hosts" ] && cmp -s "$new" "$hosts"; then
    exit 0
fi
chmod 644 "$new"
mv -fT "$new" "$hosts"
echo "updated $dir/$hosts: $(wc -l <"$hosts") records"
