import os
import json
import shutil
import tarfile
import datetime
import subprocess
from config import Config
from app.database import get_db

def dump_mysql_database(output_path):
    """
    Creates a full SQL dump of the MySQL database.
    Attempts mysqldump CLI first; if unavailable, uses Python SQL dump generator.
    """
    db_cfg = Config.DB_CONFIG
    mysqldump_bin = shutil.which('mysqldump')

    if mysqldump_bin:
        try:
            cmd = [
                mysqldump_bin,
                f"--host={db_cfg['host']}",
                f"--user={db_cfg['user']}",
                f"--password={db_cfg['password']}",
                "--add-drop-table",
                "--single-transaction",
                "--skip-comments",
                db_cfg['database']
            ]
            with open(output_path, 'w', encoding='utf-8') as f:
                res = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and os.path.getsize(output_path) > 0:
                return True
        except Exception:
            pass

    # Pure Python SQL dump generator (zero dependency, fully portable)
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW TABLES")
    tables_result = cursor.fetchall()
    table_names = [list(row.values())[0] for row in tables_result]

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("-- Linux NAS System Database Dump\n")
        f.write(f"-- Generated: {datetime.datetime.now().isoformat()}\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        for table in table_names:
            # Table structure
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_row = cursor.fetchone()
            create_sql = list(create_row.values())[1]
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            f.write(f"{create_sql};\n\n")

            # Table data
            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()
            if rows:
                col_names = list(rows[0].keys())
                col_str = ", ".join([f"`{c}`" for c in col_names])
                for r in rows:
                    vals = []
                    for c in col_names:
                        v = r[c]
                        if v is None:
                            vals.append("NULL")
                        elif isinstance(v, (int, float)):
                            vals.append(str(v))
                        elif isinstance(v, (datetime.datetime, datetime.date)):
                            vals.append(f"'{v.strftime('%Y-%m-%d %H:%M:%S')}'")
                        elif isinstance(v, bytes):
                            vals.append(f"X'{v.hex()}'")
                        else:
                            clean_v = str(v).replace("\\", "\\\\").replace("'", "''").replace("\n", "\\n").replace("\r", "\\r")
                            vals.append(f"'{clean_v}'")
                    f.write(f"INSERT INTO `{table}` ({col_str}) VALUES ({', '.join(vals)});\n")
                f.write("\n")

        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    cursor.close()
    conn.close()
    return True

def restore_mysql_database(sql_path):
    """
    Restores the database from an SQL dump file.
    """
    if not os.path.exists(sql_path):
        return False

    db_cfg = Config.DB_CONFIG
    mysql_bin = shutil.which('mysql')
    if mysql_bin:
        try:
            cmd = [
                mysql_bin,
                f"--host={db_cfg['host']}",
                f"--user={db_cfg['user']}",
                f"--password={db_cfg['password']}",
                db_cfg['database']
            ]
            with open(sql_path, 'r', encoding='utf-8') as f:
                res = subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    with open(sql_path, 'r', encoding='utf-8', errors='replace') as f:
        sql_content = f.read()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    # Split statements carefully
    statements = sql_content.split(';\n')
    for stmt in statements:
        clean = stmt.strip()
        if clean and not clean.startswith('--') and not clean.startswith('/*'):
            try:
                cursor.execute(clean)
            except Exception:
                pass

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    cursor.close()
    conn.close()
    return True

def perform_full_backup(include_db=True, backup_type='manual'):
    """
    Creates a full backup archive (.tar.gz) containing storage files and MySQL database dump.
    """
    os.makedirs(Config.BACKUP_DIR, exist_ok=True)
    os.makedirs(Config.STORAGE_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{backup_type}_{timestamp}.tar.gz"
    filepath = os.path.join(Config.BACKUP_DIR, filename)

    tmp_dump_path = os.path.join(Config.BACKUP_DIR, f"temp_db_{timestamp}.sql")
    tmp_meta_path = os.path.join(Config.BACKUP_DIR, f"temp_meta_{timestamp}.json")

    try:
        # Dump DB if requested
        if include_db:
            dump_mysql_database(tmp_dump_path)

        # Create system configuration metadata
        system_meta = {
            'timestamp': datetime.datetime.now().isoformat(),
            'backup_name': filename,
            'backup_type': backup_type,
            'includes_db': include_db,
            'storage_dir': Config.STORAGE_DIR,
            'server_version': 'NAS-Server-2.0'
        }
        with open(tmp_meta_path, 'w', encoding='utf-8') as f:
            json.dump(system_meta, f, indent=2)

        # Build tar.gz
        with tarfile.open(filepath, "w:gz") as tar:
            # Add storage directory
            tar.add(Config.STORAGE_DIR, arcname='storage')
            if include_db and os.path.exists(tmp_dump_path):
                tar.add(tmp_dump_path, arcname='nas_db_dump.sql')
            if os.path.exists(tmp_meta_path):
                tar.add(tmp_meta_path, arcname='system_config.json')

        # Record in backups table
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO backups (backup_name, file_path, status) VALUES (%s, %s, %s)",
            (filename, filepath, 'completed')
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {'success': True, 'backup_name': filename, 'file_path': filepath}
    finally:
        # Clean up temporary files
        if os.path.exists(tmp_dump_path):
            os.remove(tmp_dump_path)
        if os.path.exists(tmp_meta_path):
            os.remove(tmp_meta_path)

def perform_full_restore(backup_name):
    """
    Restores storage files and MySQL database from a backup archive.
    """
    filepath = os.path.join(Config.BACKUP_DIR, backup_name)
    if not os.path.exists(filepath):
        return {'success': False, 'error': 'Backup archive not found'}

    extract_tmp = os.path.join(Config.BACKUP_DIR, f"extract_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
    os.makedirs(extract_tmp, exist_ok=True)

    try:
        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(path=extract_tmp)

        # 1. Restore storage files
        extracted_storage = os.path.join(extract_tmp, 'storage')
        if os.path.exists(extracted_storage):
            # Copy all files into STORAGE_DIR
            for item in os.listdir(extracted_storage):
                src = os.path.join(extracted_storage, item)
                dst = os.path.join(Config.STORAGE_DIR, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        # 2. Restore database dump if present
        extracted_sql = os.path.join(extract_tmp, 'nas_db_dump.sql')
        db_restored = False
        if os.path.exists(extracted_sql):
            restore_mysql_database(extracted_sql)
            db_restored = True

        return {'success': True, 'db_restored': db_restored}
    finally:
        if os.path.exists(extract_tmp):
            shutil.rmtree(extract_tmp)

def calculate_next_run(frequency, backup_time):
    """
    Calculates next execution datetime based on frequency ('hourly', 'daily', 'weekly') and backup_time ('HH:MM').
    """
    now = datetime.datetime.now()
    try:
        hour, minute = map(int, backup_time.split(':'))
    except Exception:
        hour, minute = 2, 0

    if frequency == 'hourly':
        next_run = now + datetime.timedelta(hours=1)
        next_run = next_run.replace(minute=minute, second=0, microsecond=0)
    elif frequency == 'weekly':
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += datetime.timedelta(days=7)
    else:  # daily
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += datetime.timedelta(days=1)

    return next_run

def check_and_run_scheduled_backups():
    """
    Checks if a scheduled backup is due and runs it.
    """
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM backup_schedules LIMIT 1")
        schedule = cursor.fetchone()
        cursor.close()
        conn.close()

        if not schedule or not schedule['enabled']:
            return False

        now = datetime.datetime.now()
        next_run = schedule['next_run']

        if next_run and now < next_run:
            return False

        # Run backup
        perform_full_backup(include_db=bool(schedule.get('include_db', True)), backup_type='scheduled')

        # Update last_run and next_run
        new_next = calculate_next_run(schedule.get('frequency', 'daily'), schedule.get('backup_time', '02:00'))
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE backup_schedules SET last_run = %s, next_run = %s WHERE id = %s",
            (now, new_next, schedule['id'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error checking scheduled backups: {e}")
        return False
