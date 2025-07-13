#!/bin/bash
# GitHub Actions compatible Mullvad SOCKS5 Proxy Scanner
# This version attempts to work without access to Mullvad's internal DNS

set -euo pipefail

API_URL="https://api.mullvad.net/www/relays/all/"
OUTPUT_PREFIX="${1:-mullvad_socks}"
TMP_JSON="/tmp/mullvad_relays.json"
PROXY_TXT="${OUTPUT_PREFIX}_proxy.txt"

# Check if Mullvad internal DNS is available
if dig +short @10.64.0.1 mullvad.net &>/dev/null; then
    DNS_SERVER="10.64.0.1"
    echo "Using Mullvad internal DNS ($DNS_SERVER)"
else
    DNS_SERVER=""
    echo "Mullvad internal DNS not available, will try public DNS"
fi

# Fetch Mullvad relays
curl -s "$API_URL" -o "$TMP_JSON"
true > "$PROXY_TXT"

get_country_code() {
    local country="$1"
    case "$country" in
        "Albania") echo "AL" ;;
        "Australia") echo "AU" ;;
        "Austria") echo "AT" ;;
        "Belgium") echo "BE" ;;
        "Brazil") echo "BR" ;;
        "Bulgaria") echo "BG" ;;
        "Canada") echo "CA" ;;
        "Chile") echo "CL" ;;
        "Colombia") echo "CO" ;;
        "Croatia") echo "HR" ;;
        "Cyprus") echo "CY" ;;
        "Czech Republic") echo "CZ" ;;
        "Denmark") echo "DK" ;;
        "Estonia") echo "EE" ;;
        "Finland") echo "FI" ;;
        "France") echo "FR" ;;
        "Germany") echo "DE" ;;
        "Greece") echo "GR" ;;
        "Hong Kong") echo "HK" ;;
        "Hungary") echo "HU" ;;
        "Indonesia") echo "ID" ;;
        "Ireland") echo "IE" ;;
        "Israel") echo "IL" ;;
        "Italy") echo "IT" ;;
        "Japan") echo "JP" ;;
        "Malaysia") echo "MY" ;;
        "Mexico") echo "MX" ;;
        "Netherlands") echo "NL" ;;
        "New Zealand") echo "NZ" ;;
        "Nigeria") echo "NG" ;;
        "Norway") echo "NO" ;;
        "Peru") echo "PE" ;;
        "Philippines") echo "PH" ;;
        "Poland") echo "PL" ;;
        "Portugal") echo "PT" ;;
        "Romania") echo "RO" ;;
        "Serbia") echo "RS" ;;
        "Singapore") echo "SG" ;;
        "Slovakia") echo "SK" ;;
        "Slovenia") echo "SI" ;;
        "South Africa") echo "ZA" ;;
        "Spain") echo "ES" ;;
        "Sweden") echo "SE" ;;
        "Switzerland") echo "CH" ;;
        "Thailand") echo "TH" ;;
        "Turkey") echo "TR" ;;
        "Ukraine") echo "UA" ;;
        "United Kingdom") echo "GB" ;;
        "United States") echo "US" ;;
        *) echo "XX" ;;
    esac
}

get_color() {
    # Use the same color logic as before
    case "$1" in
        "Albania") echo "ff4444" ;;
        "Australia") echo "ffaa00" ;;
        "Austria") echo "ff0000" ;;
        "Belgium") echo "ffff00" ;;
        "Brazil") echo "00aa00" ;;
        "Bulgaria") echo "00ff00" ;;
        "Canada") echo "ff0066" ;;
        "Chile") echo "0000ff" ;;
        "Colombia") echo "ffff66" ;;
        "Croatia") echo "ff6600" ;;
        "Cyprus") echo "00ffff" ;;
        "Czech Republic") echo "aa00aa" ;;
        "Denmark") echo "ff0000" ;;
        "Estonia") echo "0066ff" ;;
        "Finland") echo "ffffff" ;;
        "France") echo "0055aa" ;;
        "Germany") echo "000000" ;;
        "Greece") echo "0088ff" ;;
        "Hong Kong") echo "ff8800" ;;
        "Hungary") echo "00aa00" ;;
        "Indonesia") echo "ff4400" ;;
        "Ireland") echo "00ff44" ;;
        "Israel") echo "0044ff" ;;
        "Italy") echo "00aa44" ;;
        "Japan") echo "ff0044" ;;
        "Malaysia") echo "ffaa44" ;;
        "Mexico") echo "aa4400" ;;
        "Netherlands") echo "ff6644" ;;
        "New Zealand") echo "44ff00" ;;
        "Nigeria") echo "00aa88" ;;
        "Norway") echo "4400ff" ;;
        "Peru") echo "ff8844" ;;
        "Philippines") echo "aa0044" ;;
        "Poland") echo "ff4488" ;;
        "Portugal") echo "44aa00" ;;
        "Romania") echo "8800ff" ;;
        "Serbia") echo "aa4488" ;;
        "Singapore") echo "ff0088" ;;
        "Slovakia") echo "88ff00" ;;
        "Slovenia") echo "0088aa" ;;
        "South Africa") echo "ffaa88" ;;
        "Spain") echo "aa8800" ;;
        "Sweden") echo "0044aa" ;;
        "Switzerland") echo "ff4400" ;;
        "Thailand") echo "8844ff" ;;
        "Turkey") echo "ff8800" ;;
        "Ukraine") echo "0088ff" ;;
        "United Kingdom") echo "aa0088" ;;
        "United States") echo "4488ff" ;;
        *) echo "888888" ;;
    esac
}

resolve_ip() {
    local hostname="$1"
    local ip=""
    if [ -n "$DNS_SERVER" ]; then
        ip=$(dig +short @"$DNS_SERVER" "$hostname" 2>/dev/null)
    fi
    if [[ ! "$ip" =~ ^[0-9.]+$ ]]; then
        ip=$(dig +short "$hostname" 2>/dev/null)
    fi
    echo "$ip"
}

echo "🌐 Processing WireGuard SOCKS5 relays..."

# Count total relays for progress
total_relays=$(jq '.[] | select(.type=="wireguard") | select(.socks_name != null)' "$TMP_JSON" | jq -s length)
echo "📊 Found $total_relays SOCKS5 relays to process"

processed=0
working_count=0

jq -r '.[] | select(.type=="wireguard") | select(.socks_name != null) | [.socks_name, .socks_port, .ipv4_addr_in, .country_name, .city_name] | @tsv' "$TMP_JSON" | while IFS=$'\t' read -r socks_name socks_port wan_ip country _; do
    internal_ip=$(resolve_ip "$socks_name")
    if [[ "$internal_ip" =~ ^[0-9.]+$ ]]; then
        country_code=$(get_country_code "$country")
        color=$(get_color "$country")
        title="$socks_name ($wan_ip)"
        url="socks5://$internal_ip:$socks_port?color=$color&title=$(echo $title | sed 's/ /%20/g')&proxyDns=false&enabled=false&countryCode=$country_code&country=$(echo $country | sed 's/ /%20/g')&patternIncludesAll=false&patternExcludesIntranet=false"
        echo "$url" >> "$PROXY_TXT"
        echo "✓ $socks_name -> $internal_ip:$socks_port is UP"
    else
        echo "✗ $socks_name is DOWN"
    fi
done

rm -f "$TMP_JSON"
echo "\nProxy URLs saved to: $PROXY_TXT"
