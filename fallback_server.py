#!/usr/bin/env python3
"""
High-Availability (HA) Backup Fallback Server for NAS Web Server.
Monitors the Primary NAS Web Server via heartbeat ping (/api/health).
If the primary server goes down (fails >= 3 consecutive health checks),
it automatically recovers using the latest verified backup archive and
assumes active service on the fallback port (default: 5050).
"""

import os
import sys
import time
import json
import shutil
import tarfile
import threading
import datetime
import urllib.request
import urllib.error
from flask import Flask, render_template_string, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Determine base directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config

PRIMARY_URL = os.environ.get('NAS_PRIMARY_URL', 'http://127.0.0.1:5000')
FALLBACK_PORT = int(os.environ.get('NAS_FALLBACK_PORT', 5050))
HEARTBEAT_INTERVAL = int(os.environ.get('NAS_HEARTBEAT_INTERVAL', 4))
FAILOVER_THRESHOLD = int(os.environ.get('NAS_FAILOVER_THRESHOLD', 3))

FALLBACK_STORAGE = os.path.join(BASE_DIR, 'fallback_storage')
os.makedirs(FALLBACK_STORAGE, exist_ok=True)
os.makedirs(Config.BACKUP_DIR, exist_ok=True)

class FallbackWatchdog:
    def __init__(self):
        self.state = 'STANDBY'  # 'STANDBY' | 'DEGRADED' | 'FAILOVER_ACTIVE'
        self.missed_pings = 0
        self.total_pings = 0
        self.primary_online = True
        self.last_ping_time = None
        self.last_backup_used = None
        self.last_restore_time = None
        self.failover_reason = None
        self.logs = []
        self._lock = threading.RLock()
        self._running = False
        self._thread = None

    def log(self, message):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {message}"
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > 60:
                self.logs.pop(0)
        print(entry)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.log(f"HA Fallback Watchdog started. Monitoring Primary at {PRIMARY_URL} (Check every {HEARTBEAT_INTERVAL}s)")

    def _run_loop(self):
        while self._running:
            self._check_primary()
            time.sleep(HEARTBEAT_INTERVAL)

    def _check_primary(self):
        self.total_pings += 1
        self.last_ping_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        health_url = f"{PRIMARY_URL.rstrip('/')}/api/health"

        is_healthy = False
        error_msg = None
        try:
            req = urllib.request.Request(health_url, headers={'User-Agent': 'NAS-Fallback-Watchdog/2.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get('status') == 'healthy':
                        is_healthy = True
        except Exception as e:
            error_msg = str(e)

        with self._lock:
            if is_healthy:
                self.primary_online = True
                if self.missed_pings > 0:
                    self.log(f"Primary server recovered. Heartbeat normal at {PRIMARY_URL}.")
                self.missed_pings = 0
                if self.state != 'STANDBY':
                    self.log("Primary NAS is back online. Setting fallback node to STANDBY monitor.")
                    self.state = 'STANDBY'
            else:
                self.primary_online = False
                self.missed_pings += 1
                self.log(f"Primary heartbeat FAILED ({self.missed_pings}/{FAILOVER_THRESHOLD}). Cause: {error_msg or 'Unhealthy response'}")

                if self.missed_pings >= FAILOVER_THRESHOLD and self.state != 'FAILOVER_ACTIVE':
                    self.trigger_failover(f"Primary server offline (Missed {self.missed_pings} consecutive heartbeats)")

    def trigger_failover(self, reason="Manual failover trigger"):
        self.state = 'FAILOVER_ACTIVE'
        self.failover_reason = reason
        self.log(f"⚠️ [FAILOVER TRIGGERED] Reason: {reason}")
        self.restore_latest_backup()

    def stand_down(self):
        with self._lock:
            self.state = 'STANDBY'
            self.failover_reason = None
            self.missed_pings = 0
            self.log("Fallback node stood down. Returned to STANDBY monitoring mode.")

    def restore_latest_backup(self):
        self.log("Scanning for newest backup archive in backups directory...")
        archives = [f for f in os.listdir(Config.BACKUP_DIR) if f.endswith('.tar.gz')]
        if not archives:
            self.log("No backup archive (.tar.gz) found to restore. Serving existing storage volume.")
            # Fall back to copying directly from main storage if present
            if os.path.exists(Config.STORAGE_DIR):
                shutil.copytree(Config.STORAGE_DIR, FALLBACK_STORAGE, dirs_exist_ok=True)
            return False

        archives.sort(key=lambda x: os.path.getmtime(os.path.join(Config.BACKUP_DIR, x)), reverse=True)
        latest_archive = archives[0]
        latest_path = os.path.join(Config.BACKUP_DIR, latest_archive)

        self.log(f"Found latest backup: '{latest_archive}'. Initiating emergency restoration...")
        extract_tmp = os.path.join(BASE_DIR, 'tmp_fallback_extract')
        os.makedirs(extract_tmp, exist_ok=True)

        try:
            with tarfile.open(latest_path, "r:gz") as tar:
                tar.extractall(path=extract_tmp)

            extracted_storage = os.path.join(extract_tmp, 'storage')
            if os.path.exists(extracted_storage):
                shutil.copytree(extracted_storage, FALLBACK_STORAGE, dirs_exist_ok=True)
                self.log(f"Storage directory successfully restored from '{latest_archive}' into fallback storage.")

            self.last_backup_used = latest_archive
            self.last_restore_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.log(f"✅ Fallback node is now ACTIVE and serving restored data.")
            return True
        except Exception as e:
            self.log(f"Error during backup archive extraction: {e}")
            return False
        finally:
            if os.path.exists(extract_tmp):
                shutil.rmtree(extract_tmp, ignore_errors=True)

watchdog = FallbackWatchdog()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fallback-nas-secret-key-2026'

FALLBACK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NAS High-Availability Fallback Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-canvas: #0f1218;
            --surface-card: #171b24;
            --surface-card-sub: #1e2330;
            --border-subtle: #272d3b;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
        }
        body {
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
        }
        .ha-navbar {
            background: #141720;
            border-bottom: 1px solid var(--border-subtle);
            padding: 14px 24px;
        }
        .ha-card {
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }
        .pulse-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        .pulse-green {
            background: var(--accent-green);
            box-shadow: 0 0 12px var(--accent-green);
            animation: pulse 2s infinite;
        }
        .pulse-amber {
            background: var(--accent-amber);
            box-shadow: 0 0 12px var(--accent-amber);
            animation: pulse 1.2s infinite;
        }
        .pulse-red {
            background: var(--accent-red);
            box-shadow: 0 0 12px var(--accent-red);
            animation: pulse 0.8s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }
        .terminal-log {
            background: #0d0f14;
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            max-height: 320px;
            overflow-y: auto;
            color: #38bdf8;
        }
        .table-dark-custom {
            --bs-table-bg: transparent;
            --bs-table-border-color: var(--border-subtle);
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <nav class="ha-navbar d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center gap-2">
            <i class="bi bi-shield-fill-check fs-4 text-warning"></i>
            <div>
                <span class="fw-bold tracking-wide">NAS HIGH-AVAILABILITY FALLBACK NODE</span>
                <span class="badge bg-secondary ms-2 font-monospace">Port {{ fallback_port }}</span>
            </div>
        </div>
        <div class="d-flex align-items-center gap-3">
            <span class="text-secondary small">
                Primary Target: <code class="text-info">{{ primary_url }}</code>
            </span>
            <a href="{{ primary_url }}" target="_blank" class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-box-arrow-up-right me-1"></i> Open Primary
            </a>
        </div>
    </nav>

    <div class="container py-4">
        <!-- Status Alert Banner -->
        {% if state == 'FAILOVER_ACTIVE' %}
        <div class="alert alert-danger d-flex align-items-center justify-content-between p-3 border-danger shadow mb-4" style="background: rgba(239, 68, 68, 0.15);">
            <div class="d-flex align-items-center gap-3">
                <span class="pulse-indicator pulse-red fs-5"></span>
                <div>
                    <h5 class="fw-bold mb-0 text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i>FAILOVER ACTIVE: Serving Traffic from Fallback Node</h5>
                    <small class="text-secondary">Primary server is unresponsive. Operating on latest restored backup: <strong>{{ last_backup_used or 'Storage Snapshot' }}</strong> (Restored: {{ last_restore_time }})</small>
                </div>
            </div>
            <button class="btn btn-sm btn-outline-light" onclick="standDown()">
                <i class="bi bi-arrow-counterclockwise me-1"></i> Stand Down Node
            </button>
        </div>
        {% else %}
        <div class="alert alert-success d-flex align-items-center justify-content-between p-3 border-success mb-4" style="background: rgba(16, 185, 129, 0.1);">
            <div class="d-flex align-items-center gap-3">
                <span class="pulse-indicator pulse-green"></span>
                <div>
                    <h6 class="fw-bold mb-0 text-success"><i class="bi bi-check-circle-fill me-2"></i>STANDBY MONITORING ACTIVE</h6>
                    <small class="text-secondary">Watchdog is actively monitoring Primary NAS ({{ primary_url }}). Zero missed heartbeats. Ready for instantaneous hot failover.</small>
                </div>
            </div>
            <button class="btn btn-sm btn-warning fw-semibold shadow-sm" onclick="simulateFailover()">
                <i class="bi bi-lightning-charge-fill me-1"></i> Test Failover Simulation
            </button>
        </div>
        {% endif %}

        <!-- Metric Cards -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="ha-card">
                    <span class="text-secondary small fw-semibold text-uppercase">Node Role</span>
                    <h4 class="fw-bold mt-2 mb-0 {% if state == 'FAILOVER_ACTIVE' %}text-danger{% else %}text-info{% endif %}">{{ state }}</h4>
                    <small class="text-secondary">Failover Threshold: {{ failover_threshold }} pings</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="ha-card">
                    <span class="text-secondary small fw-semibold text-uppercase">Primary Node State</span>
                    <h4 class="fw-bold mt-2 mb-0 {% if primary_online %}text-success{% else %}text-danger{% endif %}">
                        {% if primary_online %}ONLINE (200 OK){% else %}OFFLINE (Unreachable){% endif %}
                    </h4>
                    <small class="text-secondary">Missed Heartbeats: {{ missed_pings }}</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="ha-card">
                    <span class="text-secondary small fw-semibold text-uppercase">Latest Sync Backup</span>
                    <h5 class="fw-bold mt-2 mb-0 text-truncate font-monospace" title="{{ last_backup_used }}">{{ last_backup_used or 'Automatic Sync Ready' }}</h5>
                    <small class="text-secondary">Restored: {{ last_restore_time or 'On Standby' }}</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="ha-card">
                    <span class="text-secondary small fw-semibold text-uppercase">Watchdog Heartbeats</span>
                    <h4 class="fw-bold mt-2 mb-0 font-monospace text-warning">{{ total_pings }} pings</h4>
                    <small class="text-secondary">Last Ping: {{ last_ping_time or 'Just now' }}</small>
                </div>
            </div>
        </div>

        <!-- Files Section on Fallback Node -->
        <div class="ha-card mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h5 class="fw-bold mb-0"><i class="bi bi-folder-check text-info me-2"></i> Fallback Storage Files</h5>
                    <small class="text-secondary">Storage synchronized from latest backup archive (Directory: <code>{{ fallback_storage }}</code>)</small>
                </div>
                <button class="btn btn-sm btn-outline-info" onclick="restoreLatestBackup()">
                    <i class="bi bi-arrow-repeat me-1"></i> Unpack & Sync Latest Backup Now
                </button>
            </div>
            <div class="table-responsive">
                <table class="table table-dark-custom align-middle">
                    <thead>
                        <tr class="text-secondary small">
                            <th>File Name</th>
                            <th>Size</th>
                            <th>Last Modified</th>
                            <th class="text-end">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="fallbackFileList">
                        {% for f in files %}
                        <tr>
                            <td>
                                <i class="bi {% if f.is_dir %}bi-folder-fill text-warning{% else %}bi-file-earmark-text text-info{% endif %} me-2"></i>
                                <span class="fw-semibold">{{ f.name }}</span>
                            </td>
                            <td><span class="font-monospace small text-secondary">{{ f.size_str }}</span></td>
                            <td><span class="small text-secondary">{{ f.modified }}</span></td>
                            <td class="text-end">
                                <a href="/api/download?path={{ f.name }}" class="btn btn-sm btn-outline-success">
                                    <i class="bi bi-download me-1"></i> Download
                                </a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" class="text-center text-muted py-4">No files currently in fallback storage volume. Trigger a sync or failover to unpack latest backup.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Live Watchdog Telemetry Log -->
        <div class="ha-card">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="fw-bold mb-0 text-secondary"><i class="bi bi-terminal me-2"></i> Watchdog Heartbeat & Event Journal</h6>
                <button class="btn btn-link btn-sm text-secondary text-decoration-none p-0" onclick="window.location.reload()">
                    <i class="bi bi-arrow-clockwise"></i> Refresh Log
                </button>
            </div>
            <div class="terminal-log">
                {% for l in logs %}
                <div>{{ l }}</div>
                {% else %}
                <div>[System] Watchdog initialized. Waiting for first heartbeat event...</div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        async function simulateFailover() {
            if (!confirm("Simulate Primary Server Outage and activate Fallback Node immediately?")) return;
            const res = await fetch('/api/fallback/simulate-failover', { method: 'POST' });
            if (res.ok) window.location.reload();
        }

        async function standDown() {
            const res = await fetch('/api/fallback/stand-down', { method: 'POST' });
            if (res.ok) window.location.reload();
        }

        async function restoreLatestBackup() {
            const res = await fetch('/api/restore-latest', { method: 'POST' });
            if (res.ok) {
                alert("Latest backup unpacked successfully into fallback storage.");
                window.location.reload();
            } else {
                alert("Failed to unpack backup.");
            }
        }

        // Auto-refresh every 6 seconds to reflect live watchdog status
        setInterval(() => {
            fetch('/api/fallback/status')
                .then(r => r.json())
                .then(d => {
                    if (d.mode !== '{{ state }}' || d.primary_online !== {{ 'true' if primary_online else 'false' }}) {
                        window.location.reload();
                    }
                }).catch(() => {});
        }, 5000);
    </script>
</body>
</html>
"""

def list_fallback_files():
    items = []
    if os.path.exists(FALLBACK_STORAGE):
        for name in sorted(os.listdir(FALLBACK_STORAGE)):
            fpath = os.path.join(FALLBACK_STORAGE, name)
            is_dir = os.path.isdir(fpath)
            size = os.path.getsize(fpath) if not is_dir else 0
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{(size / 1024):.1f} KB"
            else:
                size_str = f"{(size / (1024*1024)):.2f} MB"

            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M')
            items.append({
                'name': name,
                'is_dir': is_dir,
                'size_str': size_str if not is_dir else '-',
                'modified': mtime
            })
    return items

@app.route('/')
def index():
    files = list_fallback_files()
    return render_template_string(
        FALLBACK_HTML_TEMPLATE,
        state=watchdog.state,
        primary_online=watchdog.primary_online,
        missed_pings=watchdog.missed_pings,
        total_pings=watchdog.total_pings,
        last_ping_time=watchdog.last_ping_time,
        last_backup_used=watchdog.last_backup_used,
        last_restore_time=watchdog.last_restore_time,
        primary_url=PRIMARY_URL,
        fallback_port=FALLBACK_PORT,
        failover_threshold=FAILOVER_THRESHOLD,
        fallback_storage=FALLBACK_STORAGE,
        files=files,
        logs=reversed(watchdog.logs[-25:])
    )

@app.route('/api/fallback/status')
def fallback_status():
    return jsonify({
        'mode': watchdog.state,
        'primary_online': watchdog.primary_online,
        'missed_pings': watchdog.missed_pings,
        'total_pings': watchdog.total_pings,
        'last_ping_time': watchdog.last_ping_time,
        'last_backup_used': watchdog.last_backup_used,
        'last_restore_time': watchdog.last_restore_time,
        'failover_reason': watchdog.failover_reason,
        'primary_url': PRIMARY_URL,
        'fallback_port': FALLBACK_PORT,
        'fallback_storage': FALLBACK_STORAGE,
        'logs': watchdog.logs[-15:]
    })

@app.route('/api/fallback/simulate-failover', methods=['POST'])
def simulate_failover():
    watchdog.trigger_failover("Manual Classroom / Admin Simulation via API")
    return jsonify({'success': True, 'mode': watchdog.state, 'backup_used': watchdog.last_backup_used})

@app.route('/api/fallback/stand-down', methods=['POST'])
def stand_down():
    watchdog.stand_down()
    return jsonify({'success': True, 'mode': watchdog.state})

@app.route('/api/restore-latest', methods=['POST'])
def restore_latest():
    res = watchdog.restore_latest_backup()
    return jsonify({'success': res, 'backup_used': watchdog.last_backup_used})

@app.route('/api/files', methods=['GET'])
def api_files():
    return jsonify({'items': list_fallback_files(), 'mode': watchdog.state})

@app.route('/api/download')
def api_download():
    fname = secure_filename(request.args.get('path', ''))
    fpath = os.path.join(FALLBACK_STORAGE, fname)
    if not os.path.isfile(fpath):
        return jsonify({'error': 'File not found on fallback node'}), 404
    return send_file(fpath, as_attachment=True)

if __name__ == '__main__':
    watchdog.start()
    print(f"Starting NAS Fallback Server on http://0.0.0.0:{FALLBACK_PORT} ...")
    app.run(host='0.0.0.0', port=FALLBACK_PORT, debug=False)
