import os
import shutil
from flask import Blueprint, request, jsonify, session
from config import Config
from app.database import get_db
from app.decorators import login_required, admin_required
from app.scanner import get_clamav_status, scan_nas_directory

security_bp = Blueprint('security', __name__)

@security_bp.route('/api/security/stats', methods=['GET'])
@login_required
@admin_required
def security_stats():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM security_scans")
    total_scans = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as clean FROM security_scans WHERE scan_result = 'clean'")
    clean_files = cursor.fetchone()['clean']

    cursor.execute("SELECT COUNT(*) as infected FROM security_scans WHERE scan_result = 'infected'")
    infected_threats = cursor.fetchone()['infected']

    cursor.execute("SELECT COUNT(*) as quarantined FROM security_scans WHERE is_quarantined = TRUE")
    quarantined_files = cursor.fetchone()['quarantined']

    cursor.close()
    conn.close()

    clam_status = get_clamav_status()

    return jsonify({
        'total_scans': total_scans,
        'clean_files': clean_files,
        'infected_threats': infected_threats,
        'quarantined_files': quarantined_files,
        'clamav_status': clam_status
    })

@security_bp.route('/api/security/scans', methods=['GET'])
@login_required
@admin_required
def scan_history():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.id, s.filename, s.file_path, s.scan_result, s.threat_name,
               s.is_quarantined, s.scanned_at, u.username as uploader_name
        FROM security_scans s
        LEFT JOIN users u ON s.uploaded_by = u.id
        ORDER BY s.scanned_at DESC
        LIMIT 50
    """)
    scans = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'scans': scans})

@security_bp.route('/api/security/scan-storage', methods=['POST'])
@login_required
@admin_required
def manual_scan():
    result = scan_nas_directory(uploader_id=session.get('user_id', 1))
    return jsonify({'success': True, 'result': result})

@security_bp.route('/api/security/quarantine/<int:scan_id>/action', methods=['POST'])
@login_required
@admin_required
def quarantine_action(scan_id):
    data = request.json or {}
    action = data.get('action')  # 'delete' or 'release'

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM security_scans WHERE id = %s", (scan_id,))
    scan = cursor.fetchone()

    if not scan:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Scan record not found'}), 404

    target_file = scan['file_path']

    if action == 'delete':
        if os.path.exists(target_file):
            try:
                os.remove(target_file)
            except Exception as e:
                pass
        cursor.execute("UPDATE security_scans SET is_quarantined = FALSE, scan_result = 'deleted_by_admin' WHERE id = %s", (scan_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Quarantined file deleted permanently'})

    elif action == 'release':
        # Admin decides it is a false positive and releases it to storage
        if os.path.exists(target_file):
            dest = os.path.join(Config.STORAGE_DIR, scan['filename'])
            try:
                shutil.move(target_file, dest)
                cursor.execute(
                    "INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by) VALUES (%s, %s, %s, %s)",
                    (scan['filename'], os.path.abspath(dest), os.path.getsize(dest), scan['uploaded_by'])
                )
            except Exception as e:
                cursor.close()
                conn.close()
                return jsonify({'error': f'Failed to release file: {str(e)}'}), 500

        cursor.execute("UPDATE security_scans SET is_quarantined = FALSE, scan_result = 'released_by_admin' WHERE id = %s", (scan_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'File released to storage'})

    cursor.close()
    conn.close()
    return jsonify({'error': 'Invalid action'}), 400
