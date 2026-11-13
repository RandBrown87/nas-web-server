import os
import shutil
import datetime
from flask import Blueprint, render_template, request, session, jsonify, send_file
from werkzeug.utils import secure_filename
from config import Config
from app.database import get_db
from app.decorators import login_required

files_bp = Blueprint('files', __name__)

def safe_path(relative_path=""):
    base = os.path.abspath(Config.STORAGE_DIR)
    target = os.path.abspath(os.path.join(base, relative_path.lstrip('/')))
    if not target.startswith(base):
        raise ValueError("Directory Traversal Blocked")
    return target

@files_bp.route('/')
@login_required
def index():
    return render_template('index.html', username=session['username'], is_admin=session['is_admin'])

@files_bp.route('/api/files', methods=['GET'])
@login_required
def list_files():
    req_path = request.args.get('path', '')
    try:
        target = safe_path(req_path)
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    items = []
    if os.path.exists(target):
        entries = sorted(list(os.scandir(target)), key=lambda e: (not e.is_dir(), e.name.lower()))
        paths = [os.path.abspath(e.path) for e in entries]
        metadata_map = {}

        if paths:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            placeholders = ', '.join(['%s'] * len(paths))
            cursor.execute(f"""
                SELECT f.file_path, f.filename, f.uploaded_by, f.is_private, u.username as uploader_name
                FROM file_metadata f
                LEFT JOIN users u ON f.uploaded_by = u.id
                WHERE f.file_path IN ({placeholders})
            """, paths)
            for r in cursor.fetchall():
                metadata_map[os.path.abspath(r['file_path'])] = r
            cursor.close()
            conn.close()

        current_user_id = session.get('user_id')

        for entry in entries:
            abs_path = os.path.abspath(entry.path)
            meta = metadata_map.get(abs_path)
            uploaded_by = meta['uploaded_by'] if meta else None
            uploader_name = meta['uploader_name'] if (meta and meta['uploader_name']) else ('Admin' if uploaded_by == 1 else 'System')
            is_private = bool(meta['is_private']) if meta else False
            is_uploader = (uploaded_by is not None and uploaded_by == current_user_id)

            # Private files are strictly visible ONLY to the user that uploaded them
            if is_private and not is_uploader:
                continue

            items.append({
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'size': entry.stat().st_size if entry.is_file() else None,
                'modified': datetime.datetime.fromtimestamp(entry.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'uploader': uploader_name,
                'uploaded_by': uploaded_by,
                'is_private': is_private,
                'can_toggle': bool(is_uploader)
            })

    return jsonify({'current_path': req_path, 'items': items})

@files_bp.route('/api/upload', methods=['POST'])
@login_required
def upload():
    if not session.get('can_write') and not session.get('is_admin'):
        return jsonify({'error': 'Write permission required'}), 403

    req_path = request.form.get('path', '')
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'No file uploaded'}), 400

    is_private = request.form.get('is_private', 'false').lower() in ['true', '1', 'yes', 'on']

    filename = secure_filename(file.filename)
    dest = os.path.join(safe_path(req_path), filename)
    abs_dest = os.path.abspath(dest)

    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT id, uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_dest,))
    existing = cursor.fetchone()
    cursor.fetchall()

    # If file exists and is private, only the original uploader can overwrite it
    if existing and existing.get('is_private') and existing.get('uploaded_by') != session['user_id']:
        cursor.close()
        conn.close()
        return jsonify({'error': 'A private file already exists with this name'}), 403

    file.save(dest)

    if existing:
        cursor.execute(
            "UPDATE file_metadata SET filename = %s, file_size = %s, uploaded_by = %s, is_private = %s, uploaded_at = CURRENT_TIMESTAMP WHERE id = %s",
            (filename, os.path.getsize(dest), session['user_id'], is_private, existing['id'])
        )
    else:
        cursor.execute(
            "INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by, is_private) VALUES (%s, %s, %s, %s, %s)",
            (filename, abs_dest, os.path.getsize(dest), session['user_id'], is_private)
        )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'filename': filename, 'is_private': is_private})

@files_bp.route('/api/files/visibility', methods=['POST'])
@login_required
def toggle_visibility():
    data = request.json or {}
    req_path = data.get('path', '')
    try:
        target = safe_path(req_path)
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    abs_target = os.path.abspath(target)
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT id, uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_target,))
    meta = cursor.fetchone()
    cursor.fetchall()

    if not meta:
        cursor.close()
        conn.close()
        return jsonify({'error': 'File not found or not owned by user'}), 404

    # Permission check: ONLY the user who uploaded the file can change visibility
    if meta['uploaded_by'] != session.get('user_id'):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Permission denied: only the user who uploaded this file can change its visibility'}), 403

    new_state = not bool(meta['is_private']) if 'is_private' not in data else bool(data['is_private'])
    cursor.execute("UPDATE file_metadata SET is_private = %s WHERE id = %s", (new_state, meta['id']))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'is_private': new_state})

@files_bp.route('/api/download')
@login_required
def download():
    try:
        path = safe_path(request.args.get('path', ''))
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404

    abs_path = os.path.abspath(path)
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_path,))
    meta = cursor.fetchone()
    cursor.fetchall()
    cursor.close()
    conn.close()

    # Private files can strictly ONLY be downloaded by the user who uploaded them
    if meta and meta.get('is_private'):
        if meta.get('uploaded_by') != session.get('user_id'):
            return jsonify({'error': 'Access denied: private file'}), 403

    return send_file(path, as_attachment=True)

@files_bp.route('/api/mkdir', methods=['POST'])
@login_required
def mkdir():
    if not session.get('can_write') and not session.get('is_admin'):
        return jsonify({'error': 'Write permission required'}), 403
    data = request.json or {}
    folder = secure_filename(data.get('folder_name', ''))
    if not folder:
        return jsonify({'error': 'Invalid folder name'}), 400
    folder_path = os.path.join(safe_path(data.get('path', '')), folder)
    os.makedirs(folder_path, exist_ok=True)

    abs_path = os.path.abspath(folder_path)
    is_private = bool(data.get('is_private', False))

    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT id FROM file_metadata WHERE file_path = %s", (abs_path,))
    existing = cursor.fetchone()
    cursor.fetchall()

    if not existing:
        cursor.execute(
            "INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by, is_private) VALUES (%s, %s, %s, %s, %s)",
            (folder, abs_path, 0, session['user_id'], is_private)
        )
        conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@files_bp.route('/api/delete', methods=['POST'])
@login_required
def delete():
    data = request.json or {}
    try:
        target = safe_path(data.get('path', ''))
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    abs_target = os.path.abspath(target)
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_target,))
    meta = cursor.fetchone()
    cursor.fetchall()

    is_owner = (meta and meta['uploaded_by'] == session.get('user_id'))
    # Private files can strictly only be deleted by the uploader
    if meta and meta.get('is_private') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Access denied: private file'}), 403

    if not session.get('can_delete') and not session.get('is_admin') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Delete permission required'}), 403

    if os.path.isfile(target):
        os.remove(target)
    elif os.path.isdir(target):
        shutil.rmtree(target)
    else:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Item not found'}), 404

    cursor.execute("DELETE FROM file_metadata WHERE file_path = %s OR file_path LIKE %s",
                   (abs_target, abs_target + '/%'))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})
