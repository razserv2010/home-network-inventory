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
if [ -n "$existing_port" ]; then
  chosen_port=$existing_port
else
  chosen_port=''
  for candidate in $(seq 8765 8799); do
    if ! ss -ltn "( sport = :$candidate )" | tail -n +2 | grep -q .; then
      chosen_port=$candidate
      break
    fi
  done
  if [ -z "$chosen_port" ]; then
    echo 'No free port found between 8765 and 8799.' >&2
    exit 1
  fi
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
echo "Running as $install_user on port $chosen_port. Local address: http://localhost:$chosen_port"
