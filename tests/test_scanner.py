import unittest
import os
import shutil
import io
from app import create_app
from config import Config
from app.scanner import scan_file, EICAR_SIGNATURE
from app.database import get_db

class TestMalwareProtectionGateway(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        os.makedirs(Config.STORAGE_DIR, exist_ok=True)
        os.makedirs(Config.QUARANTINE_DIR, exist_ok=True)

    def tearDown(self):
        self.app_context.pop()

    def test_scan_clean_file(self):
        clean_path = os.path.join(Config.STORAGE_DIR, "clean_doc.txt")
        with open(clean_path, "w") as f:
            f.write("Just an innocent meeting agenda.")
        try:
            res = scan_file(clean_path)
            self.assertEqual(res['status'], 'clean')
            self.assertIsNone(res['threat'])
        finally:
            if os.path.exists(clean_path):
                os.remove(clean_path)

    def test_scan_eicar_test_malware(self):
        infected_path = os.path.join(Config.QUARANTINE_DIR, "eicar_test.com")
        with open(infected_path, "wb") as f:
            f.write(EICAR_SIGNATURE)
        try:
            res = scan_file(infected_path)
            self.assertEqual(res['status'], 'infected')
            self.assertIn('EICAR', res['threat'])
        finally:
            if os.path.exists(infected_path):
                os.remove(infected_path)

    def test_upload_clean_file_passes(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True

        data = {
            'file': (io.BytesIO(b"Hello clean world"), 'good_file.txt'),
            'path': ''
        }
        res = self.client.post('/api/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_res = res.get_json()
        self.assertTrue(json_res['success'])
        self.assertEqual(json_res['scan_result'], 'clean')

        dest_file = os.path.join(Config.STORAGE_DIR, 'good_file.txt')
        self.assertTrue(os.path.exists(dest_file))
        if os.path.exists(dest_file):
            os.remove(dest_file)

    def test_upload_malware_file_quarantined_and_blocked(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True
            sess['can_write'] = True

        # Upload EICAR infected test payload
        data = {
            'file': (io.BytesIO(EICAR_SIGNATURE), 'virus_payload.com'),
            'path': ''
        }
        res = self.client.post('/api/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 422)
        json_res = res.get_json()
        self.assertTrue(json_res['quarantined'])
        self.assertIn('EICAR', json_res['threat'])

        # File must NOT be in storage!
        self.assertFalse(os.path.exists(os.path.join(Config.STORAGE_DIR, 'virus_payload.com')))

    def test_security_stats_and_history_api(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['is_admin'] = True

        res = self.client.get('/api/security/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('total_scans', data)
        self.assertIn('clean_files', data)
        self.assertIn('infected_threats', data)
        self.assertIn('quarantined_files', data)

        res_scans = self.client.get('/api/security/scans')
        self.assertEqual(res_scans.status_code, 200)
        self.assertIn('scans', res_scans.get_json())

if __name__ == '__main__':
    unittest.main()
