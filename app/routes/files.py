import os
import shutil
import datetime
from flask import Blueprint, render_template, request, session, jsonify, send_file
from werkzeug.utils import secure_filename
from config import Config
from app.database import get_db
from app.decorators import login_required
from app.scanner import scan_file

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

    # Stage upload in Quarantine folder first for Antivirus scanning
    os.makedirs(Config.QUARANTINE_DIR, exist_ok=True)
    temp_quarantine_path = os.path.join(
        Config.QUARANTINE_DIR,
        f"staging_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    )
    file.save(temp_quarantine_path)

    # Scan staged file with ClamAV Malware Protection Gateway
    scan_result = scan_file(temp_quarantine_path)

    if scan_result.get('status') == 'infected':
        threat = scan_result.get('threat', 'Malware.Detected')
        quarantine_dest = os.path.join(
            Config.QUARANTINE_DIR,
            f"quarantine_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        )
        os.rename(temp_quarantine_path, quarantine_dest)

        # Log infected attempt to security_scans table
        cursor.execute("""
            INSERT INTO security_scans (filename, file_path, uploaded_by, scan_result, threat_name, is_quarantined)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (filename, quarantine_dest, session['user_id'], 'infected', threat, True))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'error': f"Malware Detected ({threat})! File has been blocked and quarantined.",
            'threat': threat,
            'quarantined': True
        }), 422

    # Clean file: Move from quarantine to NAS storage
    try:
        shutil.move(temp_quarantine_path, dest)
    except Exception as e:
        if os.path.exists(temp_quarantine_path):
            os.remove(temp_quarantine_path)
        cursor.close()
        conn.close()
        return jsonify({'error': f'Failed to store clean file: {str(e)}'}), 500

    # Log clean scan
    cursor.execute("""
        INSERT INTO security_scans (filename, file_path, uploaded_by, scan_result, threat_name, is_quarantined)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (filename, abs_dest, session['user_id'], 'clean', None, False))

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

    return jsonify({'success': True, 'filename': filename, 'is_private': is_private, 'scan_result': 'clean'})

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

@files_bp.route('/api/preview')
@login_required
def preview():
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

    # Private files can strictly ONLY be previewed by the user who uploaded them
    if meta and meta.get('is_private'):
        if meta.get('uploaded_by') != session.get('user_id'):
            return jsonify({'error': 'Access denied: private file'}), 403

    import mimetypes
    mimetype, _ = mimetypes.guess_type(path)
    if not mimetype:
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.py', '.js', '.ts', '.html', '.css', '.json', '.sql', '.sh', '.md', '.log', '.csv']:
            mimetype = 'text/plain; charset=utf-8'
        else:
            mimetype = 'application/octet-stream'

    return send_file(path, mimetype=mimetype, as_attachment=False)


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

@files_bp.route('/api/rename', methods=['POST'])
@login_required
def rename_item():
    data = request.json or {}
    old_path = data.get('old_path', '').strip()
    new_name = data.get('new_name', '').strip()

    if not old_path or not new_name:
        return jsonify({'error': 'Old path and new name are required'}), 400

    if '/' in new_name or '\\' in new_name or '..' in new_name:
        return jsonify({'error': 'Invalid new name'}), 400

    sanitized_new_name = secure_filename(new_name)
    if not sanitized_new_name:
        return jsonify({'error': 'Invalid new name'}), 400

    try:
        old_abs = safe_path(old_path)
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.exists(old_abs):
        return jsonify({'error': 'Item not found'}), 404

    parent_dir = os.path.dirname(old_abs)
    new_abs = os.path.abspath(os.path.join(parent_dir, sanitized_new_name))

    base = os.path.abspath(Config.STORAGE_DIR)
    if not new_abs.startswith(base):
        return jsonify({'error': 'Invalid target path'}), 400

    if os.path.exists(new_abs):
        return jsonify({'error': f"An item named '{sanitized_new_name}' already exists"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT id, uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (old_abs,))
    meta = cursor.fetchone()
    cursor.fetchall()

    is_owner = (meta and meta['uploaded_by'] == session.get('user_id'))
    if meta and meta.get('is_private') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Access denied: private item'}), 403

    if not session.get('can_write') and not session.get('is_admin') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Write permission required'}), 403

    is_dir = os.path.isdir(old_abs)

    try:
        os.rename(old_abs, new_abs)
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'error': f'Filesystem rename failed: {str(e)}'}), 500

    if meta:
        cursor.execute(
            "UPDATE file_metadata SET filename = %s, file_path = %s WHERE id = %s",
            (sanitized_new_name, new_abs, meta['id'])
        )
    else:
        file_size = 0 if is_dir else os.path.getsize(new_abs)
        cursor.execute(
            "INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by) VALUES (%s, %s, %s, %s)",
            (sanitized_new_name, new_abs, file_size, session.get('user_id'))
        )

    if is_dir:
        old_prefix = old_abs + '/'
        new_prefix = new_abs + '/'
        cursor.execute(
            "UPDATE file_metadata SET file_path = CONCAT(%s, SUBSTRING(file_path, %s)) WHERE file_path LIKE %s",
            (new_prefix, len(old_prefix) + 1, old_prefix + '%')
        )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'new_name': sanitized_new_name})

@files_bp.route('/api/file/content', methods=['GET', 'POST'])
@login_required
def file_content():
    if request.method == 'GET':
        req_path = request.args.get('path', '')
        try:
            target = safe_path(req_path)
        except ValueError:
            return jsonify({'error': 'Invalid path'}), 400

        if not os.path.isfile(target):
            return jsonify({'error': 'File not found'}), 404

        abs_target = os.path.abspath(target)
        conn = get_db()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id, uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_target,))
        meta = cursor.fetchone()
        cursor.fetchall()
        cursor.close()
        conn.close()

        is_owner = (meta and meta['uploaded_by'] == session.get('user_id'))
        if meta and meta.get('is_private') and not is_owner:
            return jsonify({'error': 'Access denied: private file'}), 403

        if os.path.getsize(target) > 5 * 1024 * 1024:
            return jsonify({'error': 'File too large for inline editing (max 5MB)'}), 400

        try:
            with open(target, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            return jsonify({'error': f'Cannot read file: {str(e)}'}), 500

        can_edit = bool(session.get('can_edit') or session.get('is_admin') or is_owner)
        return jsonify({
            'path': req_path,
            'filename': os.path.basename(target),
            'content': content,
            'can_edit': can_edit
        })

    data = request.json or {}
    req_path = data.get('path', '')
    content = data.get('content', '')

    try:
        target = safe_path(req_path)
    except ValueError:
        return jsonify({'error': 'Invalid path'}), 400

    if not os.path.isfile(target):
        return jsonify({'error': 'File not found'}), 404

    abs_target = os.path.abspath(target)
    conn = get_db()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT id, uploaded_by, is_private FROM file_metadata WHERE file_path = %s", (abs_target,))
    meta = cursor.fetchone()
    cursor.fetchall()

    is_owner = (meta and meta['uploaded_by'] == session.get('user_id'))
    if meta and meta.get('is_private') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Access denied: private file'}), 403

    if not session.get('can_edit') and not session.get('is_admin') and not is_owner:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Edit permission required'}), 403

    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

    new_size = os.path.getsize(target)
    if meta:
        cursor.execute("UPDATE file_metadata SET file_size = %s WHERE id = %s", (new_size, meta['id']))
    else:
        cursor.execute(
            "INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by) VALUES (%s, %s, %s, %s)",
            (os.path.basename(target), abs_target, new_size, session.get('user_id'))
        )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'file_size': new_size})


