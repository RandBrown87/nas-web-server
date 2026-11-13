from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from app.database import get_db
from app.decorators import login_required, admin_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/roles', methods=['GET'])
@login_required
@admin_required
def get_roles():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, can_read, can_write, can_edit, can_delete, is_admin FROM roles ORDER BY id ASC")
    role_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'roles': role_list})

@users_bp.route('/api/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("""
            SELECT u.id, u.username, u.role_id, r.name as role_name,
                   r.can_read, r.can_write, r.can_edit, r.can_delete, r.is_admin,
                   u.created_at
            FROM users u
            JOIN roles r ON u.role_id = r.id
            ORDER BY u.id ASC
        """)
        user_list = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'users': user_list})

    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password')
    role_id = data.get('role_id', 2)

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    if len(username) < 3 or len(username) > 50 or not username.replace('_', '').replace('-', '').isalnum():
        return jsonify({'error': 'Invalid username format (3-50 alphanumeric chars, -, _)'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        cursor.execute("INSERT INTO users (username, password_hash, role_id) VALUES (%s, %s, %s)",
                       (username, generate_password_hash(password, method='pbkdf2:sha256'), role_id))
        conn.commit()
    except Exception:
        return jsonify({'error': 'Username already exists'}), 400
    finally:
        cursor.close()
        conn.close()
    return jsonify({'success': True})

@users_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@users_bp.route('/api/users/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    data = request.json or {}
    new_username = (data.get('username') or '').strip()
    new_password = data.get('password')
    new_role_id = data.get('role_id')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT u.*, r.is_admin FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s", (user_id,))
    target_user = cursor.fetchone()

    if not target_user:
        cursor.close()
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    # If updating role, check if target is the only admin and being demoted
    if new_role_id is not None:
        try:
            new_role_id = int(new_role_id)
        except ValueError:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid role_id'}), 400

        cursor.execute("SELECT is_admin FROM roles WHERE id = %s", (new_role_id,))
        target_role = cursor.fetchone()
        if not target_role:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Target role does not exist'}), 400

        if target_user['is_admin'] and not target_role['is_admin']:
            cursor.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id = r.id WHERE r.is_admin = TRUE")
            admin_count = cursor.fetchone()['count']
            if admin_count <= 1:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Cannot demote the only administrator'}), 400

    updates = []
    params = []

    if new_username and new_username != target_user['username']:
        if len(new_username) < 3 or len(new_username) > 50 or not new_username.replace('_', '').replace('-', '').isalnum():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid username format'}), 400
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username already taken'}), 400
        updates.append("username = %s")
        params.append(new_username)

    if new_password:
        if len(new_password) < 6:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        updates.append("password_hash = %s")
        params.append(generate_password_hash(new_password, method='pbkdf2:sha256'))

    if new_role_id is not None:
        updates.append("role_id = %s")
        params.append(new_role_id)

    if not updates:
        cursor.close()
        conn.close()
        return jsonify({'message': 'No changes requested', 'success': True})

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
    cursor.execute(query, params)
    conn.commit()

    # Update session if current user modified their own account
    if user_id == session.get('user_id'):
        if new_username:
            session['username'] = new_username
        if new_role_id is not None:
            cursor.execute("SELECT r.* FROM roles r WHERE r.id = %s", (new_role_id,))
            r = cursor.fetchone()
            if r:
                session['is_admin'] = bool(r['is_admin'])
                session['can_write'] = bool(r['can_write'])
                session['can_edit'] = bool(r.get('can_edit', True))
                session['can_delete'] = bool(r['can_delete'])

    cursor.close()
    conn.close()
    return jsonify({'success': True, 'message': 'User updated successfully'})


@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})
