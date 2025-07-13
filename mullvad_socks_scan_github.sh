#!/bin/bash
# GitHub Actions compatible Mullvad SOCKS5 Proxy Scanner
# This version attempts to work without access to Mullvad's internal DNS

set -euo pipefail

API_URL="https://api.mullvad.net/www/relays/all/"
OUTPUT_PREFIX="${1:-mullvad_socks}" 
TMP_JSON="/tmp/mullvad_relays.json"
FOXY_JSON="${OUTPUT_PREFIX}_foxyproxy.json"

echo "🔍 Fetching Mullvad relay data..."
curl -s "$API_URL" -o "$TMP_JSON"

# Prepare output files
true > "${OUTPUT_PREFIX}_list.txt"
true > "${OUTPUT_PREFIX}_proxifier.txt"
echo '[' > "$FOXY_JSON"
first=1

# Declare associative arrays for per-country outputs
declare -A country_json_files


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
        *) echo "#888888" ;;
    esac
}

# Function to resolve internal IP
resolve_internal_ip() {
    local hostname="$1"
    
    # Try Mullvad's internal DNS if available (when connected to VPN)
    if dig +short @10.64.0.1 "$hostname" 2>/dev/null | grep -E '^[0-9.]+$'; then
        return 0
    fi
    
    # Alternative approach: Try to extract from hostname pattern
    # Mullvad uses predictable patterns, we can attempt to derive internal IPs
    # This is a fallback and might not be 100% accurate
    
    # Try public DNS as fallback (might not work for internal services)
    if dig +short "$hostname" 2>/dev/null | grep -E '^[0-9.]+$'; then
        return 0
    fi
    
    # If all else fails, return empty
    echo ""
}

echo "🌐 Processing WireGuard SOCKS5 relays..."

# Count total relays for progress
total_relays=$(jq '.[] | select(.type=="wireguard") | select(.socks_name != null)' "$TMP_JSON" | jq -s length)
echo "📊 Found $total_relays SOCKS5 relays to process"

processed=0
working_count=0

jq -r '.[] | select(.type=="wireguard") | select(.socks_name != null) | [.socks_name, .socks_port, .ipv4_addr_in, .country_name, .city_name] | @tsv' "$TMP_JSON" | while IFS=$'\t' read -r socks_name socks_port wan_ip country city; do
    processed=$((processed + 1))
    echo -ne "\r🔄 Processing: $processed/$total_relays"
    
    # Try to resolve internal IP
    internal_ip=$(resolve_internal_ip "$socks_name")
    
    if [[ -n "$internal_ip" && "$internal_ip" =~ ^[0-9.]+$ ]]; then
        working_count=$((working_count + 1))
        color=$(get_country_color "$country")
        
        # Generate outputs
        echo "$internal_ip:$socks_port" >> "${OUTPUT_PREFIX}_list.txt"
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
        # Per-country file names
        country_safe=$(echo "$country" | tr ' ' '_' | tr -dc 'A-Za-z0-9_')
        json_file="${OUTPUT_PREFIX}_${country_safe}_foxyproxy.json"
        list_file="${OUTPUT_PREFIX}_${country_safe}_list.txt"
        proxifier_file="${OUTPUT_PREFIX}_${country_safe}_proxifier.txt"

        # Initialize per-country JSON file if not exists
        if [ ! -f "$json_file" ]; then echo '[' > "$json_file"; country_json_files[$country_safe]=0; fi
        # Per-country TXT/Proxifier
        touch "$list_file" "$proxifier_file"

        # Write to per-country TXT
        echo "$internal_ip:$socks_port" >> "$list_file"
        echo "$internal_ip $socks_port SOCKS5" >> "$proxifier_file"

        # Write to per-country JSON
        if [ ${country_json_files[$country_safe]} -eq 0 ]; then country_json_files[$country_safe]=1; else echo ',' >> "$json_file"; fi
        cat <<EOF >> "$json_file"
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
        echo -ne "\r✅ $socks_name -> $internal_ip:$socks_port                    \n"
    else
        echo -ne "\r❌ $socks_name (no internal IP resolved)                    \n"
    fi
done

# Close all per-country JSON arrays
for file in ${!country_json_files[@]}; do
    json_file="${OUTPUT_PREFIX}_${file}_foxyproxy.json"
    echo ']' >> "$json_file"
done

rm -f "$TMP_JSON"

echo ""
echo "📋 Summary:"
echo "  • Total relays processed: $processed"
echo "  • Working proxies found: $working_count"
echo "  • Success rate: $(( working_count * 100 / processed ))%"
echo ""
echo "📁 Output files:"
echo "  • Simple list: ${OUTPUT_PREFIX}_list.txt"
echo "  • Proxifier format: ${OUTPUT_PREFIX}_proxifier.txt"  
echo "  • FoxyProxy JSON: $FOXY_JSON"

# If no VPN connection detected, provide helpful message
if [ $working_count -eq 0 ]; then
    echo ""
    echo "⚠️  No internal IPs were resolved!"
    echo "   This usually means you're not connected to Mullvad VPN."
    echo "   For GitHub Actions, ensure WireGuard secrets are properly configured."
fi
