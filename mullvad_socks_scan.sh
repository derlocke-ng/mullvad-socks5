#!/bin/bash
# Simple Mullvad SOCKS5 Proxy Scanner using dig and Mullvad API
# Usage: ./mullvad_socks_scan.sh [output_prefix]

API_URL="https://api.mullvad.net/www/relays/all/"
DNS_SERVER="10.64.0.1"
OUTPUT_PREFIX="${1:-mullvad_socks}" # Default output prefix
TMP_JSON="/tmp/mullvad_relays.json"
FOXY_JSON="${OUTPUT_PREFIX}_foxyproxy.json"

# Fetch Mullvad relays
curl -s "$API_URL" -o "$TMP_JSON"

# Prepare FoxyProxy JSON array
echo '[' > "$FOXY_JSON"
first=1

# Function to get country color
get_country_color() {
    case "$1" in
        "Albania") echo "#ff4444" ;;
        "Australia") echo "#ffaa00" ;;
        "Austria") echo "#ff0000" ;;
        "Belgium") echo "#ffff00" ;;
        "Brazil") echo "#00aa00" ;;
        "Bulgaria") echo "#00ff00" ;;
        "Canada") echo "#ff0066" ;;
        "Chile") echo "#0000ff" ;;
        "Colombia") echo "#ffff66" ;;
        "Croatia") echo "#ff6600" ;;
        "Cyprus") echo "#00ffff" ;;
        "Czech Republic") echo "#aa00aa" ;;
        "Denmark") echo "#ff0000" ;;
        "Estonia") echo "#0066ff" ;;
        "Finland") echo "#ffffff" ;;
        "France") echo "#0055aa" ;;
        "Germany") echo "#000000" ;;
        "Greece") echo "#0088ff" ;;
        "Hong Kong") echo "#ff8800" ;;
        "Hungary") echo "#00aa00" ;;
        "Indonesia") echo "#ff4400" ;;
        "Ireland") echo "#00ff44" ;;
        "Israel") echo "#0044ff" ;;
        "Italy") echo "#00aa44" ;;
        "Japan") echo "#ff0044" ;;
        "Malaysia") echo "#ffaa44" ;;
        "Mexico") echo "#aa4400" ;;
        "Netherlands") echo "#ff6644" ;;
        "New Zealand") echo "#44ff00" ;;
        "Nigeria") echo "#00aa88" ;;
        "Norway") echo "#4400ff" ;;
        "Peru") echo "#ff8844" ;;
        "Philippines") echo "#aa0044" ;;
        "Poland") echo "#ff4488" ;;
        "Portugal") echo "#44aa00" ;;
        "Romania") echo "#8800ff" ;;
        "Serbia") echo "#aa4488" ;;
        "Singapore") echo "#ff0088" ;;
        "Slovakia") echo "#88ff00" ;;
        "Slovenia") echo "#0088aa" ;;
        "South Africa") echo "#ffaa88" ;;
        "Spain") echo "#aa8800" ;;
        "Sweden") echo "#0044aa" ;;
        "Switzerland") echo "#ff4400" ;;
        "Thailand") echo "#8844ff" ;;
        "Turkey") echo "#ff8800" ;;
        "Ukraine") echo "#0088ff" ;;
        "United Kingdom") echo "#aa0088" ;;
        "United States") echo "#4488ff" ;;
        *) echo "#888888" ;; # Default gray for unknown countries
    esac
}

jq -r '.[] | select(.type=="wireguard") | select(.socks_name != null) | [.socks_name, .socks_port, .ipv4_addr_in, .country_name, .city_name] | @tsv' "$TMP_JSON" | while IFS=$'\t' read -r socks_name socks_port wan_ip country city; do
    # Get internal IP using dig
    internal_ip=$(dig +short @"$DNS_SERVER" "$socks_name")
    if [[ "$internal_ip" =~ ^[0-9.]+$ ]]; then
        # Get country-specific color
        color=$(get_country_color "$country")
        
        echo "$internal_ip:$socks_port" >> "${OUTPUT_PREFIX}_list.txt"
        # Proxifier config (TXT): Host Port Protocol
        echo "$internal_ip $socks_port SOCKS5" >> "${OUTPUT_PREFIX}_proxifier.txt"
        # FoxyProxy JSON
        if [ $first -eq 0 ]; then echo ',' >> "$FOXY_JSON"; fi
        first=0
        cat <<EOF >> "$FOXY_JSON"
{
  "title": "$socks_name ($wan_ip)",
  "type": 3,
  "host": "$internal_ip",
  "port": $socks_port,
  "username": "",
  "password": "",
  "proxyDNS": true,
  "active": true,
  "color": "$color",
  "country": "$country",
  "city": "$city"
}
EOF
        echo "✓ $socks_name -> $internal_ip:$socks_port is UP"
    else
        echo "✗ $socks_name is DOWN"
    fi
done

echo ']' >> "$FOXY_JSON"
rm -f "$TMP_JSON"
echo "\nWorking proxies saved to: ${OUTPUT_PREFIX}_list.txt"
echo "Proxifier TXT: ${OUTPUT_PREFIX}_proxifier.txt"
echo "FoxyProxy JSON: $FOXY_JSON"
