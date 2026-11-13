import unittest
import os
import shutil
import io
from app import create_app
from app.database import get_db
from config import Config

class TestRename(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Ensure storage directory exists
        os.makedirs(Config.STORAGE_DIR, exist_ok=True)

        # Clear test files in storage
        for item in os.listdir(Config.STORAGE_DIR):
            p = os.path.join(Config.STORAGE_DIR, item)
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)

    def tearDown(self):
        self.app_context.pop()

    def test_file_rename_success(self):
        # Create a test file
        test_file_path = os.path.join(Config.STORAGE_DIR, "test_file.txt")
        with open(test_file_path, "w") as f:
            f.write("Hello NAS")

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True
            sess['can_delete'] = True

        res = self.client.post('/api/rename', json={
            'old_path': 'test_file.txt',
            'new_name': 'renamed_file.txt'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))
        self.assertFalse(os.path.exists(test_file_path))
        self.assertTrue(os.path.exists(os.path.join(Config.STORAGE_DIR, "renamed_file.txt")))

    def test_folder_rename_success(self):
        folder_path = os.path.join(Config.STORAGE_DIR, "test_folder")
        os.makedirs(folder_path, exist_ok=True)
        sub_file = os.path.join(folder_path, "inner.txt")
        with open(sub_file, "w") as f:
            f.write("inside folder")

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True

        res = self.client.post('/api/rename', json={
            'old_path': 'test_folder',
            'new_name': 'renamed_folder'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))
        self.assertFalse(os.path.exists(folder_path))
        self.assertTrue(os.path.exists(os.path.join(Config.STORAGE_DIR, "renamed_folder", "inner.txt")))

    def test_rename_traversal_blocked(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True

        # Directory traversal attempt in old_path
        res = self.client.post('/api/rename', json={
            'old_path': '../../etc/passwd',
            'new_name': 'hacked.txt'
        })
        self.assertEqual(res.status_code, 400)

        # Directory traversal attempt in new_name
        res2 = self.client.post('/api/rename', json={
            'old_path': 'test_file.txt',
            'new_name': '../outside.txt'
        })
        self.assertEqual(res2.status_code, 400)

    def test_readonly_user_cannot_rename(self):
        test_file_path = os.path.join(Config.STORAGE_DIR, "readonly_test.txt")
        with open(test_file_path, "w") as f:
            f.write("test")

        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'reader'
            sess['is_admin'] = False
            sess['can_write'] = False

        res = self.client.post('/api/rename', json={
            'old_path': 'readonly_test.txt',
            'new_name': 'should_fail.txt'
        })
        self.assertEqual(res.status_code, 403)

if __name__ == '__main__':
    unittest.main()
