import os
import tarfile
import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from config import Config
from app.database import get_db
from app.decorators import login_required, admin_required

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/api/backup', methods=['GET', 'POST'])
@login_required
@admin_required
def handle_backup():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("SELECT * FROM backups ORDER BY created_at DESC")
        backups = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'backups': backups})

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{timestamp}.tar.gz"
    filepath = os.path.join(Config.BACKUP_DIR, filename)

    with tarfile.open(filepath, "w:gz") as tar:
        tar.add(Config.STORAGE_DIR, arcname=os.path.basename(Config.STORAGE_DIR))

    cursor.execute("INSERT INTO backups (backup_name, file_path) VALUES (%s, %s)", (filename, filepath))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'backup_name': filename})

@backup_bp.route('/api/restore', methods=['POST'])
@login_required
@admin_required
def handle_restore():
    data = request.json or {}
    filename = secure_filename(data.get('backup_name', ''))
    path = os.path.join(Config.BACKUP_DIR, filename)

    if not os.path.exists(path):
        return jsonify({'error': 'Archive not found'}), 404

    target_parent = os.path.dirname(Config.STORAGE_DIR)
    with tarfile.open(path, "r:gz") as tar:
        tar.extractall(path=target_parent)

    return jsonify({'success': True})
