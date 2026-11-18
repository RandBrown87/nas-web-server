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

        total_bytes = 0
        latest_dt = None

        # Add file size and explicit human-readable date & time fields
        for b in backups:
            fpath = os.path.join(Config.BACKUP_DIR, b['backup_name'])
            sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            b['size_bytes'] = sz
            total_bytes += sz

            dt = b.get('created_at')
            if isinstance(dt, datetime.datetime):
                b['created_at_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                b['date_formatted'] = dt.strftime('%Y-%m-%d')
                b['time_formatted'] = dt.strftime('%H:%M:%S')
                if not latest_dt:
                    latest_dt = dt
            elif dt:
                dt_str = str(dt)
                b['created_at_formatted'] = dt_str
                b['date_formatted'] = dt_str.split(' ')[0] if ' ' in dt_str else dt_str
                b['time_formatted'] = dt_str.split(' ')[1] if ' ' in dt_str else ''
                if not latest_dt:
                    latest_dt = dt
            else:
                b['created_at_formatted'] = '-'
                b['date_formatted'] = '-'
                b['time_formatted'] = '-'

        latest_time_str = latest_dt.strftime('%Y-%m-%d %H:%M:%S') if isinstance(latest_dt, datetime.datetime) else (str(latest_dt) if latest_dt else 'Never')

        return jsonify({
            'backups': backups,
            'total_archives': len(backups),
            'total_size_bytes': total_bytes,
            'latest_backup_time': latest_time_str
        })

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
        if schedule:
            if isinstance(schedule.get('last_run'), datetime.datetime):
                schedule['last_run_formatted'] = schedule['last_run'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                schedule['last_run_formatted'] = str(schedule.get('last_run')) if schedule.get('last_run') else 'Never'
            if isinstance(schedule.get('next_run'), datetime.datetime):
                schedule['next_run_formatted'] = schedule['next_run'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                schedule['next_run_formatted'] = str(schedule.get('next_run')) if schedule.get('next_run') else 'Not scheduled'
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

