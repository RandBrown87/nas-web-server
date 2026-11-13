let currentPath = '';

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

async function fetchFiles() {
    const res = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
    const data = await res.json();
    document.getElementById('currentPathLabel').textContent = currentPath || 'root';
    const tbody = document.getElementById('fileTableBody');
    tbody.innerHTML = '';
    
    if (!data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4"><i class="bi bi-inbox fs-3 d-block mb-1"></i>No files found in this directory.</td></tr>';
        return;
    }

    data.items.forEach(item => {
        const tr = document.createElement('tr');
        const icon = item.is_dir ? '<i class="bi bi-folder-fill text-warning"></i>' : '<i class="bi bi-file-earmark text-secondary"></i>';
        const safeName = escapeHtml(item.name);
        const nameHtml = item.is_dir 
            ? `<a href="#" onclick="enterFolder('${encodeURIComponent(item.name)}')" class="text-decoration-none fw-bold">${safeName}</a>`
            : safeName;
        const sizeText = item.size !== null ? (item.size / 1024).toFixed(1) + ' KB' : '-';
        
        const uploaderHtml = `<span class="badge bg-light text-dark border"><i class="bi bi-person-fill text-primary"></i> ${escapeHtml(item.uploader || 'System')}</span>`;
        
        const visibilityHtml = item.is_private 
            ? `<span class="badge bg-danger" title="Hidden: Only you and admins can see this file"><i class="bi bi-lock-fill"></i> Private</span>`
            : `<span class="badge bg-light text-muted border" title="Visible to all users"><i class="bi bi-globe"></i> Public</span>`;
        
        let toggleVisibilityBtn = '';
        if (item.can_toggle) {
            const toggleIcon = item.is_private ? 'bi-unlock' : 'bi-lock';
            const toggleTitle = item.is_private ? 'Make Public' : 'Make Private (Hide)';
            const btnClass = item.is_private ? 'btn-outline-warning' : 'btn-outline-secondary';
            toggleVisibilityBtn = `<button class="btn btn-sm ${btnClass}" onclick="toggleVisibility('${encodeURIComponent(item.name)}')" title="${toggleTitle}"><i class="bi ${toggleIcon}"></i></button>`;
        }

        const filePath = currentPath ? currentPath + '/' + item.name : item.name;

        tr.innerHTML = `
            <td>${icon} ${nameHtml}</td>
            <td>${item.is_dir ? 'Directory' : 'File'}</td>
            <td>${sizeText}</td>
            <td>${uploaderHtml}</td>
            <td>${visibilityHtml}</td>
            <td>${item.modified}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    ${!item.is_dir ? `<a href="/api/download?path=${encodeURIComponent(filePath)}" class="btn btn-sm btn-outline-success" title="Download"><i class="bi bi-download"></i></a>` : ''}
                    ${toggleVisibilityBtn}
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteItem('${encodeURIComponent(item.name)}')" title="Delete"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function enterFolder(encodedName) {
    const name = decodeURIComponent(encodedName);
    currentPath = currentPath ? currentPath + '/' + name : name;
    fetchFiles();
}

function navigateUp() {
    if (!currentPath) return;
    const parts = currentPath.split('/');
    parts.pop();
    currentPath = parts.join('/');
    fetchFiles();
}

async function uploadFile() {
    const input = document.getElementById('fileInput');
    const privateCheck = document.getElementById('privateCheck');
    if (!input.files[0]) return alert("Select a file first");
    
    const fd = new FormData();
    fd.append('file', input.files[0]);
    fd.append('path', currentPath);
    if (privateCheck && privateCheck.checked) {
        fd.append('is_private', 'true');
    }
    
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (res.ok) { 
        input.value = ''; 
        if (privateCheck) privateCheck.checked = false;
        fetchFiles(); 
    } else {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Upload failed");
    }
}

async function toggleVisibility(encodedName) {
    const name = decodeURIComponent(encodedName);
    const target = currentPath ? currentPath + '/' + name : name;
    const res = await fetch('/api/files/visibility', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path: target })
    });
    if (res.ok) {
        fetchFiles();
    } else {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Failed to update visibility");
    }
}

async function createFolder() {
    const name = prompt("Enter folder name:");
    if (!name) return;
    const isPrivate = confirm("Would you like this folder to be Private (only visible to you)?");
    await fetch('/api/mkdir', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path: currentPath, folder_name: name, is_private: isPrivate })
    });
    fetchFiles();
}

async function deleteItem(encodedName) {
    const name = decodeURIComponent(encodedName);
    if (!confirm(`Delete ${name}?`)) return;
    const target = currentPath ? currentPath + '/' + name : name;
    const res = await fetch('/api/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path: target })
    });
    if (res.ok) {
        fetchFiles();
    } else {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Delete failed");
    }
}

async function fetchStats() {
    const res = await fetch('/api/system');
    const data = await res.json();
    document.getElementById('cpuPercent').textContent = data.cpu_percent + '%';
    document.getElementById('cpuBar').style.width = data.cpu_percent + '%';
    document.getElementById('ramText').textContent = `${data.ram_used_gb} / ${data.ram_total_gb} GB (${data.ram_percent}%)`;
    document.getElementById('ramBar').style.width = data.ram_percent + '%';
    document.getElementById('diskText').textContent = `${data.disk_used_gb} / ${data.disk_total_gb} GB (${data.disk_percent}%)`;
    document.getElementById('diskBar').style.width = data.disk_percent + '%';
    document.getElementById('logBox').textContent = data.logs.join('\n');
}

async function fetchUsers() {
    const res = await fetch('/api/users');
    const data = await res.json();
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '';
    data.users.forEach(u => {
        tbody.innerHTML += `<tr><td>${u.id}</td><td>${u.username}</td><td><span class="badge bg-secondary">${u.role_name}</span></td><td>${u.created_at}</td><td><button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id})">Delete</button></td></tr>`;
    });
}

async function addUser() {
    const username = document.getElementById('newUsername').value;
    const password = document.getElementById('newPassword').value;
    const role_id = document.getElementById('newRole').value;
    const res = await fetch('/api/users', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ username, password, role_id })
    });
    if (res.ok) { bootstrap.Modal.getInstance(document.getElementById('addUserModal')).hide(); fetchUsers(); }
    else alert("Error adding user");
}

async function deleteUser(id) {
    if (!confirm("Delete this user?")) return;
    const res = await fetch(`/api/users/${id}`, { method: 'DELETE' });
    if (res.ok) fetchUsers(); else alert("Error deleting user");
}

async function fetchBackups() {
    const res = await fetch('/api/backup');
    const data = await res.json();
    const tbody = document.getElementById('backupTableBody');
    tbody.innerHTML = '';
    data.backups.forEach(b => {
        tbody.innerHTML += `<tr><td>${b.backup_name}</td><td>${b.created_at}</td><td><button class="btn btn-sm btn-warning" onclick="restoreBackup('${b.backup_name}')"><i class="bi bi-arrow-counterclockwise"></i> Restore</button></td></tr>`;
    });
}

async function createBackup() {
    alert("Running backup...");
    const res = await fetch('/api/backup', { method: 'POST' });
    if (res.ok) { alert("Backup complete!"); fetchBackups(); } else alert("Backup failed");
}

async function restoreBackup(name) {
    if (!confirm(`Restore from ${name}?`)) return;
    const res = await fetch('/api/restore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ backup_name: name })
    });
    if (res.ok) { alert("Restored!"); fetchFiles(); } else alert("Restore failed");
}

fetchFiles();
setInterval(fetchStats, 5000);
