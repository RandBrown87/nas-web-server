import unittest
import os
import shutil
import json
from app import create_app
from app.database import get_db
from config import Config
from fallback_server import app as fallback_app, watchdog

class TestNewFeaturesAndBugfixes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.fallback_client = fallback_app.test_client()

        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        self.test_filename = "test_feature_doc.txt"
        self.test_file_path = os.path.join(Config.STORAGE_DIR, self.test_filename)
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Critical configuration data.")

        abs_path = os.path.abspath(self.test_file_path)
        # Ensure DB record for file ownership & permissions testing
        # User 16 is incognito_User with role 'readonly'
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_metadata WHERE filename = %s", (self.test_filename,))
            cursor.execute("""
                INSERT INTO file_metadata (filename, file_path, file_size, uploaded_by, is_private, access_level)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (self.test_filename, abs_path, len("Line 1: Critical configuration data."), 16, 0, 'editable'))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print("DB setup error:", e)

    def tearDown(self):
        if os.path.exists(self.test_file_path):
            try:
                os.remove(self.test_file_path)
            except OSError:
                pass
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_metadata WHERE filename = %s", (self.test_filename,))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass
        self.app_context.pop()

    def test_readonly_user_cannot_edit_even_if_owner(self):
        """Bug fix verification: read-only user cannot edit content in preview mode even if owner."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 16  # incognito_User in DB with role 'readonly' and owner of file
            sess['username'] = 'incognito_User'
            sess['is_admin'] = False
            sess['can_write'] = False
            sess['can_edit'] = False

        # Attempt to read content: can_edit must be False
        res = self.client.get(f'/api/file/content?path={self.test_filename}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['can_edit'])
        self.assertIn("read-only", data.get('lock_reason', '').lower())

        # Attempt to save content: MUST return 403 Forbidden
        res_post = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Attempted unauthorized edit by read-only owner!'
        })
        self.assertEqual(res_post.status_code, 403)
        self.assertIn("read-only", res_post.get_json().get('error', '').lower())

    def test_file_access_modifier_readonly_blocks_editor(self):
        """Feature: file-level access_level == 'readonly' locks file editing for regular editors."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE file_metadata SET access_level = 'readonly' WHERE filename = %s", (self.test_filename,))
        conn.commit()
        cursor.close()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['user_id'] = 7  # Ash_iphone with role 'user' (has edit permissions)
            sess['username'] = 'Ash_iphone'
            sess['is_admin'] = False
            sess['can_write'] = True
            sess['can_edit'] = True

        # Editor can view, but can_edit should be False due to file-level lock
        res = self.client.get(f'/api/file/content?path={self.test_filename}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['can_edit'])
        self.assertEqual(data.get('access_level'), 'readonly')

        # Editor attempting to save should be blocked with 403
        res_post = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Attempting edit on read-only locked file'
        })
        self.assertEqual(res_post.status_code, 403)
        self.assertIn("read-only", res_post.get_json().get('error', '').lower())

    def test_admin_can_override_file_readonly_lock(self):
        """Admin can edit files even if marked as readonly."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE file_metadata SET access_level = 'readonly' WHERE filename = %s", (self.test_filename,))
        conn.commit()
        cursor.close()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True
            sess['can_edit'] = True

        res_post = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Admin authorized update on locked file.'
        })
        self.assertEqual(res_post.status_code, 200)
        self.assertTrue(res_post.get_json().get('success'))

    def test_file_access_api_endpoint(self):
        """Test POST /api/files/access modifies access_level."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        # Change to readonly
        res = self.client.post('/api/files/access', json={
            'path': self.test_filename,
            'access_level': 'readonly'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json().get('access_level'), 'readonly')

        # Change to private
        res = self.client.post('/api/files/access', json={
            'path': self.test_filename,
            'access_level': 'private'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json().get('access_level'), 'private')

        # Invalid access level should be rejected
        res_bad = self.client.post('/api/files/access', json={
            'path': self.test_filename,
            'access_level': 'invalid_level'
        })
        self.assertEqual(res_bad.status_code, 400)

    def test_backup_datetime_formatting(self):
        """Feature: backup listings return formatted date and time."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        res = self.client.get('/api/backup')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('backups', data)
        self.assertIn('latest_backup_time', data)

        res_sched = self.client.get('/api/backup/schedule')
        self.assertEqual(res_sched.status_code, 200)
        sched_data = res_sched.get_json()
        self.assertIn('schedule', sched_data)
        self.assertIn('last_run_formatted', sched_data['schedule'])
        self.assertIn('next_run_formatted', sched_data['schedule'])

    def test_health_check_endpoint(self):
        """Primary server health check endpoint returns 200 and healthy status."""
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertTrue(data.get('storage_accessible'))

    def test_fallback_server_endpoints(self):
        """Fallback server status and stand-down endpoints work."""
        res_status = self.fallback_client.get('/api/fallback/status')
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.get_json()
        self.assertIn('mode', status_data)
        self.assertIn('fallback_port', status_data)

        # Stand down
        res_standdown = self.fallback_client.post('/api/fallback/stand-down')
        self.assertEqual(res_standdown.status_code, 200)
        self.assertEqual(res_standdown.get_json().get('mode'), 'STANDBY')

if __name__ == '__main__':
    unittest.main()
