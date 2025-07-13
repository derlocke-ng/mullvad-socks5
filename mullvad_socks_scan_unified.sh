#!/bin/bash
# Unified Mullvad SOCKS5 Proxy Scanner for local and CI use
# Usage: ./mullvad_socks_scan_unified.sh [output_prefix]

API_URL="https://api.mullvad.net/www/relays/all/"
DNS_SERVER="10.64.0.1"
OUTPUT_PREFIX="${1:-mullvad_socks}" # Default output prefix
OUT_TXT="${OUTPUT_PREFIX}_proxies.txt"
TMP_JSON="/tmp/mullvad_relays.json"

# Fetch Mullvad relays
curl -s "$API_URL" -o "$TMP_JSON"

# Prepare output file
true > "$OUT_TXT"

# Function to get country color
get_country_color() {
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

# Function to resolve internal IP
resolve_ip() {
    local hostname="$1"
    # Try Mullvad's internal DNS if available
    ip=$(dig +short @${DNS_SERVER} "$hostname" 2>/dev/null | grep -E '^[0-9.]+$')
    if [ -n "$ip" ]; then echo "$ip"; return; fi
    # Fallback: public DNS
    ip=$(dig +short "$hostname" 2>/dev/null | grep -E '^[0-9.]+$')
    echo "$ip"
}

jq -r '.[] | select(.type=="wireguard") | select(.socks_name != null) | [.socks_name, .socks_port, .ipv4_addr_in, .country_name, .city_name] | @tsv' "$TMP_JSON" | while IFS=$'\t' read -r socks_name socks_port wan_ip country city; do
    internal_ip=$(resolve_ip "$socks_name")
    if [[ "$internal_ip" =~ ^[0-9.]+$ ]]; then
        color=$(get_country_color "$country")
        cc=$(echo "$country" | awk '{print toupper(substr($1,1,2))}')
        title="$(echo "$socks_name ($wan_ip)" | sed 's/ /%20/g')"
        city_enc="$(echo "$city" | sed 's/ /%20/g')"
        country_enc="$(echo "$country" | sed 's/ /%20/g')"
        # Output line
        echo "socks5://:@$internal_ip:$socks_port?color=$color&title=$title&proxyDns=false&enabled=false&countryCode=$cc&country=$country_enc&patternIncludesAll=false&patternExcludesIntranet=false" >> "$OUT_TXT"
    fi
    # ...existing code...
done

rm -f "$TMP_JSON"
echo "Proxies saved to: $OUT_TXT"
