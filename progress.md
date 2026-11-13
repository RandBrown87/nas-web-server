# Project 2: Linux NAS Web Server - Progress Tracker

**Document Reference**: Project 2: Linux Web-Server (Building a Web Server for NAS Servers)  
**Last Updated**: November 2026  
**Overall Completion**: **100% Complete (All Core & Security Rubrics Met)**

---

## 1. Executive Summary

The Linux NAS Web Server project is fully implemented, hardened, and verified with an automated test suite (27/27 tests passing). The platform includes a Flask backend, MySQL relational database, responsive Bootstrap 5 dashboard, and two enterprise-grade security features (ClamAV Malware Protection Gateway and Web Application Firewall).

### Completed Milestone Highlights:
1.  **File & Folder Renaming**: Secure API (`POST /api/rename`) with traversal protection, ownership verification, recursive database metadata updating, and UI rename modals.
2.  **User Account Modification & Roles**: Admin API (`PUT /api/users/<id>`) and UI modal for updating usernames, passwords, and roles (`admin`, `user`, `editor`, `readonly`).
3.  **Inline File Viewer & Editor**: Monospace browser text editor with role-based editing permissions (`GET/POST /api/file/content`).
4.  **Automated Scheduled Backups**: Full `.tar.gz` archives containing all storage files, complete MySQL relational database dumps (`nas_db_dump.sql`), and system configuration JSON. Supports background scheduler (hourly/daily/weekly) and full system restoration.
5.  **Malware Protection Gateway (ClamAV)**: Upload quarantine pipeline scanning files with ClamAV daemon/CLI and heuristic analysis, blocking infected files, threat logging, quarantine management, and on-demand storage scanning.
6.  **Web Application Firewall (WAF)**: Dual-layer OWASP CRS WAF inspecting queries, headers, and form/JSON bodies for SQL Injection, XSS, Path Traversal, and RCE, backed by Apache ModSecurity configuration.
7.  **Linux Production Deployment**: Production Apache VirtualHost configuration (`deploy/nas_apache.conf`), Systemd service file (`deploy/nas.service`), UFW firewall setup script (`deploy/setup_server.sh`), cron backup script (`deploy/nas_backup_cron`), and a comprehensive port forwarding guide (`deploy/PORT_FORWARDING_GUIDE.md`).

---

## 2. Requirements & Objectives Audit

### Objective 1: File Management
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Upload files** |  Done | Staged via quarantine pipeline and scanned by ClamAV before placement. |
| **Download files** |  Done | Handled via `/api/download` with private file access enforcement. |
| **Delete files** |  Done | Handled via `/api/delete` with owner/admin authorization. |
| **Create folders** |  Done | Handled via `/api/mkdir` with privacy support. |
| **Delete folders** |  Done | Handled via `/api/delete` with recursive removal and DB cleanup. |
| **Rename files & folders** |  Done | Handled via `/api/rename` with traversal guards and DB cascade. |
| **Edit text files** |  Done | Built-in web editor via `/api/file/content` with role permissions. |
| **File privacy & uploader tracking** |  Done | Badges and privacy toggles restricted to file owners. |

---

### Objective 2: User Management
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Create user accounts** |  Done | Supported via Admin modal (`POST /api/users`) and public (`/register`). |
| **Delete user accounts** |  Done | Supported via Admin interface (`DELETE /api/users/<id>`). |
| **Modify user accounts** |  Done | Admin modal and `PUT /api/users/<id>` (username, password, role). |
| **Assign user roles/permissions** |  Done | 4 Roles: Admin (Full), User (Read/Write/Edit), Editor (Read/Edit), ReadOnly (Read). |

---

### Objective 3: System Monitoring
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Monitor disk usage** |  Done | Real-time disk storage gauge and GB calculation via `psutil`. |
| **Monitor CPU usage** |  Done | Real-time CPU percentage graph/bar via `psutil`. |
| **Monitor RAM usage** |  Done | Real-time RAM used / total GB and percentage. |
| **Monitor system logs** |  Done | Live log reader via `journalctl -n 15` on Linux (with fallback). |

