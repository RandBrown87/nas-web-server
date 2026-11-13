import os
from flask import Flask
from config import Config
from app.database import get_db
from werkzeug.security import generate_password_hash

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        # Ensure is_private column exists in file_metadata
        try:
            cursor.execute("ALTER TABLE file_metadata ADD COLUMN is_private BOOLEAN DEFAULT FALSE")
            conn.commit()
        except Exception:
            pass

        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()['count'] == 0:
            hashed = generate_password_hash("AdminPass123!", method='pbkdf2:sha256')
            cursor.execute("INSERT INTO users (username, password_hash, role_id) VALUES (%s, %s, %s)",
                           ('admin', hashed, 1))
            conn.commit()
            print("Default admin created: admin / AdminPass123!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"DB not initialized or not yet reachable: {e}")

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(Config.STORAGE_DIR, exist_ok=True)
    os.makedirs(Config.BACKUP_DIR, exist_ok=True)

    from app.routes.auth import auth_bp
    from app.routes.files import files_bp
    from app.routes.system import system_bp
    from app.routes.users import users_bp
    from app.routes.backup import backup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(backup_bp)

    with app.app_context():
        init_db()

    return app
