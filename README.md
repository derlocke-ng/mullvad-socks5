# Mullvad SOCKS5 Proxy Scanner

Automated GitHub workflow that scans and generates Mullvad SOCKS5 proxy lists in multiple formats.

## Features

- 🔄 **Automated scanning** - Runs every 6 hours via GitHub Actions
- 🎯 **Multiple formats** - Generates lists for different proxy tools
- 🌍 **Country-based colors** - Color-coded by country for FoxyProxy
- 📦 **Automatic releases** - Downloads available as GitHub releases
- 🔒 **Secure** - Uses GitHub Secrets for credentials

## Output Formats

### 1. Simple List (`*_list.txt`)
```
10.124.0.155:1080
10.124.0.212:1080
...
```

### 2. Proxifier Format (`*_proxifier.txt`)
```
10.124.0.155 1080 SOCKS5
10.124.0.212 1080 SOCKS5
...
```

### 3. FoxyProxy JSON (`*_foxyproxy.json`)
```json
[
  {
    "title": "al-tia-wg-socks5-001.relays.mullvad.net (31.171.153.66)",
    "type": 3,
    "host": "10.124.0.155",
    "port": 1080,
    "username": "",
    "password": "",
    "proxyDNS": true,
    "active": true,
    "color": "#ff4444",
    "country": "Albania",
    "city": "Tirana"
  }
]
```

## Setup Instructions

### 1. Fork this repository

### 2. Generate Mullvad WireGuard configuration
1. Log into your [Mullvad account](https://mullvad.net/account)
2. Go to "WireGuard configuration"
3. Generate a new configuration
4. Download the `.conf` file

### 3. Extract credentials from the config file
From your downloaded WireGuard config file, extract:

```ini
[Interface]
PrivateKey = MULLVAD_PRIVATE_KEY
Address = MULLVAD_ADDRESS
DNS = 10.64.0.1

[Peer]
PublicKey = MULLVAD_SERVER_PUBLIC_KEY
Endpoint = MULLVAD_SERVER_ENDPOINT (as IP:PORT)
AllowedIPs = 10.64.0.0/10
```

### 4. Set GitHub Secrets
Go to your forked repository → Settings → Secrets and variables → Actions

Add these secrets:
- `MULLVAD_PRIVATE_KEY`: Your private key from `[Interface]` section
- `MULLVAD_ADDRESS`: Your address from `[Interface]` section (e.g., `10.64.0.2/32`)
- `MULLVAD_SERVER_PUBLIC_KEY`: Public key from `[Peer]` section
- `MULLVAD_SERVER_ENDPOINT`: Endpoint from `[Peer]` section (e.g., `123.45.67.89:51820`)

### 5. Enable GitHub Actions
1. Go to the "Actions" tab in your repository
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow will run automatically every 6 hours

### 6. Manual trigger (optional)
You can manually trigger the workflow:
1. Go to Actions → "Mullvad SOCKS5 Proxy Scanner"
2. Click "Run workflow"

## Security Notes

⚠️ **Important Security Considerations:**

1. **Use a dedicated Mullvad device** - Generate a separate WireGuard config just for this automation
2. **Limit the config scope** - Use `AllowedIPs = 10.64.0.0/10` instead of `0.0.0.0/0` to only route Mullvad internal traffic
3. **Regular rotation** - Regenerate your WireGuard keys periodically
4. **Monitor usage** - Check your Mullvad account for unexpected usage

## Download Latest Results

The latest proxy lists are available as:
1. **GitHub Releases** - Download from the [Releases page](../../releases)
2. **Artifacts** - Available for 30 days after each run in the Actions tab

## Local Usage

You can also run the scanner locally if you're connected to Mullvad VPN:

```bash
chmod +x mullvad_socks_scan.sh
./mullvad_socks_scan.sh my_proxy_list
```

## How It Works

1. **Connects to Mullvad** - Uses WireGuard to establish VPN connection
2. **Fetches relay data** - Downloads current relay information from Mullvad API
3. **Resolves internal IPs** - Uses Mullvad's internal DNS (10.64.0.1) to resolve SOCKS5 hostnames
4. **Tests connectivity** - Verifies each proxy is accessible
5. **Generates output** - Creates formatted lists for different proxy tools
6. **Publishes results** - Uploads as GitHub release artifacts

## Troubleshooting

### Workflow fails with "Connection failed"
- Check that your Mullvad account is active
- Verify the WireGuard configuration secrets are correct
- Ensure the endpoint server is online

### Empty proxy lists
- Your Mullvad account might not have SOCKS5 access
- Check if your subscription includes proxy features

### Authentication errors
- Regenerate your WireGuard configuration
- Update the GitHub secrets with new values

## License

MIT License - Feel free to fork and modify for your needs.
