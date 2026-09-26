#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo 'Run as your regular user, without sudo.' >&2
  exit 1
fi

install_user=$(id -un)
install_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
sudo install -D -o root -g root -m 0755 "$install_dir/upgrade-web.sh" /usr/local/libexec/home-inventory-upgrade.sh

sudo tee /etc/systemd/system/home-inventory-upgrade.service >/dev/null <<SERVICE
[Unit]
Description=Update Home network inventory
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash /usr/local/libexec/home-inventory-upgrade.sh $install_user $install_dir
SERVICE

# Permit the app to start this one updater service without a sudo password.
sudo tee /etc/sudoers.d/home-inventory-upgrade >/dev/null <<SUDOERS
$install_user ALL=(root) NOPASSWD: /usr/bin/systemctl start --no-block home-inventory-upgrade.service
SUDOERS
sudo chmod 0440 /etc/sudoers.d/home-inventory-upgrade
sudo visudo -cf /etc/sudoers.d/home-inventory-upgrade
sudo systemd-analyze verify /etc/systemd/system/home-inventory-upgrade.service
# Existing installations use NoNewPrivileges=true, which blocks this one sudo action.
sudo mkdir -p /etc/systemd/system/home-inventory.service.d
sudo tee /etc/systemd/system/home-inventory.service.d/web-upgrade.conf >/dev/null <<SERVICE
[Service]
NoNewPrivileges=false
SERVICE
sudo systemctl daemon-reload
if systemctl is-active --quiet home-inventory.service; then
  sudo systemctl restart home-inventory.service
fi
echo 'Web update setup complete; the existing app port was not changed.'
