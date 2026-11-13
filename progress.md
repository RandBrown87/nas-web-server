# Project 2: Linux NAS Web Server - Progress Tracker

**Document Reference**: Project 2: Linux Web-Server (Building a Web Server for NAS Servers)  
**Last Updated**: November 2026  
**Overall Completion Estimate**: **~75% - 80% Complete**

---

## 1. Executive Summary

The core application architecture, database layer, authentication system, and frontend dashboard are functional and running. You have a working Flask web server backed by MySQL, supporting real-time system monitoring, file uploading/downloading/deleting, directory traversal protection, user roles, self-registration, and manual archive backups.

To achieve 100% completion according to the project specifications, several specific features and deployment steps remain:
1. **File/Folder Renaming** (UI & API).
2. **Modifying Existing User Accounts & Roles** (Admin UI & API).
3. **Automated / Scheduled Backups** (cron job or background scheduler).
4. **Linux Deployment, Apache/WSGI service, & Firewall Setup** (migrating from local dev to a Linux server).
5. **Router Port Forwarding** (remote access configuration).

---

## 2. Requirements & Objectives Audit

### Objective 1: File Management
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Upload files** |  Done | Implemented via `/api/upload` with directory traversal protection. |
| **Download files** |  Done | Implemented via `/api/download` with ownership/privacy checks. |
| **Delete files** |  Done | Implemented via `/api/delete` with owner/admin authorization. |
| **Create folders** |  Done | Implemented via `/api/mkdir`. |
| **Delete folders** |  Done | Implemented via `/api/delete` using recursive folder removal. |
| **Rename files & folders** | ❌ **Pending** | Needs a `/api/rename` route and UI action in the file table. |
| *Bonus: File privacy & uploader tracking* |  Done | Implemented uploader badges and user-level private files. |

---

### Objective 2: User Management
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Create user accounts** |  Done | Supported via Admin modal (`POST /api/users`) and public (`/register`). |
| **Delete user accounts** |  Done | Supported via Admin interface (`DELETE /api/users/<id>`). |
| **Assign user roles/permissions** |  Done | Role-based system (`admin`, `user`, `readonly`) with DB permission flags. |
| **Modify user accounts** | ❌ **Pending** | Currently no endpoint or UI modal to edit an existing user's username, password, or role. |

---

### Objective 3: System Monitoring
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Monitor disk usage** |  Done | Real-time disk storage gauge and GB calculation via `psutil`. |
| **Monitor CPU usage** |  Done | Real-time CPU percentage graph/bar via `psutil`. |
| **Monitor RAM usage** |  Done | Real-time RAM used / total GB and percentage. |
| **Monitor system logs** |  Done | Live log reader via `journalctl -n 15` on Linux (with host fallback). |

---

### Objective 4: Backup and Restore
| Requirement | Status | Implementation Details |
| :--- | :---: | :--- |
| **Create backup archives** |  Done | On-demand `.tar.gz` archive creation via `/api/backup`. |
| **Restore files from archive** |  Done | Extraction and restore utility via `/api/restore`. |
| **Schedule automatic backups** | ❌ **Pending** | Needs scheduled automatic backup triggers (e.g., daily cron job or APScheduler). |
| **Backup system configurations** | ⚠️ **Partial** | Currently backs up `/storage` directory; could include database dumps (`mysqldump`). |

---

## 3. Tasks Breakdown (Infrastructure & Setup)

### Task 1: Set up the Linux Server
-  **MySQL Database**: Configured and initialized with tables (`roles`, `users`, `file_metadata`, `backups`).
-  **Python Environment**: Virtual environment created with dependencies (`flask`, `mysql-connector-python`, `psutil`, `werkzeug`).
- ❌ **Apache / Production WSGI**: Currently running on Flask development server (`run.py`); needs deployment on Apache (`mod_wsgi` / reverse proxy) or Gunicorn + systemd service on Linux.
- ❌ **Firewall & OS Permissions**: Configuring `ufw` (Uncomplicated Firewall) on Linux and filesystem permissions (`chmod`/`chown` on `/srv/nas_storage`).

### Task 2: Develop the Web Interface
-  **HTML / CSS / JavaScript**: Modern dashboard layout with Bootstrap 5, responsive pills navigation, AJAX stats polling.
-  **Backend Scripts**: Modular Flask blueprints (`auth`, `files`, `system`, `users`, `backup`).
-  **MySQL Integration**: Fully integrated with connection pooling, buffered cursors, and relational constraints.

### Task 3: Configure Port Forwarding
- ❌ **Router Configuration**: External port forwarding rule (`External Port 5050 -> Internal NAS IP:5050`) or network tunnel (Tailscale / Cloudflare Tunnel) to enable access outside home network.

### Task 4: Implement User Access Control
-  **Roles & Permissions**: Admin, User (Read/Write), ReadOnly enforced across all routes.
-  **Authentication & Security**: Werkzeug password hashing with `pbkdf2:sha256`, session authentication, protected views (`@login_required`, `@admin_required`).

---

## 4. What Is Left to Be Done (Action Items)

### High Priority Code Features (To reach 100% of software rubric):
1. **File & Folder Renaming**:
   - Add backend endpoint: `POST /api/rename` taking `{ "old_path": "...", "new_name": "..." }`.
   - Update `file_metadata` path and filename on rename.
   - Add a "Rename" button / modal in the dashboard file table.
2. **Modify Existing User Accounts**:
   - Add backend endpoint: `PUT /api/users/<int:user_id>` to update user role, username, or reset password.
   - Add an "Edit User" modal in the Admin Users tab.
3. **Scheduled Automatic Backups**:
   - Implement scheduled backup execution (e.g., hourly/daily cron job or background Python timer).
   - Add UI controls in the Backups tab to set backup frequency (e.g. Daily / Weekly).
   - Optionally add a database dump (`nas_db.sql`) into the backup tarball to cover "system configurations".

### Deployment & Submission Items:
4. **Linux Production Service Setup**:
   - If submitting on a Linux VM: deploy with Apache reverse proxy or Gunicorn systemd service (`/etc/systemd/system/nas.service`).
   - Configure Linux firewall: `sudo ufw allow 5050/tcp` (or port 80/443).
5. **Port Forwarding Documentation / Setup**:
   - Configure home router port forwarding or document the configuration steps and verification.
