#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo 'Run this script as your regular user, without sudo.' >&2
  exit 1
fi

install_user=$(id -un)
install_dir=$(cd "$(dirname "$0")" && pwd -P)
unit_name=home-inventory.service

if ! command -v ping >/dev/null; then
  echo 'ping is missing. Install it first: sudo apt install iputils-ping' >&2
  exit 1
fi

python3 -m venv "$install_dir/.venv"
"$install_dir/.venv/bin/pip" install -r "$install_dir/requirements.txt"
mkdir -p "$install_dir/data"

existing_port=$(systemctl show "$unit_name" -p Environment --value 2>/dev/null | sed -n 's/.*PORT=\([0-9]*\).*/\1/p' || true)
# Stop our own service so its port can be tested like any other port.
if systemctl is-active --quiet "$unit_name"; then
  sudo systemctl stop "$unit_name"
fi

# Binding to all interfaces checks whether the app can actually listen on the LAN.
# Prefer the previous port on reinstall; otherwise use the first available one.
chosen_port=$(python3 - "$existing_port" <<'PY'
import socket
import sys

previous = sys.argv[1]
candidates = []
if previous.isdecimal() and 1 <= int(previous) <= 65535:
    candidates.append(int(previous))
candidates.extend(range(8765, 8800))

for port in dict.fromkeys(candidates):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("0.0.0.0", port))
        print(port)
        break
    except OSError:
        continue
else:
    sys.exit("No available port between 8765 and 8799.")
PY
)
if [ -n "$existing_port" ] && [ "$chosen_port" != "$existing_port" ]; then
  echo "Port $existing_port is occupied; using $chosen_port instead."
fi

sudo tee "/etc/systemd/system/$unit_name" >/dev/null <<SERVICE
[Unit]
Description=Home network inventory
After=network-online.target
Wants=network-online.target

[Service]
User=$install_user
WorkingDirectory="$install_dir"
Environment=HOST=0.0.0.0
Environment=PORT=$chosen_port
ExecStart="$install_dir/.venv/bin/waitress-serve" --host=0.0.0.0 --port=$chosen_port app:app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable "$unit_name"
sudo systemctl restart "$unit_name"
sudo systemctl is-active --quiet "$unit_name" || {
  echo "Service failed to start on port $chosen_port; inspect: sudo journalctl -u $unit_name -n 50 --no-pager" >&2
  exit 1
}
server_ip=$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]\+\).*/\1/p' | head -n 1)
if [ -z "$server_ip" ]; then
  server_ip=$(hostname -I 2>/dev/null | awk '{ print $1 }')
fi
echo "Installation complete. Running as $install_user on port $chosen_port."
if [ -n "$server_ip" ]; then
  echo "Open from a device on your home network: http://$server_ip:$chosen_port"
else
  echo "Could not detect a LAN IP. Run 'hostname -I' to find it. Port: $chosen_port"
fi
echo "To find the configured port later, run: systemctl show $unit_name -p Environment --value | tr ' ' '\\n' | sed -n 's/^PORT=//p'"
