# Copilot Instructions for Mullvad SOCKS5 Proxy Scanner

## Project Overview
- This repository automates the discovery and publication of Mullvad SOCKS5 proxy endpoints using WireGuard VPN credentials.
- Outputs proxy lists in three formats: simple list, Proxifier, and FoxyProxy JSON (with country-based color coding).
- Designed for both local use and automated GitHub Actions workflows.

## Key Components
- `mullvad_socks_scan.sh`: Main Bash script for scanning proxies when connected to Mullvad VPN. Uses Mullvad API, internal DNS, and generates output files.
- `mullvad_socks_scan_github.sh`: GitHub Actions-compatible scanner. Attempts to resolve internal IPs even without VPN, with fallback logic.
- `.github/workflows/mullvad-proxy-scan.yml`: GitHub Actions workflow. Sets up WireGuard, runs the scanner, uploads results as artifacts/releases, and cleans up.
- `README.md`: Contains setup, usage, and troubleshooting instructions. Always reference this for user-facing documentation.

## Developer Workflows
- **Local Run:**
  - Connect to Mullvad VPN.
  - Run: `./mullvad_socks_scan.sh <output_prefix>`
  - Output: `<output_prefix>_list.txt`, `<output_prefix>_proxifier.txt`, `<output_prefix>_foxyproxy.json`
- **GitHub Actions:**
  - Requires secrets: `MULLVAD_PRIVATE_KEY`, `MULLVAD_ADDRESS`, `MULLVAD_SERVER_PUBLIC_KEY`, `MULLVAD_SERVER_ENDPOINT`.
  - Workflow runs every 6 hours or on manual trigger.
  - Results published as artifacts and releases.

## Patterns & Conventions
- **Country Color Coding:**
  - Both scripts use a hardcoded Bash function to assign colors per country for FoxyProxy JSON.
- **Internal IP Resolution:**
  - Local script uses Mullvad's internal DNS (`10.64.0.1`).
  - GitHub script attempts DNS, then falls back to hostname pattern or public DNS.
- **Output File Naming:**
  - All output files use the provided prefix, defaulting to `mullvad_socks` or `mullvad_proxies` in CI.
- **Cleanup:**
  - Old proxy files (>10 days) are deleted in CI.
  - WireGuard interface is always brought down after workflow.

## Integration Points
- **Mullvad API:**
  - Relays fetched from `https://api.mullvad.net/www/relays/all/`.
- **WireGuard:**
  - VPN connection required for full scanning. Config generated from user secrets.
- **GitHub Actions:**
  - Uses `actions/checkout`, `actions/upload-artifact`, and `softprops/action-gh-release`.

## Troubleshooting
- Always check the workflow logs for connection or authentication errors.
- If no proxies are found, verify VPN connection and secrets.
- For local runs, ensure you are connected to Mullvad VPN and have required tools (`curl`, `jq`, `dig`).

## Example: Adding a New Output Format
- Extend the main scan script(s) to generate the new format after the proxy is verified.
- Update workflow to include the new file in artifact/release steps.

---

For any unclear conventions or missing details, consult `README.md` or ask the user for clarification.
