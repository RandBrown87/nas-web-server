#!/bin/bash
# ==============================================================================
# Linux NAS Server - Production Setup, Hardening & Deployment Script
# Targets: Ubuntu 22.04 / 24.04 LTS, Debian 11 / 12
# Tasks covered:
#  - Package installation (Apache, MySQL, Python3, ClamAV, UFW)
#  - Linux storage directory creation & permission hardening (chmod 770 / chown www-data)
#  - ClamAV Malware Protection Gateway service setup
#  - ModSecurity Web Application Firewall (WAF) integration
#  - UFW (Uncomplicated Firewall) rule configuration
#  - Systemd production service registration & startup
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (use sudo ./deploy/setup_server.sh)"
  exit 1
fi

echo "[*] Step 1: Updating system packages..."
apt-get update -y
apt-get install -y \
    apache2 \
    libapache2-mod-security2 \
    mysql-server \
    python3 \
    python3-venv \
    python3-pip \
    clamav \
    clamav-daemon \
    ufw \
    curl \
    git

echo "[*] Step 2: Creating Linux storage, backup, and quarantine directories..."
mkdir -p /srv/nas_storage
mkdir -p /srv/nas_backups
mkdir -p /srv/nas_quarantine
mkdir -p /srv/nas-web-server

# Set strict permissions: owned by www-data (Apache & NAS service), readable/writable by group only
chown -R www-data:www-data /srv/nas_storage /srv/nas_backups /srv/nas_quarantine
chmod -R 770 /srv/nas_storage /srv/nas_backups /srv/nas_quarantine

echo "[*] Step 3: Configuring ClamAV Antivirus Daemon..."
systemctl stop clamav-freshclam || true
freshclam || true
systemctl enable --now clamav-freshclam
systemctl enable --now clamav-daemon
# Allow www-data access to clamav daemon socket
usermod -aG clamav www-data || true

echo "[*] Step 4: Configuring Linux UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH Remote Management'
ufw allow 80/tcp comment 'NAS HTTP Web Portal'
ufw allow 443/tcp comment 'NAS HTTPS Web Portal'
ufw allow 5050/tcp comment 'NAS Direct Gunicorn Port'
echo "y" | ufw enable
ufw status verbose

echo "[*] Step 5: Configuring Apache & ModSecurity WAF..."
a2enmod proxy proxy_http headers rewrite security2
cp deploy/modsecurity_nas.conf /etc/modsecurity/modsecurity_nas.conf
cp deploy/nas_apache.conf /etc/apache2/sites-available/nas.conf
a2dissite 000-default.conf || true
a2ensite nas.conf
systemctl restart apache2

echo "[*] Step 6: Setting up Python Virtualenv & Dependencies..."
if [ ! -d "/srv/nas-web-server/venv" ]; then
    python3 -m venv /srv/nas-web-server/venv
fi
/srv/nas-web-server/venv/bin/pip install --upgrade pip
/srv/nas-web-server/venv/bin/pip install -r requirements.txt

echo "[*] Step 7: Configuring and Starting Systemd Service..."
cp deploy/nas.service /etc/systemd/system/nas.service
systemctl daemon-reload
systemctl enable --now nas.service

echo "[+] Linux NAS Production Server successfully deployed and secured!"
echo "[+] NAS Portal URL: http://$(hostname -I | awk '{print $1}')/ or http://localhost/"
