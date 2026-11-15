# Network Port Forwarding & Remote Access Guide for NAS Web Server

This guide outlines the end-to-end configuration for exposing your Linux NAS server securely to the internet or across your local network.

---

## 1. Network Architecture Overview

```
[ External Client / Internet ]
              |
              v (WAN Public IP: Port 5050 or 80/443)
      [ Home Router / Gateway ]
              | (NAT / Port Forwarding Rule)
              v (LAN IP: e.g., 192.168.1.150:80)
      [ Linux NAS Server ]
          ├── UFW Firewall (allows 80, 443, 5050)
          ├── ModSecurity WAF / OWASP CRS Filter
          ├── Apache 2.4 Reverse Proxy
          └── Gunicorn WSGI (127.0.0.1:5050) -> Flask Application
```

---

## 2. Step 1: Determine the NAS Server's Local Static IP

Before forwarding ports on your router, ensure your NAS server has a static LAN IP address so it does not change after reboot.

Run on the Linux server:
```bash
ip addr show
# Look for your active network interface (e.g. eth0, enp3s0, or wlan0)
# Example output: inet 192.168.1.150/24 brd 192.168.1.255
```

Note your NAS IP (e.g., `192.168.1.150`) and your Gateway / Router IP (`ip route | grep default` -> usually `192.168.1.1`).

---

## 3. Step 2: Configure DHCP Reservation in Your Router

1. Open your web browser and navigate to your router admin panel (typically `http://192.168.1.1` or `http://192.168.0.1`).
2. Log in with your router administrator credentials.
3. Locate **LAN Setup** / **DHCP Server** / **Static Lease**.
4. Add a DHCP reservation binding your NAS server's MAC address to its IP (`192.168.1.150`).

---

## 4. Step 3: Add Port Forwarding Rules in Router

Navigate to **Advanced Settings -> NAT / Port Forwarding / Virtual Server**:

Create the following forwarding rules:

| Rule Name | External / WAN Port | Protocol | Internal / LAN IP | Internal Port | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **NAS-Web-HTTP** | `80` (or `8080`) | TCP | `192.168.1.150` | `80` | Enabled |
| **NAS-Web-HTTPS** | `443` (or `8443`)| TCP | `192.168.1.150` | `443` | Enabled |
| **NAS-Direct-Port** | `5050` | TCP | `192.168.1.150` | `5050` | Enabled |

*Tip: If your Internet Service Provider (ISP) blocks inbound port 80, use external port 5050 or 8080 mapping to internal port 80.*

---

## 5. Step 4: Verify Firewall Configuration on Linux

Ensure the Linux UFW firewall allows the forwarded traffic:

```bash
sudo ufw allow 80/tcp comment 'NAS Web HTTP'
sudo ufw allow 443/tcp comment 'NAS Web HTTPS'
sudo ufw allow 5050/tcp comment 'NAS Gunicorn Direct'
sudo ufw status verbose
```

---

## 6. Step 5: Test Remote Connectivity

1. Find your public WAN IP by running:
   ```bash
   curl ifconfig.me
   ```
   *(Example: `203.0.113.45`)*
2. Using a mobile network (cellular data) or an external connection outside your home Wi-Fi:
   - Navigate to: `http://203.0.113.45:5050/` or `http://203.0.113.45/`
3. You should see the **Linux NAS Portal** login screen.

---

## 7. Step 6: Dynamic DNS (DDNS) Configuration

Since residential ISPs assign dynamic IP addresses that change over time, configure Dynamic DNS:

1. Register a free hostname with a DDNS provider (e.g., [DuckDNS](https://www.duckdns.org) or [No-IP](https://www.noip.com)).
2. Configure the DDNS updater on your router under **Advanced -> DDNS**, or run a lightweight Linux cron script:
   ```bash
   echo "*/10 * * * * root curl -s 'https://www.duckdns.org/update?domains=MYNAS&token=MYTOKEN&ip=' >/dev/null 2>&1" | sudo tee /etc/cron.d/duckdns
   ```
3. Now access your NAS anywhere using your domain: `http://MYNAS.duckdns.org:5050/`.

---

## 8. Security Best Practices for Public NAS Port Forwarding

1. **Active WAF**: The built-in Web Application Firewall and ModSecurity inspect all incoming queries and block SQL injection, XSS, and directory traversal attempts.
2. **ClamAV Antivirus**: All remote uploads are quarantined and scanned before reaching NAS disk storage.
3. **Strong Password Policies**: Keep default passwords disabled.
4. **Zero-Trust Alternative (Cloudflare Tunnel)**:
   If your ISP uses CGNAT (Carrier-Grade NAT) or blocks inbound ports, install `cloudflared`:
   ```bash
   cloudflared tunnel --url http://localhost:80
   ```
   This gives you a secure, encrypted HTTPS URL with zero port forwarding required.
