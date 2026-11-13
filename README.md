# Linux NAS Web Server

Modular web-based interface for managing and monitoring a Network Attached Storage (NAS) server running on Linux.

## Features
- **File Management**: Upload, download, delete files, and create directories with directory traversal protection.
- **System Monitoring**: Real-time CPU, RAM, and Disk metrics plus recent system logs.
- **User Management**: Admin interface to create and manage user roles (Admin, User, Read-Only).
- **Backup & Restore**: Create compressed `.tar.gz` storage archives and restore them.
- **Security**: Password hashing via Werkzeug, session authentication, and role authorization.

## Quick Start (VM / Linux)
1. **Initialize Database**:
   ```bash
   sudo mysql < sql/schema.sql
   ```
2. **Setup Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Run Server**:
   ```bash
   python3 run.py
   ```
4. Access via browser at `http://<SERVER_IP>:5050` (or `PORT=8080 python3 run.py`; Default login: `admin` / `AdminPass123!`).
