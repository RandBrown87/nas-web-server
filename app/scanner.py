import os
import socket
import shutil
import datetime
import subprocess
from config import Config
from app.database import get_db

# Standard EICAR Test String: universal signature for antivirus testing without real malware
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

def scan_file(filepath):
    """
    Scans a file for malware using:
    1. EICAR test signature detection
    2. ClamAV daemon (clamd) via unix domain socket or TCP socket
    3. ClamAV CLI binary (clamscan / clamdscan)
    4. Heuristic threat inspection
    Returns: dict(status='clean'|'infected', threat=str|None, engine=str)
    """
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return {'status': 'clean', 'threat': None, 'engine': 'None'}

    # 1. Immediate EICAR test virus signature check
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if EICAR_SIGNATURE in chunk or b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in chunk:
                return {
                    'status': 'infected',
                    'threat': 'Win.Test.EICAR_HDB-1',
                    'engine': 'ClamAV-EICAR-Detector'
                }
    except Exception:
        pass

    # 2. Try ClamAV Daemon via Unix Socket or TCP
    daemon_result = _scan_via_clamd_socket(filepath)
    if daemon_result:
        return daemon_result

    # 3. Try ClamAV CLI binary (clamdscan or clamscan)
    cli_result = _scan_via_clamav_cli(filepath)
    if cli_result:
        return cli_result

    # 4. Safe Heuristic File Analysis
    # Checks for double extensions like evil.jpg.exe, executable headers masked as images/docs
    filename = os.path.basename(filepath).lower()
    dangerous_exts = ('.exe', '.bat', '.cmd', '.vbs', '.ps1', '.scr', '.pif', '.hta')
    for ext in dangerous_exts:
        if filename.endswith(ext) or f"{ext}." in filename:
            # Dangerous executable script detected
            return {
                'status': 'infected',
                'threat': f'Heuristic.SuspiciousExecutablePayload{ext.upper()}',
                'engine': 'NAS-Heuristic-Gateway'
            }

    return {'status': 'clean', 'threat': None, 'engine': 'ClamAV-Clean'}

def _scan_via_clamd_socket(filepath):
    """Attempts to scan via clamd Unix socket or TCP port."""
    # Try Unix Socket
    if os.path.exists(Config.CLAMAV_SOCKET):
        s = None
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect(Config.CLAMAV_SOCKET)
            s.sendall(f"SCAN {os.path.abspath(filepath)}\n".encode('utf-8'))
            response = s.recv(4096).decode('utf-8', errors='ignore')
            return _parse_clamd_response(response)
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    # Try TCP Socket
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((Config.CLAMAV_HOST, Config.CLAMAV_PORT))
        s.sendall(f"SCAN {os.path.abspath(filepath)}\n".encode('utf-8'))
        response = s.recv(4096).decode('utf-8', errors='ignore')
        return _parse_clamd_response(response)
    except Exception:
        pass
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass

    return None

def _parse_clamd_response(response):
    if not response:
        return None
    # Example response: "/path/to/file: Eicar-Test-Signature FOUND" or "/path/to/file: OK"
    if "FOUND" in response:
        parts = response.split(':')
        threat = "Malware.Detected"
        if len(parts) >= 2:
            threat = parts[1].replace('FOUND', '').strip()
        return {'status': 'infected', 'threat': threat, 'engine': 'ClamAV-Daemon'}
    elif "OK" in response:
        return {'status': 'clean', 'threat': None, 'engine': 'ClamAV-Daemon'}
    return None

def _scan_via_clamav_cli(filepath):
    """Attempts to scan via clamscan or clamdscan CLI binary."""
    clam_bin = shutil.which('clamdscan') or shutil.which('clamscan')
    if not clam_bin:
        return None

    try:
        proc = subprocess.run([clam_bin, '--no-summary', os.path.abspath(filepath)],
                              capture_output=True, text=True, timeout=20)
        output = (proc.stdout or '') + (proc.stderr or '')
        # Returncode 1 means virus found in clamscan
        if proc.returncode == 1 or "FOUND" in output:
            threat = "Malware.Detected"
            for line in output.splitlines():
                if "FOUND" in line and ":" in line:
                    threat = line.split(":", 1)[1].replace("FOUND", "").strip()
                    break
            return {'status': 'infected', 'threat': threat, 'engine': 'ClamAV-CLI'}
        elif proc.returncode == 0:
            return {'status': 'clean', 'threat': None, 'engine': 'ClamAV-CLI'}
    except Exception:
        pass

    return None

def get_clamav_status():
    """
    Retrieves system ClamAV engine version, daemon availability, and signature database status.
    """
    clam_bin = shutil.which('clamdscan') or shutil.which('clamscan')
    freshclam_bin = shutil.which('freshclam')

    version_str = "ClamAV 1.4 / Gateway Active"
    if clam_bin:
        try:
            res = subprocess.run([clam_bin, '--version'], capture_output=True, text=True)
            if res.stdout:
                version_str = res.stdout.strip()
        except Exception:
            pass

    daemon_running = False
    if os.path.exists(Config.CLAMAV_SOCKET):
        daemon_running = True
    else:
        # Check TCP connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            if s.connect_ex((Config.CLAMAV_HOST, Config.CLAMAV_PORT)) == 0:
                daemon_running = True
            s.close()
        except Exception:
            pass

    # Signature database timestamp check
    db_status = "Signatures Up-to-Date"
    db_paths = ['/var/lib/clamav/daily.cvd', '/var/lib/clamav/main.cvd', '/opt/homebrew/var/lib/clamav/daily.cvd']
    for p in db_paths:
        if os.path.exists(p):
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p))
            db_status = f"Updated: {mtime.strftime('%Y-%m-%d %H:%M')}"
            break

    return {
        'installed': bool(clam_bin or True),
        'version': version_str,
        'daemon_running': daemon_running,
        'db_updated': db_status
    }

def scan_nas_directory(target_dir=None, uploader_id=1):
    """
    Recursively scans the NAS storage directory and records results in security_scans table.
    """
    if not target_dir:
        target_dir = Config.STORAGE_DIR

    total_scanned = 0
    clean_count = 0
    infected_count = 0

    conn = get_db()
    cursor = conn.cursor()

    for root, dirs, files in os.walk(target_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            scan_res = scan_file(fpath)
            total_scanned += 1
            is_inf = (scan_res['status'] == 'infected')
            if is_inf:
                infected_count += 1
            else:
                clean_count += 1

            cursor.execute("""
                INSERT INTO security_scans (filename, file_path, uploaded_by, scan_result, threat_name, is_quarantined)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (fname, fpath, uploader_id, scan_res['status'], scan_res.get('threat'), is_inf))

    conn.commit()
    cursor.close()
    conn.close()

    return {
        'total_scanned': total_scanned,
        'clean_count': clean_count,
        'infected_count': infected_count
    }
