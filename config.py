import os
import platform

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nas_super_secret_key_2026')
    
    # Use /srv on Linux; use local project folders on Mac
    IS_LINUX = platform.system() == 'Linux'
    STORAGE_DIR = '/srv/nas_storage' if IS_LINUX else os.path.abspath('./storage')
    BACKUP_DIR = '/srv/nas_backups' if IS_LINUX else os.path.abspath('./backups')
    
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'nas_user'),
        'password': os.environ.get('DB_PASS', 'NasPassword123!'),
        'database': os.environ.get('DB_NAME', 'nas_db')
    }
