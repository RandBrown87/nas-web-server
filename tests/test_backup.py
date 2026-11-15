import unittest
import os
import shutil
import tarfile
from app import create_app
from config import Config
from app.backup_utils import dump_mysql_database, perform_full_backup, perform_full_restore, calculate_next_run

class TestBackupAndRestore(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        os.makedirs(Config.BACKUP_DIR, exist_ok=True)

        self.sample_file = os.path.join(Config.STORAGE_DIR, "backup_sample.txt")
        with open(self.sample_file, "w") as f:
            f.write("Important NAS User Data")

    def tearDown(self):
        if os.path.exists(self.sample_file):
            os.remove(self.sample_file)
        self.app_context.pop()

    def test_database_dump_creation(self):
        dump_path = os.path.join(Config.BACKUP_DIR, "test_manual_dump.sql")
        try:
            success = dump_mysql_database(dump_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(dump_path))
            self.assertGreater(os.path.getsize(dump_path), 0)

            with open(dump_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("users", content)
            self.assertIn("roles", content)
        finally:
            if os.path.exists(dump_path):
                os.remove(dump_path)

    def test_full_backup_and_restore(self):
        res = perform_full_backup(include_db=True, backup_type='test')
        self.assertTrue(res['success'])
        backup_name = res['backup_name']
        backup_path = res['file_path']
        self.assertTrue(os.path.exists(backup_path))

        # Inspect archive contents
        with tarfile.open(backup_path, "r:gz") as tar:
            names = tar.getnames()
            self.assertTrue(any("storage" in n for n in names))
            self.assertIn("nas_db_dump.sql", names)
            self.assertIn("system_config.json", names)

        # Modify storage file
        with open(self.sample_file, "w") as f:
            f.write("Corrupted file content")

        # Perform restore
        restore_res = perform_full_restore(backup_name)
        self.assertTrue(restore_res['success'])
        self.assertTrue(restore_res['db_restored'])

        # Check restored content
        with open(self.sample_file, "r") as f:
            self.assertEqual(f.read(), "Important NAS User Data")

    def test_backup_schedule_api(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        # Update schedule
        res = self.client.post('/api/backup/schedule', json={
            'enabled': True,
            'frequency': 'weekly',
            'backup_time': '03:30',
            'include_db': True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['schedule']
        self.assertTrue(data['enabled'])
        self.assertEqual(data['frequency'], 'weekly')
        self.assertEqual(data['backup_time'], '03:30')
        self.assertIsNotNone(data['next_run'])

        # Read schedule back
        res_get = self.client.get('/api/backup/schedule')
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(res_get.get_json()['schedule']['enabled'])

    def test_calculate_next_run(self):
        next_daily = calculate_next_run('daily', '02:00')
        self.assertEqual(next_daily.hour, 2)
        self.assertEqual(next_daily.minute, 0)

        next_hourly = calculate_next_run('hourly', '02:15')
        self.assertEqual(next_hourly.minute, 15)

if __name__ == '__main__':
    unittest.main()
