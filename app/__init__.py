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

        # Ensure can_edit column exists in roles
        try:
            cursor.execute("ALTER TABLE roles ADD COLUMN can_edit BOOLEAN DEFAULT TRUE")
            conn.commit()
        except Exception:
            pass

        cursor.execute("UPDATE roles SET can_edit = TRUE WHERE name IN ('admin', 'user')")
        cursor.execute("UPDATE roles SET can_edit = FALSE, can_write = FALSE, can_delete = FALSE WHERE name = 'readonly'")
        cursor.execute("INSERT IGNORE INTO roles (id, name, can_read, can_write, can_edit, can_delete, is_admin) VALUES (4, 'editor', TRUE, FALSE, TRUE, FALSE, FALSE)")
        conn.commit()

        # Table for automated backup schedules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                frequency VARCHAR(20) DEFAULT 'daily',
                backup_time VARCHAR(10) DEFAULT '02:00',
                include_db BOOLEAN DEFAULT TRUE,
                last_run TIMESTAMP NULL,
                next_run TIMESTAMP NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SELECT COUNT(*) as count FROM backup_schedules")
        if cursor.fetchone()['count'] == 0:
            cursor.execute("INSERT INTO backup_schedules (enabled, frequency, backup_time, include_db) VALUES (FALSE, 'daily', '02:00', TRUE)")
            conn.commit()

        # Table for Malware scans / ClamAV gateway
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_scans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                uploaded_by INT,
                scan_result VARCHAR(50) NOT NULL,
                threat_name VARCHAR(255),
                is_quarantined BOOLEAN DEFAULT FALSE,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Table for Web Application Firewall (WAF) logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waf_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ip_address VARCHAR(45) NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                attack_type VARCHAR(50) NOT NULL,
                payload_sample TEXT,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

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
    os.makedirs(Config.QUARANTINE_DIR, exist_ok=True)

    from app.routes.auth import auth_bp
    from app.routes.files import files_bp
    from app.routes.system import system_bp
    from app.routes.users import users_bp
    from app.routes.backup import backup_bp
    from app.routes.security import security_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(security_bp)

    with app.app_context():
        init_db()
        try:
            from app.scheduler import start_scheduler
            start_scheduler(app)
        except Exception as e:
            print(f"Could not start scheduler: {e}")

    return app
