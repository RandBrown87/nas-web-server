# Remaining Tasks – Project 2 (Status: All Complete)

All core and security tasks have been completed, verified with 27/27 automated unit tests, and committed:

- [x] **Implement file and folder renaming.** (Completed: `/api/rename`, DB recursive path updates, UI modal, tests in `test_rename.py`).
- [x] **Implement editing existing user accounts (username, password, role).** (Completed: `PUT /api/users/<id>`, password hashing, role updates, UI edit modal, tests in `test_users.py`).
- [x] **Verify read, write, edit, and admin permissions.** (Completed: 4 role model: Admin, User, Editor, ReadOnly; inline file editor `/api/file/content` with permission gates; tests in `test_file_editor.py`).
- [x] **Implement automatic scheduled backups (daily/weekly).** (Completed: background scheduler, UI schedule manager, cron script `deploy/nas_backup_cron`, tests in `test_backup.py`).
- [x] **Include MySQL database dumps in backups.** (Completed: zero-dependency + mysqldump SQL dumper in `app/backup_utils.py` included inside `.tar.gz` archives).
- [x] **Implement restoration of system configurations.** (Completed: database restores table schemas, permissions, file metadata, and storage files in `/api/restore`).
- [x] **Configure Apache for Linux production deployment.** (Completed: reverse proxy config in `deploy/nas_apache.conf` and systemd service `deploy/nas.service`).
- [x] **Configure Linux firewall (UFW).** (Completed: hardened firewall setup in `deploy/setup_server.sh` allowing 80, 443, 5050, 22).
- [x] **Set Linux storage permissions (chmod/chown).** (Completed: `chmod 770` and `chown -R www-data:www-data` in `deploy/setup_server.sh`).
- [x] **Configure router port forwarding for remote access.** (Completed: comprehensive architecture and configuration documentation in `deploy/PORT_FORWARDING_GUIDE.md`).
- [x] **Test all features and user permissions.** (Completed: 27/27 tests passing across `tests/test_*.py`).
- [x] **Security Feature 1: NAS Malware Protection Gateway.** (Completed: ClamAV integration, quarantine staging folder, EICAR test signature detection, threat inspector, storage scanner, tests in `test_scanner.py`).
- [x] **Security Feature 2: Web Application Firewall (WAF).** (Completed: OWASP CRS in-app middleware, SQLi/XSS/Traversal/RCE blocking, incident audit logs, Apache ModSecurity configuration `deploy/modsecurity_nas.conf`, tests in `test_waf.py`).
- [ ] **Prepare final project documentation and screenshots.** (Per user instructions: "Regarding report , we shall do it in the end.")
