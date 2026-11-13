import unittest
from app import create_app
from app.database import get_db
from werkzeug.security import check_password_hash

class TestUserManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_get_roles(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        res = self.client.get('/api/roles')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('roles', data)
        role_names = [r['name'] for r in data['roles']]
        self.assertIn('admin', role_names)
        self.assertIn('user', role_names)
        self.assertIn('readonly', role_names)
        self.assertIn('editor', role_names)

    def test_create_and_modify_user(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        # 1. Create a new user
        test_username = 'bob_builder'
        res_create = self.client.post('/api/users', json={
            'username': test_username,
            'password': 'InitialPassword123!',
            'role_id': 2
        })
        self.assertEqual(res_create.status_code, 200)

        # Get the created user ID
        res_list = self.client.get('/api/users')
        users = res_list.get_json()['users']
        created_user = next(u for u in users if u['username'] == test_username)
        user_id = created_user['id']

        # 2. Modify username and role to editor (role_id 4)
        res_update = self.client.put(f'/api/users/{user_id}', json={
            'username': 'bob_edited',
            'role_id': 4
        })
        self.assertEqual(res_update.status_code, 200)

        # Verify in DB
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s", (user_id,))
        updated = cursor.fetchone()
        self.assertEqual(updated['username'], 'bob_edited')
        self.assertEqual(updated['role_name'], 'editor')
        cursor.close()
        conn.close()

        # 3. Modify password
        res_pw = self.client.put(f'/api/users/{user_id}', json={
            'password': 'NewPassword456!'
        })
        self.assertEqual(res_pw.status_code, 200)

        conn2 = get_db()
        cursor2 = conn2.cursor(dictionary=True)
        cursor2.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        pw_row = cursor2.fetchone()
        self.assertTrue(check_password_hash(pw_row['password_hash'], 'NewPassword456!'))

        # Clean up created user
        cursor2.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn2.commit()
        cursor2.close()
        conn2.close()

    def test_cannot_demote_only_admin(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        # Attempt to demote admin (id 1) to readonly (role_id 3)
        res = self.client.put('/api/users/1', json={
            'role_id': 3
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('Cannot demote the only administrator', res.get_json().get('error', ''))

    def test_unauthorized_user_cannot_modify(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['username'] = 'regular_user'
            sess['is_admin'] = False

        res = self.client.put('/api/users/1', json={
            'username': 'hacked'
        })
        self.assertEqual(res.status_code, 403)

if __name__ == '__main__':
    unittest.main()
