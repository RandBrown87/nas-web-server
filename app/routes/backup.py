import os
import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from config import Config
from app.database import get_db
from app.decorators import login_required, admin_required
from app.backup_utils import perform_full_backup, perform_full_restore, calculate_next_run

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/api/backup', methods=['GET', 'POST'])
@login_required
@admin_required
def handle_backup():
    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM backups ORDER BY created_at DESC")
        backups = cursor.fetchall()
        cursor.close()
        conn.close()

        # Add file size if archive exists on disk
        for b in backups:
            fpath = os.path.join(Config.BACKUP_DIR, b['backup_name'])
            b['size_bytes'] = os.path.getsize(fpath) if os.path.exists(fpath) else 0

        return jsonify({'backups': backups})

    data = request.json or {}
    include_db = data.get('include_db', True)

    result = perform_full_backup(include_db=include_db, backup_type='manual')
    return jsonify(result)

@backup_bp.route('/api/restore', methods=['POST'])
@login_required
@admin_required
def handle_restore():
    data = request.json or {}
    filename = secure_filename(data.get('backup_name', ''))
    if not filename:
        return jsonify({'error': 'Backup name required'}), 400

    result = perform_full_restore(filename)
    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)

@backup_bp.route('/api/backup/schedule', methods=['GET', 'POST'])
@login_required
@admin_required
def handle_schedule():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("SELECT * FROM backup_schedules LIMIT 1")
        schedule = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({'schedule': schedule})

    data = request.json or {}
    enabled = bool(data.get('enabled', False))
    frequency = data.get('frequency', 'daily')
    backup_time = data.get('backup_time', '02:00')
    include_db = bool(data.get('include_db', True))

    if frequency not in ['hourly', 'daily', 'weekly']:
        frequency = 'daily'

    next_run = calculate_next_run(frequency, backup_time) if enabled else None

    cursor.execute("""
        UPDATE backup_schedules
        SET enabled = %s, frequency = %s, backup_time = %s, include_db = %s, next_run = %s
        WHERE id = 1
    """, (enabled, frequency, backup_time, include_db, next_run))
    conn.commit()

    cursor.execute("SELECT * FROM backup_schedules LIMIT 1")
    updated = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'schedule': updated})

