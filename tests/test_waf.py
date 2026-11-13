import unittest
from app import create_app

class TestWebApplicationFirewall(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_sqli_attack_blocked(self):
        res = self.client.get('/api/files?path=1%27%20OR%20%271%27=%271')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertTrue(data.get('blocked'))
        self.assertIn('SQL Injection', data.get('attack_type', ''))

    def test_xss_attack_blocked(self):
        res = self.client.get('/api/files?path=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertTrue(data.get('blocked'))
        self.assertIn('XSS', data.get('attack_type', ''))

    def test_path_traversal_attack_blocked(self):
        res = self.client.get('/api/files?path=../../etc/passwd')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertTrue(data.get('blocked'))
        self.assertIn('Path Traversal', data.get('attack_type', ''))

    def test_scanner_user_agent_blocked(self):
        headers = {'User-Agent': 'sqlmap/1.6.4#stable (https://sqlmap.org)'}
        res = self.client.get('/login', headers=headers)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertTrue(data.get('blocked'))

    def test_legitimate_request_passes(self):
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)

    def test_waf_logs_and_stats_api(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        res = self.client.get('/api/waf/logs')
        self.assertEqual(res.status_code, 200)
        self.assertIn('waf_logs', res.get_json())

        res_stats = self.client.get('/api/waf/stats')
        self.assertEqual(res_stats.status_code, 200)
        self.assertIn('total_blocked', res_stats.get_json())

if __name__ == '__main__':
    unittest.main()
