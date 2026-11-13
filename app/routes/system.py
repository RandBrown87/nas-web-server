import psutil
import subprocess
from flask import Blueprint, jsonify
from config import Config
from app.decorators import login_required

system_bp = Blueprint('system', __name__)

@system_bp.route('/api/system')
@login_required
def stats():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(Config.STORAGE_DIR if psutil.os.path.exists(Config.STORAGE_DIR) else '/')

    try:
        proc = subprocess.run(['journalctl', '-n', '15', '--no-pager'], capture_output=True, text=True)
        logs = proc.stdout.splitlines()[-15:] if proc.stdout else ["No recent logs"]
    except Exception:
        logs = ["Logs unavailable on host"]

    return jsonify({
        'cpu_percent': cpu,
        'ram_percent': ram.percent,
        'ram_used_gb': round(ram.used / (1024**3), 2),
        'ram_total_gb': round(ram.total / (1024**3), 2),
        'disk_percent': disk.percent,
        'disk_used_gb': round(disk.used / (1024**3), 2),
        'disk_total_gb': round(disk.total / (1024**3), 2),
        'logs': logs
    })
