# Internal Wi-Fi Platform v0.5

Offline-first private-network foundation for Raspberry Pi deployment.

## Default network
- SSID: `InternalNet`
- Subnet: `192.168.50.0/24`
- Gateway: `192.168.50.1`
- DHCP: `192.168.50.100`–`192.168.50.200`
- Local DNS domain: `.internal`
- Internet uplink: disabled

## v0.5
- Authenticated administrative API
- Raspberry Pi apply mode with rollback snapshots
- hostapd, dnsmasq and nftables configuration generation
- Boot-time systemd service
- Internet forwarding is forced off
- WPA credential and admin-token validation before privileged apply

Production secrets must be supplied through protected environment/configuration and are not stored in this repository.