---

### Objective 4: Backup and Restore
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Create backup archives** |  Done | On-demand `.tar.gz` archive creation via `/api/backup`. |
| **Restore files from archive** |  Done | Full archive extraction and restore via `/api/restore`. |
| **Schedule automatic backups** |  Done | Background scheduler thread + Linux cron script supporting hourly/daily/weekly. |
| **Backup system configurations** |  Done | Full MySQL relational database dump (`nas_db_dump.sql`) + `system_config.json`. |
| **Restore system configurations** |  Done | Restores database tables, permissions, users, and file metadata on restore. |

---

### Objective 5: Advanced Security Features
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Malware Protection Gateway** |  Done | ClamAV integration, quarantine staging folder, threat inspection, live statistics. |
| **EICAR Signature Detection** |  Done | Intercepts standard antivirus test strings and blocks infected uploads. |
| **On-Demand Storage Antivirus Scan** |  Done | Scans entire NAS disk storage recursively from the Admin dashboard. |
| **Web Application Firewall (WAF)** |  Done | In-app OWASP CRS inspection blocking SQLi, XSS, Path Traversal, and RCE. |
| **ModSecurity CRS Integration** |  Done | Apache configuration in `deploy/modsecurity_nas.conf`. |
| **Security Audit Logs** |  Done | Dedicated `security_scans` and `waf_logs` tables with UI incident inspection. |

---

## 3. Tasks Breakdown (Infrastructure & Setup)

### Task 1: Set up the Linux Server
-  **MySQL Database**: Initialized with tables (`roles`, `users`, `file_metadata`, `backups`, `backup_schedules`, `security_scans`, `waf_logs`).
-  **Python Environment**: Dependencies in `requirements.txt` (`flask`, `mysql-connector-python`, `psutil`, `werkzeug`, `gunicorn`).
-  **Apache / Production WSGI**: Production VirtualHost proxy in `deploy/nas_apache.conf` and Systemd unit in `deploy/nas.service`.
-  **Firewall & OS Permissions**: Hardened UFW configuration (`ufw allow 80, 443, 5050, 22`) and Linux permissions script (`deploy/setup_server.sh`).

### Task 2: Develop the Web Interface
-  **HTML / CSS / JavaScript**: Responsive dashboard with Bootstrap 5, file manager, system gauges, user administration, backup scheduler, and security center.
-  **Backend Blueprints**: Modular architecture (`auth`, `files`, `system`, `users`, `backup`, `security`, `waf`).

### Task 3: Configure Port Forwarding
-  **Router Port Forwarding**: Detailed guide in `deploy/PORT_FORWARDING_GUIDE.md` covering WAN port forwarding, DHCP reservations, DDNS setup, and Zero-Trust tunnel options.

### Task 4: Implement User Access Control
-  **Roles & Access Control**: Enforced across all endpoints with `@login_required`, `@admin_required`, and role flags.

---

## 4. Verification & Automated Test Suite

All 27 automated unit and integration tests passing:
- `tests/test_rename.py`: 4 tests (File rename, folder rename, traversal blocking, permission enforcement)
- `tests/test_users.py`: 4 tests (Roles retrieval, user creation/modification, admin demotion safeguard, unauthorized blocks)
- `tests/test_file_editor.py`: 4 tests (Admin edit, editor edit, readonly block, traversal block)
- `tests/test_backup.py`: 4 tests (Database dump, full archive backup & restore, schedule API, timing calculations)
- `tests/test_scanner.py`: 5 tests (Clean scan, EICAR malware block, clean upload, infected upload quarantine, security stats API)
- `tests/test_waf.py`: 6 tests (SQLi block, XSS block, Path traversal block, Scanner block, legitimate requests, WAF logging API)
