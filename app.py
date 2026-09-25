import ipaddress
import json
import os
import re
import socket
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, Response, abort, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'devices.sqlite3'
DB.parent.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ping_cache = {}
ping_lock = Lock()


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=5000')
    return db


with connect() as db:
    db.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, mac TEXT NOT NULL DEFAULT '',
        ip TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '', component TEXT NOT NULL DEFAULT '',
        connectivity TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )''')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(devices)')}
    for column in ('component', 'connectivity'):
        if column not in columns:
            db.execute(f"ALTER TABLE devices ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS devices_mac_unique ON devices(mac) WHERE mac != ''")
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')


def clean(value):
    return str(value or '').strip()


def validate(data):
    name = clean(data.get('name'))[:120]
    mac = clean(data.get('mac')).replace('-', ':').upper()
    ip = clean(data.get('ip'))
    kind = clean(data.get('type'))[:80]
    notes = clean(data.get('notes'))[:1000]
    if not name:
        raise ValueError('חובה למלא שם מכשיר')
    if mac and not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', mac):
        raise ValueError('כתובת MAC צריכה להיות בפורמט AA:BB:CC:DD:EE:FF')
    if ip:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ValueError('כתובת IP אינה תקינה')
    component = clean(data.get('component'))[:80]
    connectivity = clean(data.get('connectivity'))[:80]
    return (name, mac, ip, kind, notes, component, connectivity)


def all_devices(db):
    devices = [dict(row) for row in db.execute('SELECT * FROM devices')]

    def by_ip(device):
        address = device['ip']
        if address:
            try:
                parsed = ipaddress.ip_address(address)
                return (0, parsed.version, int(parsed), device['name'].casefold(), device['id'])
            except ValueError:
                pass
        return (1, 0, 0, device['name'].casefold(), device['id'])

    return sorted(devices, key=by_ip)


def validate_network_prefix(raw):
    parts = str(raw or '').strip().rstrip('.').split('.')
    if len(parts) != 3 or any(not part.isdecimal() or not 0 <= int(part) <= 255 for part in parts):
        raise ValueError('יש להזין שלושה חלקים של כתובת LAN, למשל 192.168.0')
    return '.'.join(str(int(part)) for part in parts)


def detect_lan_prefix():
    # A UDP connect selects the preferred local interface without sending data.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('1.1.1.1', 80))
            address = ipaddress.IPv4Address(probe.getsockname()[0])
            if address.is_private and not address.is_link_local and not address.is_loopback:
                return '.'.join(str(address).split('.')[:3])
    except OSError:
        pass
    try:
        output = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2, check=False).stdout
        for raw in output.split():
            try:
                address = ipaddress.IPv4Address(raw)
                if address.is_private and not address.is_link_local and not address.is_loopback:
                    return '.'.join(str(address).split('.')[:3])
            except ipaddress.AddressValueError:
                continue
    except (OSError, subprocess.TimeoutExpired):
        pass
    return '192.168.0'


def network_prefix(db):
    row = db.execute("SELECT value FROM settings WHERE key='network_prefix'").fetchone()
    if row:
        return row['value']
    prefix = detect_lan_prefix()
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('network_prefix',?)", (prefix,))
    return db.execute("SELECT value FROM settings WHERE key='network_prefix'").fetchone()['value']


@app.get('/api/ip-options')
def ip_options():
    with connect() as db:
        prefix = network_prefix(db)
        used = {row['ip'] for row in db.execute('SELECT ip FROM devices WHERE ip != ?', ('',))}
    return jsonify(prefix=prefix, suggestions=[f'{prefix}.{last}' for last in range(1, 255)
                                      if f'{prefix}.{last}' not in used])


@app.put('/api/ip-options')
def update_ip_options():
    try:
        prefix = validate_network_prefix((request.get_json(silent=True) or {}).get('prefix'))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with connect() as db:
        db.execute("INSERT INTO settings(key,value) VALUES('network_prefix',?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (prefix,))
    return jsonify(prefix=prefix)


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/devices')
def list_devices():
    with connect() as db:
        return jsonify(all_devices(db))


def ping_ip(ip):
    address = ipaddress.ip_address(ip)
    if not address.is_private and not address.is_link_local:
        return 'unavailable'
    try:
        result = subprocess.run(
            ['ping', '-6' if address.version == 6 else '-4', '-n', '-c', '1', '-W', '1', ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2, check=False,
        )
        return 'online' if result.returncode == 0 else 'offline'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 'unavailable'


@app.get('/api/status')
def device_status():
    with connect() as db:
        devices = all_devices(db)
    ips = {d['ip'] for d in devices if d['ip']}
    now = time.monotonic()
    with ping_lock:
        pending = [ip for ip in ips if ip not in ping_cache or now - ping_cache[ip][0] > 25]
    if pending:
        with ThreadPoolExecutor(max_workers=24) as pool:
            results = dict(zip(pending, pool.map(ping_ip, pending)))
        with ping_lock:
            ping_cache.update({ip: (time.monotonic(), status) for ip, status in results.items()})
    with ping_lock:
        return jsonify({str(d['id']): (ping_cache[d['ip']][1] if d['ip'] else 'no_ip') for d in devices})


@app.post('/api/devices')
def create_device():
    try:
        values = validate(request.get_json(silent=True) or {})
        with connect() as db:
            cursor = db.execute('INSERT INTO devices(name,mac,ip,type,notes,component,connectivity) VALUES(?,?,?,?,?,?,?)', values)
            return jsonify(dict(db.execute('SELECT * FROM devices WHERE id=?', (cursor.lastrowid,)).fetchone())), 201
    except (ValueError, sqlite3.IntegrityError) as error:
        return jsonify(error='כתובת MAC כבר קיימת' if isinstance(error, sqlite3.IntegrityError) else str(error)), 400


@app.put('/api/devices/<int:device_id>')
def update_device(device_id):
    try:
        values = validate(request.get_json(silent=True) or {})
        with connect() as db:
            cursor = db.execute("UPDATE devices SET name=?,mac=?,ip=?,type=?,notes=?,component=?,connectivity=?,updated_at=datetime('now') WHERE id=?", (*values, device_id))
            if not cursor.rowcount:
                abort(404)
            return jsonify(dict(db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone()))
    except (ValueError, sqlite3.IntegrityError) as error:
        return jsonify(error='כתובת MAC כבר קיימת' if isinstance(error, sqlite3.IntegrityError) else str(error)), 400


@app.delete('/api/devices/<int:device_id>')
def delete_device(device_id):
    with connect() as db:
        cursor = db.execute('DELETE FROM devices WHERE id=?', (device_id,))
        if not cursor.rowcount:
            abort(404)
    return '', 204


@app.post('/api/devices/delete')
def delete_many():
    data = request.get_json(silent=True) or {}
    if data.get('all') is True:
        with connect() as db:
            count = db.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
            db.execute('DELETE FROM devices')
        return jsonify(deleted=count)
    ids = data.get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 5000 or any(type(x) is not int or x < 1 for x in ids):
        return jsonify(error='לא נבחרו רשומות למחיקה'), 400
    with connect() as db:
        count = 0
        for device_id in set(ids):
            count += db.execute('DELETE FROM devices WHERE id=?', (device_id,)).rowcount
    return jsonify(deleted=count)


FIELDS = ('name', 'mac', 'ip', 'type', 'notes', 'component', 'connectivity')


@app.get('/backup.json')
def download_backup():
    with connect() as db:
        devices = [{key: row[key] for key in FIELDS} for row in all_devices(db)]
        prefix = network_prefix(db)
    payload = json.dumps({'format': 'home-network-inventory', 'version': 1, 'devices': devices,
                          'network_prefix': prefix}, ensure_ascii=False, indent=2)
    filename = 'network-inventory-' + datetime.now(timezone.utc).strftime('%Y-%m-%d') + '.json'
    return Response(payload, mimetype='application/json', headers={'Content-Disposition': f'attachment; filename={filename}'})


@app.post('/restore')
def restore_backup():
    uploaded = request.files.get('file')
    if not uploaded or not uploaded.filename.lower().endswith('.json'):
        return jsonify(error='בחר קובץ גיבוי JSON של היישום'), 400
    try:
        payload = json.load(uploaded.stream)
        if not isinstance(payload, dict) or payload.get('format') != 'home-network-inventory' or payload.get('version') != 1:
            raise ValueError('קובץ הגיבוי אינו בפורמט המתאים')
        devices = payload.get('devices')
        if not isinstance(devices, list) or len(devices) > 5000:
            raise ValueError('רשימת המכשירים בגיבוי אינה תקינה')
        prefix = validate_network_prefix(payload['network_prefix']) if 'network_prefix' in payload else None
        values = []
        macs = set()
        for i, device in enumerate(devices, 1):
            if not isinstance(device, dict):
                raise ValueError(f'רשומה {i} אינה תקינה')
            entry = validate(device)
            if entry[1] and entry[1] in macs:
                raise ValueError(f'כתובת MAC כפולה בגיבוי בשורה {i}')
            macs.add(entry[1])
            values.append(entry)
        with connect() as db:
            db.execute('DELETE FROM devices')
            db.executemany('INSERT INTO devices(name,mac,ip,type,notes,component,connectivity) VALUES(?,?,?,?,?,?,?)', values)
            if prefix is not None:
                db.execute("INSERT INTO settings(key,value) VALUES('network_prefix',?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (prefix,))
        return jsonify(restored=len(values))
    except (ValueError, UnicodeError, json.JSONDecodeError, sqlite3.Error) as error:
        return jsonify(error=str(error)), 400


if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8765')), debug=False)
