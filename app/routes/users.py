from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from app.database import get_db
from app.decorators import login_required, admin_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("SELECT u.id, u.username, u.role_id, r.name as role_name, u.created_at FROM users u JOIN roles r ON u.role_id = r.id")
        user_list = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'users': user_list})

    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    role_id = data.get('role_id', 2)

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

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
