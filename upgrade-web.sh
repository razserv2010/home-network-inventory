#!/usr/bin/env bash
set -euo pipefail

app_user=$1
project_dir=$2
status_file="$project_dir/data/upgrade-status.json"

write_status() {
  python3 - "$status_file" "$1" "$2" <<'PY'
import json, os, sys, tempfile, time
path, state, message = sys.argv[1:]
fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.upgrade-')
try:
    with os.fdopen(fd, 'w') as output:
        json.dump({'state': state, 'message': message, 'time': time.time()}, output)
    os.chmod(temp, 0o644)
    os.replace(temp, path)
finally:
    if os.path.exists(temp):
        os.unlink(temp)
PY
}

on_error() {
  write_status error 'העדכון נכשל. בדוק את יומן שירות העדכון בשרת.'
}
trap on_error ERR
write_status running 'מוריד ומתקין את העדכון...'
runuser -u "$app_user" -- bash "$project_dir/UPGRADE" --no-restart
write_status running 'מפעיל מחדש את השירות...'
systemctl restart home-inventory.service
systemctl is-active --quiet home-inventory.service
write_status success 'העדכון הושלם בהצלחה.'
trap - ERR
