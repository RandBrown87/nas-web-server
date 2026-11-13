import unittest
import os
import shutil
from app import create_app
from app.database import get_db
from config import Config

class TestFileEditorPermissions(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        self.test_filename = "editor_sample.txt"
        self.test_file_path = os.path.join(Config.STORAGE_DIR, self.test_filename)
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Initial Content\nLine 2: Server Config")

    def tearDown(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        self.app_context.pop()

    def test_admin_read_and_edit_content(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True
            sess['can_edit'] = True

        # Read content
        res = self.client.get(f'/api/file/content?path={self.test_filename}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("Initial Content", data['content'])
        self.assertTrue(data['can_edit'])

        # Save edited content
        res_save = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Updated by Admin!'
        })
        self.assertEqual(res_save.status_code, 200)
        self.assertTrue(res_save.get_json().get('success'))

        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Updated by Admin!")

    def test_editor_user_can_edit(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 4
            sess['username'] = 'editor_user'
            sess['is_admin'] = False
            sess['can_write'] = False
            sess['can_edit'] = True

        res = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Updated by Editor!'
        })
        self.assertEqual(res.status_code, 200)

        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Updated by Editor!")

    def test_readonly_user_cannot_edit(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'readonly_user'
            sess['is_admin'] = False
            sess['can_write'] = False
            sess['can_edit'] = False

        # Read is allowed
        res = self.client.get(f'/api/file/content?path={self.test_filename}')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()['can_edit'])

        # Edit is blocked
        res_save = self.client.post('/api/file/content', json={
            'path': self.test_filename,
            'content': 'Malicious Write'
        })
        self.assertEqual(res_save.status_code, 403)

    def test_traversal_blocked(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        res = self.client.get('/api/file/content?path=../../etc/passwd')
        self.assertIn(res.status_code, [400, 403])

if __name__ == '__main__':
    unittest.main()
