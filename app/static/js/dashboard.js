// ==============================================================================
// LINUX NAS PORTAL - INNOVATIVE DASHBOARD & UNIVERSAL MEDIA SUITE
// Features: Universal Media Previewer (Images, Video, Audio, PDF, Code Editor),
// Dark/Light Theme Engine, Live CPU Sparkline, Storage Spectrum, Drag & Drop Upload
// ==============================================================================

let currentPath = '';
let cachedFiles = [];
let cachedUsers = [];
let toastInstance = null;
let currentPreviewIndex = -1;
let currentImageZoom = 1.0;
let cpuHistory = [10, 15, 12, 18, 22, 19, 25, 20, 24, 18, 22, 28, 24, 20, 18];

// Helper: Escape HTML strings for XSS safety
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// 1. Modern Toast Notification Utility
function showToast(title, message, type = 'info') {
    const toastEl = document.getElementById('nasToast');
    if (!toastEl) {
        if (type === 'danger' || type === 'error') alert(message);
        return;
    }
    const iconEl = document.getElementById('nasToastIcon');
    const titleEl = document.getElementById('nasToastTitle');
    const msgEl = document.getElementById('nasToastMessage');

    titleEl.textContent = title;
    msgEl.textContent = message;

    if (type === 'success') {
        iconEl.className = 'bi bi-check-circle-fill fs-5 text-success';
    } else if (type === 'danger' || type === 'error') {
        iconEl.className = 'bi bi-exclamation-triangle-fill fs-5 text-danger';
    } else if (type === 'warning') {
        iconEl.className = 'bi bi-shield-exclamation fs-5 text-warning';
    } else {
        iconEl.className = 'bi bi-info-circle-fill fs-5 text-primary';
    }

    if (!toastInstance) {
        toastInstance = new bootstrap.Toast(toastEl, { delay: 4000 });
    }
    toastInstance.show();
}

// 2. Dark / Light Theme Engine
function initTheme() {
    const savedTheme = localStorage.getItem('nas-theme') || 'light';
    applyTheme(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('nas-theme', theme);
    const icon = document.getElementById('themeToggleIcon');
    if (icon) {
        icon.className = theme === 'dark' ? 'bi bi-sun-fill text-warning' : 'bi bi-moon-stars-fill';
    }
}

// 3. File Type Icon Stylizer
function getFileIcon(name, isDir) {
    if (isDir) {
        return '<span class="file-icon-box file-icon-dir"><i class="bi bi-folder-fill"></i></span>';
    }
    const lower = name.toLowerCase();
    if (lower.endsWith('.pdf')) {
        return '<span class="file-icon-box file-icon-pdf"><i class="bi bi-file-earmark-pdf-fill"></i></span>';
    } else if (/\.(jpg|jpeg|png|gif|svg|webp|bmp|ico)$/.test(lower)) {
        return '<span class="file-icon-box file-icon-img"><i class="bi bi-file-earmark-image-fill"></i></span>';
    } else if (/\.(mp4|webm|ogg|mov|mkv|m4v)$/.test(lower)) {
        return '<span class="file-icon-box" style="background: rgba(6, 182, 212, 0.15); color: #06b6d4;"><i class="bi bi-file-earmark-play-fill"></i></span>';
    } else if (/\.(mp3|wav|ogg|m4a|aac|flac)$/.test(lower)) {
        return '<span class="file-icon-box" style="background: rgba(147, 51, 234, 0.15); color: #9333ea;"><i class="bi bi-file-earmark-music-fill"></i></span>';
    } else if (/\.(py|js|html|css|json|sh|sql|ts|php|c|cpp|h|md|log|csv|yml|yaml|env|conf|ini)$/.test(lower)) {
        return '<span class="file-icon-box file-icon-code"><i class="bi bi-file-earmark-code-fill"></i></span>';
    } else if (/\.(tar|gz|zip|bz2|xz|rar|7z)$/.test(lower)) {
        return '<span class="file-icon-box file-icon-archive"><i class="bi bi-file-earmark-zip-fill"></i></span>';
    } else {
        return '<span class="file-icon-box file-icon-txt"><i class="bi bi-file-earmark-text-fill"></i></span>';
    }
}

// 4. Clickable Interactive Breadcrumbs
function renderBreadcrumbs(path) {
    const label = document.getElementById('currentPathLabel');
    if (!path) {
        label.innerHTML = '<span class="text-primary fw-bold">root</span>';
        return;
    }
    const parts = path.split('/').filter(Boolean);
    let html = `<a href="#" onclick="navigateToPath('')" class="breadcrumb-crumb">root</a>`;
    let accum = '';
    parts.forEach((p, idx) => {
        accum = accum ? accum + '/' + p : p;
        html += `<span class="breadcrumb-sep">/</span>`;
        if (idx === parts.length - 1) {
            html += `<span class="fw-bold text-dark">${escapeHtml(p)}</span>`;
        } else {
            html += `<a href="#" onclick="navigateToPath('${encodeURIComponent(accum)}')" class="breadcrumb-crumb">${escapeHtml(p)}</a>`;
        }
    });
    label.innerHTML = html;
}

function navigateToPath(target) {
    currentPath = decodeURIComponent(target);
    fetchFiles();
}

// 5. Files & Directory Operations
async function fetchFiles() {
    try {
        const res = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
        const data = await res.json();
        renderBreadcrumbs(currentPath);
        cachedFiles = data.items || [];
        renderFileList(cachedFiles);
        updateStorageSpectrum(cachedFiles);
    } catch (err) {
        console.error("Fetch files error:", err);
    }
}

function renderFileList(items) {
    const tbody = document.getElementById('fileTableBody');
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-5">
                    <i class="bi bi-folder2-open fs-1 d-block mb-2 text-secondary opacity-50"></i>
                    <div class="fw-semibold">No files found in this directory.</div>
                    <small class="text-muted">Use the Upload or New Folder buttons above to add files.</small>
                </td>
            </tr>`;
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');
        const iconHtml = getFileIcon(item.name, item.is_dir);
        const safeName = escapeHtml(item.name);
        const nameHtml = item.is_dir
            ? `<a href="#" onclick="enterFolder('${encodeURIComponent(item.name)}')" class="text-decoration-none fw-bold text-primary">${safeName}</a>`
            : `<span class="fw-semibold text-dark file-row-name" role="button" onclick="openFilePreview('${encodeURIComponent(item.name)}')">${safeName}</span>`;

        let sizeText = '-';
        if (item.size !== null) {
            if (item.size < 1024) sizeText = item.size + ' B';
            else if (item.size < 1024 * 1024) sizeText = (item.size / 1024).toFixed(1) + ' KB';
            else sizeText = (item.size / (1024 * 1024)).toFixed(2) + ' MB';
        }

        const uploaderHtml = `<span class="badge bg-light text-dark border px-2 py-1"><i class="bi bi-person-fill text-primary me-1"></i>${escapeHtml(item.uploader || 'System')}</span>`;

        const visibilityHtml = item.is_private
            ? `<span class="badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1" title="Hidden: Visible only to your account"><i class="bi bi-lock-fill"></i> Private</span>`
            : `<span class="badge bg-light text-muted border px-2 py-1" title="Visible to all users"><i class="bi bi-globe me-1"></i>Public</span>`;

        let toggleVisibilityBtn = '';
        if (item.can_toggle) {
            const toggleIcon = item.is_private ? 'bi-unlock' : 'bi-lock';
            const toggleTitle = item.is_private ? 'Make Public' : 'Make Private';
            const btnClass = item.is_private ? 'btn-outline-warning' : 'btn-outline-secondary';
            toggleVisibilityBtn = `<button class="btn btn-sm ${btnClass}" onclick="toggleVisibility('${encodeURIComponent(item.name)}')" title="${toggleTitle}"><i class="bi ${toggleIcon}"></i></button>`;
        }

        const filePath = currentPath ? currentPath + '/' + item.name : item.name;

        tr.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    ${iconHtml}
                    <div class="text-truncate" style="max-width: 320px;">${nameHtml}</div>
                </div>
            </td>
            <td><span class="badge bg-light text-secondary border">${item.is_dir ? 'Directory' : 'File'}</span></td>
            <td><span class="font-monospace small">${sizeText}</span></td>
            <td>${uploaderHtml}</td>
            <td>${visibilityHtml}</td>
            <td><span class="small text-muted font-monospace">${item.modified}</span></td>
            <td class="text-end">
                <div class="btn-group btn-group-sm shadow-sm" style="border-radius: 8px; overflow: hidden;">
                    ${!item.is_dir ? `<button class="btn btn-outline-info" onclick="openFilePreview('${encodeURIComponent(item.name)}')" title="Preview / View / Edit"><i class="bi bi-eye"></i></button>` : ''}
                    ${!item.is_dir ? `<a href="/api/download?path=${encodeURIComponent(filePath)}" class="btn btn-outline-success" title="Download File"><i class="bi bi-download"></i></a>` : ''}
                    <button class="btn btn-outline-primary" onclick="openRenameModal('${encodeURIComponent(item.name)}')" title="Rename"><i class="bi bi-pencil"></i></button>
                    ${toggleVisibilityBtn}
                    <button class="btn btn-outline-danger" onclick="deleteItem('${encodeURIComponent(item.name)}')" title="Delete"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 6. Instant Directory Search & Category Filters
function filterFiles(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
        renderFileList(cachedFiles);
        return;
    }
    const filtered = cachedFiles.filter(item => item.name.toLowerCase().includes(q));
    renderFileList(filtered);
}

function filterByExtensionGroup(group) {
    let exts = [];
    if (group === 'images') exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico'];
    else if (group === 'docs') exts = ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt'];
    else if (group === 'videos') exts = ['.mp4', '.webm', '.ogg', '.mov', '.mkv', '.m4v'];
    else if (group === 'code') exts = ['.py', '.js', '.ts', '.html', '.css', '.json', '.sh', '.sql', '.yml', '.yaml', '.php', '.c', '.cpp', '.h'];
    else if (group === 'archives') exts = ['.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z'];

    const filtered = cachedFiles.filter(item => {
        if (item.is_dir) return false;
        const lower = item.name.toLowerCase();
        return exts.some(e => lower.endsWith(e));
    });
    renderFileList(filtered);
}

// 7. Directory Storage Breakdown Spectrum
function updateStorageSpectrum(items) {
    let imgBytes = 0, docBytes = 0, vidBytes = 0, codeBytes = 0, archBytes = 0, otherBytes = 0;
    let imgCount = 0, docCount = 0, vidCount = 0, codeCount = 0, archCount = 0;

    items.forEach(item => {
        if (item.is_dir) return;
        const lower = item.name.toLowerCase();
        const size = item.size || 0;

        if (/\.(jpg|jpeg|png|gif|svg|webp|bmp|ico)$/.test(lower)) {
            imgBytes += size; imgCount++;
        } else if (/\.(pdf|doc|docx|txt|md|rtf|odt)$/.test(lower)) {
            docBytes += size; docCount++;
        } else if (/\.(mp4|webm|ogg|mov|mkv|m4v)$/.test(lower)) {
            vidBytes += size; vidCount++;
        } else if (/\.(py|js|ts|html|css|json|sh|sql|yml|yaml|php|c|cpp|h)$/.test(lower)) {
            codeBytes += size; codeCount++;
        } else if (/\.(zip|tar|gz|bz2|xz|rar|7z)$/.test(lower)) {
            archBytes += size; archCount++;
        } else {
            otherBytes += size;
        }
    });

    const total = imgBytes + docBytes + vidBytes + codeBytes + archBytes + otherBytes;

    if (total > 0) {
        document.getElementById('specImg').style.width = ((imgBytes / total) * 100).toFixed(1) + '%';
        document.getElementById('specDoc').style.width = ((docBytes / total) * 100).toFixed(1) + '%';
        document.getElementById('specVid').style.width = ((vidBytes / total) * 100).toFixed(1) + '%';
        document.getElementById('specCode').style.width = ((codeBytes / total) * 100).toFixed(1) + '%';
        document.getElementById('specArch').style.width = ((archBytes / total) * 100).toFixed(1) + '%';
        document.getElementById('specOther').style.width = ((otherBytes / total) * 100).toFixed(1) + '%';

        let totalMb = (total / (1024 * 1024)).toFixed(2);
        document.getElementById('spectrumStatsLabel').textContent = `${totalMb} MB in ${items.length} items`;
    } else {
        document.getElementById('specImg').style.width = '0%';
        document.getElementById('specDoc').style.width = '0%';
        document.getElementById('specVid').style.width = '0%';
        document.getElementById('specCode').style.width = '0%';
        document.getElementById('specArch').style.width = '0%';
        document.getElementById('specOther').style.width = '0%';
        document.getElementById('spectrumStatsLabel').textContent = 'Directory is empty';
    }

    document.getElementById('specCountImg').textContent = imgCount;
    document.getElementById('specCountDoc').textContent = docCount;
    document.getElementById('specCountVid').textContent = vidCount;
    document.getElementById('specCountCode').textContent = codeCount;
    document.getElementById('specCountArch').textContent = archCount;
    document.getElementById('specCountAll').textContent = items.length;
}

function enterFolder(encodedName) {
    const name = decodeURIComponent(encodedName);
    currentPath = currentPath ? currentPath + '/' + name : name;
    const searchInput = document.getElementById('fileSearchInput');
    if (searchInput) searchInput.value = '';
    fetchFiles();
}

function navigateUp() {
    if (!currentPath) return;
    const parts = currentPath.split('/');
    parts.pop();
    currentPath = parts.join('/');
    const searchInput = document.getElementById('fileSearchInput');
    if (searchInput) searchInput.value = '';
    fetchFiles();
}

async function uploadFile() {
    const input = document.getElementById('fileInput');
    const privateCheck = document.getElementById('privateCheck');
    if (!input.files[0]) {
        showToast("Upload Notice", "Please select a file to upload first.", "warning");
        return;
    }

    const fd = new FormData();
    fd.append('file', input.files[0]);
    fd.append('path', currentPath);
    if (privateCheck && privateCheck.checked) {
        fd.append('is_private', 'true');
    }

    showToast("Malware Gateway", "Quarantine scanning and uploading file...", "info");

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            input.value = '';
            if (privateCheck) privateCheck.checked = false;
            showToast("Upload Success", `File '${data.filename}' verified clean by ClamAV and stored.`, "success");
            fetchFiles();
        } else {
            showToast("Upload Blocked", data.error || "Upload rejected by gateway.", "danger");
        }
    } catch (err) {
        showToast("Upload Error", "Failed to communicate with upload server.", "danger");
    }
}

async function toggleVisibility(encodedName) {
    const name = decodeURIComponent(encodedName);
    const target = currentPath ? currentPath + '/' + name : name;
    try {
        const res = await fetch('/api/files/visibility', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: target })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Visibility Updated", `File visibility changed to: ${data.is_private ? 'Private' : 'Public'}`, "info");
            fetchFiles();
        } else {
            showToast("Permission Notice", data.error || "Failed to update visibility.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error while toggling visibility.", "danger");
    }
}

async function createFolder() {
    const name = prompt("Enter new folder name:");
    if (!name || !name.trim()) return;
    const isPrivate = confirm("Make this folder Private (visible only to your account)?");
    try {
        const res = await fetch('/api/mkdir', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: currentPath, folder_name: name.trim(), is_private: isPrivate })
        });
        if (res.ok) {
            showToast("Folder Created", `Folder '${name}' created successfully.`, "success");
            fetchFiles();
        } else {
            const data = await res.json().catch(() => ({}));
            showToast("Error", data.error || "Failed to create folder.", "danger");
        }
    } catch (err) {
        showToast("Error", "Communication error creating folder.", "danger");
    }
}

async function deleteItem(encodedName) {
    const name = decodeURIComponent(encodedName);
    if (!confirm(`Are you sure you want to permanently delete '${name}'?`)) return;
    const target = currentPath ? currentPath + '/' + name : name;

    try {
        const res = await fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: target })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Deleted", `'${name}' was removed.`, "info");
            fetchFiles();
        } else {
            showToast("Delete Blocked", data.error || "Delete operation failed.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error during deletion.", "danger");
    }
}

// ==============================================================================
// 8. UNIVERSAL FILE PREVIEWER & MULTIMEDIA SUITE (Images, Video, Audio, PDF, Text)
// ==============================================================================

// Direct compatibility alias for openFileEditor
function openFileEditor(encodedName) {
    openFilePreview(encodedName);
}

async function openFilePreview(encodedName) {
    const name = decodeURIComponent(encodedName);
    const target = currentPath ? currentPath + '/' + name : name;

    const modalEl = document.getElementById('fileEditorModal');
    if (!modalEl) return;
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    // Track index for Prev/Next navigation
    const fileOnlyItems = (cachedFiles || []).filter(f => !f.is_dir);
    currentPreviewIndex = fileOnlyItems.findIndex(f => f.name === name);

    updatePreviewNavButtons(fileOnlyItems);

    const pathInput = document.getElementById('editorFilePath');
    if (pathInput) pathInput.value = target;

    const nameEl = document.getElementById('editorFileName');
    if (nameEl) nameEl.textContent = name;

    const pathHint = document.getElementById('editorPathHint');
    if (pathHint) pathHint.textContent = '/' + target;

    const downloadBtn = document.getElementById('previewDownloadBtn');
    if (downloadBtn) downloadBtn.href = `/api/download?path=${encodeURIComponent(target)}`;

    const container = document.getElementById('previewMediaContainer');
    const zoomControls = document.getElementById('imageZoomControls');
    const saveBtn = document.getElementById('editorSaveBtn');
    const statusBadge = document.getElementById('editorStatusBadge');
    const metaDetails = document.getElementById('previewMetaDetails');
    const iconEl = document.getElementById('previewFileIcon');

    currentImageZoom = 1.0;
    if (zoomControls) zoomControls.style.display = 'none';
    if (saveBtn) saveBtn.style.display = 'none';
    if (statusBadge) {
        statusBadge.className = 'badge bg-secondary px-2 py-1 small';
        statusBadge.textContent = 'Preview';
    }

    // Determine file size and display
    const currentItem = fileOnlyItems.find(f => f.name === name);
    let sizeText = '-';
    if (currentItem && currentItem.size !== null && currentItem.size !== undefined) {
        if (currentItem.size < 1024) sizeText = currentItem.size + ' B';
        else if (currentItem.size < 1024 * 1024) sizeText = (currentItem.size / 1024).toFixed(1) + ' KB';
        else sizeText = (currentItem.size / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // Immediately open modal for instant visual feedback
    modal.show();

    const lower = name.toLowerCase();

    // 1. IMAGE PREVIEW
    if (/\.(jpg|jpeg|png|gif|svg|webp|bmp|ico)$/.test(lower)) {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-image text-purple"></i>';
        if (zoomControls) zoomControls.style.display = 'inline-flex';
        if (statusBadge) {
            statusBadge.className = 'badge bg-purple-subtle text-purple border border-purple-subtle px-2 py-1 small';
            statusBadge.textContent = 'Image Lightbox';
        }
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Image | Path: /${target}`;

        if (container) {
            container.innerHTML = `
                <div class="preview-img-container" id="imgContainer">
                    <img id="activePreviewImg" src="/api/preview?path=${encodeURIComponent(target)}" alt="${safeName(name)}" style="transform: scale(1);" onerror="this.onerror=null; this.parentElement.innerHTML='<div class=\\'text-center text-secondary py-5\\'><i class=\\'bi bi-file-earmark-x fs-1 text-warning d-block mb-3\\'></i><div>Unable to render image preview</div><small class=\\'text-muted\\'>File may be corrupted or in an unsupported format.</small></div>';">
                </div>`;
        }

    // 2. PDF VIEWER
    } else if (lower.endsWith('.pdf')) {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-pdf text-danger"></i>';
        if (statusBadge) {
            statusBadge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1 small';
            statusBadge.textContent = 'PDF Document';
        }
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Adobe PDF Document | In-browser Rendering`;

        if (container) {
            container.innerHTML = `
                <iframe src="/api/preview?path=${encodeURIComponent(target)}#toolbar=1" style="width: 100%; height: 75vh; border: none; border-radius: 8px;"></iframe>`;
        }

    // 3. VIDEO PLAYER
    } else if (/\.(mp4|webm|ogg|mov|mkv|m4v)$/.test(lower)) {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-play text-info"></i>';
        if (statusBadge) {
            statusBadge.className = 'badge bg-info-subtle text-info border border-info-subtle px-2 py-1 small';
            statusBadge.textContent = 'Cinema Video Player';
        }
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Video Stream | HTML5 Media Player`;

        if (container) {
            container.innerHTML = `
                <div class="w-100 p-3 d-flex flex-column align-items-center justify-content-center">
                    <video controls autoplay playsinline style="max-width: 100%; max-height: 72vh; border-radius: 8px; background: #000; box-shadow: 0 10px 30px rgba(0,0,0,0.6);">
                        <source src="/api/preview?path=${encodeURIComponent(target)}">
                        Your browser does not support HTML5 video preview.
                    </video>
                </div>`;
        }

    // 4. AUDIO PLAYER WITH WAVEFORM
    } else if (/\.(mp3|wav|ogg|m4a|aac|flac)$/.test(lower)) {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-music text-primary"></i>';
        if (statusBadge) {
            statusBadge.className = 'badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1 small';
            statusBadge.textContent = 'Audio Track';
        }
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Audio File | HTML5 Sound Engine`;

        if (container) {
            container.innerHTML = `
                <div class="w-100 p-5 d-flex flex-column align-items-center justify-content-center text-center">
                    <div class="audio-visualizer-bars">
                        <div class="audio-bar"></div><div class="audio-bar"></div><div class="audio-bar"></div>
                        <div class="audio-bar"></div><div class="audio-bar"></div><div class="audio-bar"></div>
                        <div class="audio-bar"></div><div class="audio-bar"></div>
                    </div>
                    <h5 class="text-white mb-3 fw-bold font-monospace">${escapeHtml(name)}</h5>
                    <audio controls autoplay style="width: 100%; max-width: 520px;">
                        <source src="/api/preview?path=${encodeURIComponent(target)}">
                        Your browser does not support HTML5 audio playback.
                    </audio>
                </div>`;
        }

    // 5. ARCHIVES & COMPRESSED PACKAGES
    } else if (/\.(zip|tar|gz|bz2|xz|rar|7z|iso|dmg|bin|exe)$/.test(lower)) {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-zip text-warning"></i>';
        if (statusBadge) {
            statusBadge.className = 'badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1 small';
            statusBadge.textContent = 'Archive';
        }
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Compressed Archive / Binary Package`;

        if (container) {
            container.innerHTML = `
                <div class="w-100 p-5 text-center d-flex flex-column align-items-center justify-content-center">
                    <div class="nas-stat-icon mb-3" style="width: 72px; height: 72px; font-size: 2.5rem; background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-radius: 20px;">
                        <i class="bi bi-file-earmark-zip"></i>
                    </div>
                    <h4 class="text-white fw-bold mb-2 font-monospace">${escapeHtml(name)}</h4>
                    <p class="text-secondary small mb-4">Direct preview is not applicable for binary archives. Click below to download and extract.</p>
                    <a href="/api/download?path=${encodeURIComponent(target)}" class="btn btn-warning px-4 py-2 fw-semibold shadow-sm">
                        <i class="bi bi-download me-2"></i> Download Archive (${sizeText})
                    </a>
                </div>`;
        }

    // 6. TEXT / CODE / CONFIG / MARKDOWN EDITOR
    } else {
        if (iconEl) iconEl.innerHTML = '<i class="bi bi-file-earmark-code text-success"></i>';
        if (metaDetails) metaDetails.textContent = `Size: ${sizeText} | Type: Plaintext / Code | Monospace Editor`;
        if (statusBadge) {
            statusBadge.className = 'badge bg-info-subtle text-info border border-info-subtle px-2 py-1 small';
            statusBadge.textContent = 'Loading...';
        }

        if (container) {
            container.innerHTML = `
                <div class="w-100 p-3">
                    <textarea id="fileEditorText" class="form-control font-monospace" rows="18" style="font-size: 0.88rem; tab-size: 4; background: #090d16; color: #38bdf8; border: 1px solid #1e293b; resize: vertical;" readonly>Loading file contents from NAS storage...</textarea>
                </div>`;
        }

        try {
            const res = await fetch(`/api/file/content?path=${encodeURIComponent(target)}`);
            const data = await res.json().catch(() => ({}));
            const textarea = document.getElementById('fileEditorText');

            if (!res.ok) {
                if (container) {
                    container.innerHTML = `
                        <div class="w-100 p-5 text-center d-flex flex-column align-items-center justify-content-center">
                            <div class="nas-stat-icon mb-3" style="width: 72px; height: 72px; font-size: 2.5rem; background: rgba(148, 163, 184, 0.15); color: #94a3b8; border-radius: 20px;">
                                <i class="bi bi-file-earmark-binary"></i>
                            </div>
                            <h4 class="text-white fw-bold mb-2 font-monospace">${escapeHtml(name)}</h4>
                            <p class="text-secondary small mb-4">${escapeHtml(data.error || 'This file format cannot be displayed as plain text.')}</p>
                            <a href="/api/download?path=${encodeURIComponent(target)}" class="btn btn-outline-light px-4 py-2 fw-semibold">
                                <i class="bi bi-download me-2"></i> Download File (${sizeText})
                            </a>
                        </div>`;
                }
                if (statusBadge) {
                    statusBadge.className = 'badge bg-secondary px-2 py-1 small';
                    statusBadge.textContent = 'Binary File';
                }
                return;
            }

            if (textarea) {
                textarea.value = data.content !== undefined ? data.content : '';
                if (data.can_edit) {
                    textarea.removeAttribute('readonly');
                    if (saveBtn) saveBtn.style.display = 'inline-flex';
                    if (statusBadge) {
                        statusBadge.className = 'badge bg-success px-2 py-1 small';
                        statusBadge.textContent = 'Editable';
                    }
                } else {
                    textarea.setAttribute('readonly', 'true');
                    if (saveBtn) saveBtn.style.display = 'none';
                    if (statusBadge) {
                        statusBadge.className = 'badge bg-secondary px-2 py-1 small';
                        statusBadge.textContent = 'Read Only';
                    }
                }
            }
        } catch (err) {
            const textarea = document.getElementById('fileEditorText');
            if (textarea) textarea.value = '[Error fetching file text from server]';
            if (statusBadge) {
                statusBadge.className = 'badge bg-danger px-2 py-1 small';
                statusBadge.textContent = 'Load Failed';
            }
        }
    }
}

function safeName(str) {
    return escapeHtml(str).replace(/"/g, '&quot;');
}

function updatePreviewNavButtons(fileItems) {
    const prevBtn = document.getElementById('previewPrevBtn');
    const nextBtn = document.getElementById('previewNextBtn');
    if (!prevBtn || !nextBtn) return;

    if (!fileItems || fileItems.length <= 1) {
        prevBtn.style.display = 'none';
        nextBtn.style.display = 'none';
        return;
    }
    prevBtn.style.display = 'flex';
    nextBtn.style.display = 'flex';

    if (currentPreviewIndex <= 0) {
        prevBtn.style.opacity = '0.25';
        prevBtn.disabled = true;
    } else {
        prevBtn.style.opacity = '1';
        prevBtn.disabled = false;
    }

    if (currentPreviewIndex >= fileItems.length - 1 || currentPreviewIndex === -1) {
        nextBtn.style.opacity = '0.25';
        nextBtn.disabled = true;
    } else {
        nextBtn.style.opacity = '1';
        nextBtn.disabled = false;
    }
}

function previewPrevFile() {
    const fileItems = (cachedFiles || []).filter(f => !f.is_dir);
    if (currentPreviewIndex > 0) {
        currentPreviewIndex--;
        openFilePreview(encodeURIComponent(fileItems[currentPreviewIndex].name));
    }
}

function previewNextFile() {
    const fileItems = (cachedFiles || []).filter(f => !f.is_dir);
    if (currentPreviewIndex < fileItems.length - 1 && currentPreviewIndex !== -1) {
        currentPreviewIndex++;
        openFilePreview(encodeURIComponent(fileItems[currentPreviewIndex].name));
    }
}

function zoomImage(factor) {
    const img = document.getElementById('activePreviewImg');
    if (!img) return;
    currentImageZoom = Math.max(0.2, Math.min(5.0, currentImageZoom * factor));
    img.style.transform = `scale(${currentImageZoom})`;
}

function resetZoomImage() {
    const img = document.getElementById('activePreviewImg');
    if (!img) return;
    currentImageZoom = 1.0;
    img.style.transform = 'scale(1)';
}

async function saveFileContent() {
    const pathInput = document.getElementById('editorFilePath');
    const path = pathInput ? pathInput.value : '';
    const textEl = document.getElementById('fileEditorText');
    const content = textEl ? textEl.value : '';

    if (!path) {
        showToast("Error", "No active file selected to save.", "danger");
        return;
    }

    try {
        const res = await fetch('/api/file/content', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: path, content: content })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("File Saved", "Changes written to storage successfully.", "success");
            const modalEl = document.getElementById('fileEditorModal');
            if (modalEl) {
                const modalInstance = bootstrap.Modal.getInstance(modalEl);
                if (modalInstance) modalInstance.hide();
            }
            fetchFiles();
        } else {
            showToast("Save Failed", data.error || "Failed to save file.", "danger");
        }
    } catch (err) {
        showToast("Error", "Network error saving file.", "danger");
    }
}

// 9. Rename Operations
function openRenameModal(encodedName) {
    const name = decodeURIComponent(encodedName);
    const target = currentPath ? currentPath + '/' + name : name;
    document.getElementById('renameOldPath').value = target;
    document.getElementById('renameNewName').value = name;
    const modal = new bootstrap.Modal(document.getElementById('renameModal'));
    modal.show();
}

async function submitRename() {
    const oldPath = document.getElementById('renameOldPath').value;
    const newName = document.getElementById('renameNewName').value.trim();
    if (!newName) {
        showToast("Notice", "Please enter a valid new name.", "warning");
        return;
    }

    try {
        const res = await fetch('/api/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ old_path: oldPath, new_name: newName })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Rename Success", `Item renamed to '${data.new_name}'.`, "success");
            const modalEl = document.getElementById('renameModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            fetchFiles();
        } else {
            showToast("Rename Failed", data.error || "Rename error.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error during rename.", "danger");
    }
}

// 10. Real-time System Monitoring & Telemetry with SVG Sparkline
async function fetchStats() {
    try {
        const res = await fetch('/api/system');
        const data = await res.json();
        
        // CPU Percentage & Sparkline Update
        document.getElementById('cpuPercent').textContent = data.cpu_percent + '%';
        document.getElementById('cpuBar').style.width = data.cpu_percent + '%';
        updateCpuSparkline(data.cpu_percent);
        
        // RAM
        document.getElementById('ramText').textContent = `${data.ram_used_gb} / ${data.ram_total_gb} GB (${data.ram_percent}%)`;
        document.getElementById('ramBar').style.width = data.ram_percent + '%';
        
        // Disk
        document.getElementById('diskText').textContent = `${data.disk_used_gb} / ${data.disk_total_gb} GB (${data.disk_percent}%)`;
        document.getElementById('diskBar').style.width = data.disk_percent + '%';

        // Logs
        const logBox = document.getElementById('logBox');
        if (logBox && data.logs) {
            logBox.textContent = data.logs.join('\n');
        }
    } catch (err) {
        console.error("Telemetry fetch error:", err);
    }
}

function updateCpuSparkline(newVal) {
    cpuHistory.shift();
    cpuHistory.push(parseFloat(newVal) || 0);

    const width = 100;
    const height = 30;
    const step = width / (cpuHistory.length - 1);

    let pathD = '';
    let fillD = '';

    cpuHistory.forEach((val, i) => {
        const x = (i * step).toFixed(1);
        // Normalize 0-100 to height-0 (with padding)
        const y = (height - (val / 100) * 26 - 2).toFixed(1);

        if (i === 0) {
            pathD = `M ${x} ${y}`;
            fillD = `M ${x} ${height} L ${x} ${y}`;
        } else {
            pathD += ` L ${x} ${y}`;
            fillD += ` L ${x} ${y}`;
        }
    });

    fillD += ` L ${width} ${height} Z`;

    const pathEl = document.getElementById('cpuSparklinePath');
    const fillEl = document.getElementById('cpuSparklineFill');
    if (pathEl) pathEl.setAttribute('d', pathD);
    if (fillEl) fillEl.setAttribute('d', fillD);
}

// 11. User Management & Access Control
async function fetchUsers() {
    try {
        const res = await fetch('/api/users');
        const data = await res.json();
        cachedUsers = data.users || [];
        const tbody = document.getElementById('userTableBody');
        tbody.innerHTML = '';

        cachedUsers.forEach(u => {
            let roleBadge = '<span class="badge bg-secondary">ReadOnly</span>';
            let permChips = '<span class="badge bg-light text-secondary border">Read</span>';

            if (u.role_name === 'admin') {
                roleBadge = '<span class="badge bg-warning text-dark px-2 py-1"><i class="bi bi-shield-shaded me-1"></i>Admin</span>';
                permChips = '<span class="badge bg-success-subtle text-success border border-success-subtle me-1">Full Control</span>';
            } else if (u.role_name === 'editor') {
                roleBadge = '<span class="badge bg-info text-dark px-2 py-1"><i class="bi bi-pencil-fill me-1"></i>Editor</span>';
                permChips = '<span class="badge bg-light text-dark border me-1">Read</span><span class="badge bg-info-subtle text-info border border-info-subtle">Edit</span>';
            } else if (u.role_name === 'user') {
                roleBadge = '<span class="badge bg-primary px-2 py-1"><i class="bi bi-person-fill me-1"></i>User</span>';
                permChips = '<span class="badge bg-light text-dark border me-1">Read</span><span class="badge bg-primary-subtle text-primary border border-primary-subtle me-1">Write</span><span class="badge bg-info-subtle text-info border border-info-subtle">Edit</span>';
            }

            tbody.innerHTML += `
                <tr>
                    <td><span class="font-monospace text-secondary">${u.id}</span></td>
                    <td><strong>${escapeHtml(u.username)}</strong></td>
                    <td>${roleBadge}</td>
                    <td>${permChips}</td>
                    <td><span class="small text-muted font-monospace">${u.created_at}</span></td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm shadow-sm" style="border-radius: 8px; overflow: hidden;">
                            <button class="btn btn-outline-primary" onclick="openEditUserModal(${u.id})" title="Edit User"><i class="bi bi-pencil-square"></i> Edit</button>
                            <button class="btn btn-outline-danger" onclick="deleteUser(${u.id})" title="Delete User"><i class="bi bi-trash"></i> Delete</button>
                        </div>
                    </td>
                </tr>`;
        });
    } catch (err) {
        console.error("Fetch users error:", err);
    }
}

function openEditUserModal(userId) {
    const user = cachedUsers.find(u => u.id === userId);
    if (!user) return;
    document.getElementById('editUserId').value = user.id;
    document.getElementById('editUsername').value = user.username;
    document.getElementById('editPassword').value = '';
    document.getElementById('editRole').value = user.role_id;
    const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
    modal.show();
}

async function submitEditUser() {
    const userId = document.getElementById('editUserId').value;
    const username = document.getElementById('editUsername').value.trim();
    const password = document.getElementById('editPassword').value;
    const roleId = document.getElementById('editRole').value;

    const payload = {
        username: username,
        role_id: parseInt(roleId)
    };
    if (password) {
        payload.password = password;
    }

    try {
        const res = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("User Updated", "User account and roles saved successfully.", "success");
            const modalEl = document.getElementById('editUserModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            fetchUsers();
        } else {
            showToast("Update Blocked", data.error || "Failed to update user.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error updating user.", "danger");
    }
}

async function addUser() {
    const username = document.getElementById('newUsername').value.trim();
    const password = document.getElementById('newPassword').value;
    const role_id = document.getElementById('newRole').value;

    if (!username || !password) {
        showToast("Notice", "Username and password are required.", "warning");
        return;
    }

    try {
        const res = await fetch('/api/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password, role_id })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("User Created", `Account '${username}' created successfully.`, "success");
            const modalEl = document.getElementById('addUserModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            document.getElementById('newUsername').value = '';
            document.getElementById('newPassword').value = '';
            fetchUsers();
        } else {
            showToast("Creation Failed", data.error || "Failed to create user.", "danger");
        }
    } catch (err) {
        showToast("Error", "Communication error adding user.", "danger");
    }
}

async function deleteUser(id) {
    if (!confirm("Are you sure you want to permanently delete this user?")) return;
    try {
        const res = await fetch(`/api/users/${id}`, { method: 'DELETE' });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("User Removed", "User account deleted successfully.", "info");
            fetchUsers();
        } else {
            showToast("Delete Blocked", data.error || "Cannot delete user.", "danger");
        }
    } catch (err) {
        showToast("Error", "Error deleting user.", "danger");
    }
}

// 12. Backup Scheduler & Recovery Operations
async function fetchBackups() {
    fetchBackupSchedule();
    try {
        const res = await fetch('/api/backup');
        const data = await res.json();
        const tbody = document.getElementById('backupTableBody');
        tbody.innerHTML = '';
        if (!data.backups || data.backups.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No backups created yet.</td></tr>';
            return;
        }
        data.backups.forEach(b => {
            const sizeMb = b.size_bytes ? (b.size_bytes / (1024 * 1024)).toFixed(2) + ' MB' : '-';
            tbody.innerHTML += `
                <tr>
                    <td><strong class="font-monospace text-dark">${escapeHtml(b.backup_name)}</strong></td>
                    <td><span class="font-monospace small">${sizeMb}</span></td>
                    <td><span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1"><i class="bi bi-check2 me-1"></i>${escapeHtml(b.status || 'completed')}</span></td>
                    <td><span class="small text-muted font-monospace">${b.created_at}</span></td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-warning shadow-sm" onclick="restoreBackup('${encodeURIComponent(b.backup_name)}')">
                            <i class="bi bi-arrow-counterclockwise"></i> Restore
                        </button>
                    </td>
                </tr>`;
        });
    } catch (err) {
        console.error("Fetch backups error:", err);
    }
}

async function fetchBackupSchedule() {
    try {
        const res = await fetch('/api/backup/schedule');
        const data = await res.json();
        if (!data.schedule) return;
        const s = data.schedule;

        document.getElementById('schedEnabled').checked = Boolean(s.enabled);
        document.getElementById('schedFrequency').value = s.frequency || 'daily';
        document.getElementById('schedTime').value = s.backup_time || '02:00';
        document.getElementById('schedIncludeDb').checked = Boolean(s.include_db);

        const badge = document.getElementById('scheduleStatusBadge');
        if (s.enabled) {
            badge.className = 'badge bg-success px-3 py-2';
            badge.textContent = `Active (${s.frequency})`;
        } else {
            badge.className = 'badge bg-secondary px-3 py-2';
            badge.textContent = 'Disabled';
        }

        const lastRunText = s.last_run ? s.last_run : 'Never';
        const nextRunText = s.next_run ? s.next_run : (s.enabled ? 'Pending evaluation' : 'Disabled');
        document.getElementById('scheduleRunTimes').innerHTML = `Last Run: <strong>${lastRunText}</strong> | Next Run: <strong>${nextRunText}</strong>`;
    } catch (err) {
        console.error("Schedule fetch error:", err);
    }
}

async function saveBackupSchedule() {
    const enabled = document.getElementById('schedEnabled').checked;
    const frequency = document.getElementById('schedFrequency').value;
    const backupTime = document.getElementById('schedTime').value;
    const includeDb = document.getElementById('schedIncludeDb').checked;

    try {
        const res = await fetch('/api/backup/schedule', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                enabled: enabled,
                frequency: frequency,
                backup_time: backupTime,
                include_db: includeDb
            })
        });
        if (res.ok) {
            showToast("Schedule Saved", "Backup schedule settings updated.", "success");
            fetchBackupSchedule();
        } else {
            showToast("Save Failed", "Failed to update backup schedule.", "danger");
        }
    } catch (err) {
        showToast("Error", "Communication error saving schedule.", "danger");
    }
}

async function createBackup() {
    const includeDb = confirm("Create a full archive containing storage files and MySQL relational database dump?");
    showToast("Backup Started", "Compressing storage and dumping database...", "info");

    try {
        const res = await fetch('/api/backup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ include_db: includeDb })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Backup Complete", `Archive '${data.backup_name}' stored successfully.`, "success");
            fetchBackups();
        } else {
            showToast("Backup Failed", "Failed to create archive.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error during backup.", "danger");
    }
}

async function restoreBackup(encodedName) {
    const name = decodeURIComponent(encodedName);
    if (!confirm(`Warning: Restoring from ${name} will restore storage files and system configurations / database tables. Continue?`)) return;

    showToast("Restoration Started", "Extracting files and restoring system...", "warning");

    try {
        const res = await fetch('/api/restore', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ backup_name: name })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Restored", `Files and MySQL database successfully restored.`, "success");
            fetchFiles();
        } else {
            showToast("Restore Failed", data.error || "Failed to restore archive.", "danger");
        }
    } catch (err) {
        showToast("Error", "Server error during restoration.", "danger");
    }
}

// 13. Security Gateway (ClamAV) & Web Application Firewall (WAF)
async function fetchSecurityData() {
    try {
        const statsRes = await fetch('/api/security/stats');
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById('secCleanCount').textContent = stats.clean_files || 0;
            document.getElementById('secInfectedCount').textContent = stats.infected_threats || 0;
            document.getElementById('secQuarantinedCount').textContent = stats.quarantined_files || 0;
            if (stats.clamav_status) {
                document.getElementById('secEngineName').textContent = stats.clamav_status.version || 'ClamAV Gateway';
                document.getElementById('secDbStatus').innerHTML = `<i class="bi bi-check-circle-fill"></i> ${escapeHtml(stats.clamav_status.db_updated || 'Active')}`;
            }
        }

        const historyRes = await fetch('/api/security/scans');
        if (historyRes.ok) {
            const data = await historyRes.json();
            const tbody = document.getElementById('securityTableBody');
            tbody.innerHTML = '';
            if (!data.scans || data.scans.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No scans recorded yet.</td></tr>';
            } else {
                data.scans.forEach(s => {
                    const isClean = s.scan_result === 'clean';
                    const badgeClass = isClean ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-danger-subtle text-danger border border-danger-subtle';
                    const threatBadge = s.threat_name ? `<span class="badge bg-danger font-monospace">${escapeHtml(s.threat_name)}</span>` : '<span class="text-muted">None</span>';
                    const quarantineBadge = s.is_quarantined
                        ? `<span class="badge bg-warning text-dark"><i class="bi bi-lock-fill"></i> Quarantined</span>`
                        : (isClean ? `<span class="badge bg-light text-success border">Storage</span>` : `<span class="badge bg-secondary">${escapeHtml(s.scan_result)}</span>`);

                    let actionBtn = '';
                    if (s.is_quarantined) {
                        actionBtn = `
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-danger" onclick="quarantineAction(${s.id}, 'delete')">Delete</button>
                                <button class="btn btn-outline-success" onclick="quarantineAction(${s.id}, 'release')">Release</button>
                            </div>`;
                    } else {
                        actionBtn = '<span class="text-muted small">-</span>';
                    }

                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${escapeHtml(s.filename)}</strong></td>
                            <td>${escapeHtml(s.uploader_name || 'System')}</td>
                            <td><span class="badge ${badgeClass}">${escapeHtml(s.scan_result)}</span></td>
                            <td>${threatBadge}</td>
                            <td>${quarantineBadge}</td>
                            <td><span class="small text-muted font-monospace">${s.scanned_at}</span></td>
                            <td class="text-end">${actionBtn}</td>
                        </tr>`;
                });
            }
        }

        const wafRes = await fetch('/api/waf/logs');
        if (wafRes.ok) {
            const wafData = await wafRes.json();
            const tbody = document.getElementById('wafTableBody');
            if (tbody) {
                tbody.innerHTML = '';
                if (!wafData.waf_logs || wafData.waf_logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No suspicious attacks detected. NAS is protected.</td></tr>';
                } else {
                    wafData.waf_logs.forEach(w => {
                        tbody.innerHTML += `
                            <tr>
                                <td><code>${escapeHtml(w.ip_address)}</code></td>
                                <td><span class="badge bg-danger">${escapeHtml(w.attack_type)}</span></td>
                                <td><code>${escapeHtml(w.endpoint)}</code></td>
                                <td><code class="text-danger small">${escapeHtml(w.payload_sample)}</code></td>
                                <td>${w.blocked_at}</td>
                            </tr>`;
                    });
                }
            }
        }

        const wafStatsRes = await fetch('/api/waf/stats');
        if (wafStatsRes.ok) {
            const stats = await wafStatsRes.json();
            const badge = document.getElementById('wafTotalBlockedBadge');
            if (badge) badge.textContent = `${stats.total_blocked || 0} Blocked`;
        }
    } catch (err) {
        console.error("Security data fetch error:", err);
    }
}

async function runStorageMalwareScan() {
    const btn = document.getElementById('runStorageScanBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Scanning Storage...';

    showToast("Malware Inspection", "Deep ClamAV scan started across all NAS storage directories.", "info");

    try {
        const res = await fetch('/api/security/scan-storage', { method: 'POST' });
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-shield-exclamation me-1"></i> Scan Entire Storage Now';

        if (res.ok) {
            const data = await res.json();
            const r = data.result;
            showToast("Scan Complete", `Scanned ${r.total_scanned} files. Clean: ${r.clean_count}, Threats: ${r.infected_count}`, r.infected_count > 0 ? "warning" : "success");
            fetchSecurityData();
        } else {
            showToast("Scan Error", "Failed to complete storage scan.", "danger");
        }
    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-shield-exclamation me-1"></i> Scan Entire Storage Now';
        showToast("Error", "Error communicating with malware scanner.", "danger");
    }
}

async function quarantineAction(scanId, action) {
    const promptMsg = action === 'delete' ? 'Permanently delete this quarantined threat?' : 'Release this file to normal NAS storage?';
    if (!confirm(promptMsg)) return;

    try {
        const res = await fetch(`/api/security/quarantine/${scanId}/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: action })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            showToast("Quarantine Action", data.message || "Action completed.", "info");
            fetchSecurityData();
            fetchFiles();
        } else {
            showToast("Action Failed", data.error || "Action failed.", "danger");
        }
    } catch (err) {
        showToast("Error", "Error executing quarantine action.", "danger");
    }
}

// 14. Global Drag and Drop File Upload
function initGlobalDragAndDrop() {
    const overlay = document.getElementById('globalDropOverlay');
    if (!overlay) return;

    let dragCounter = 0;

    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        overlay.classList.add('active');
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            overlay.classList.remove('active');
        }
    });

    window.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        overlay.classList.remove('active');

        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const input = document.getElementById('fileInput');
            if (input) {
                input.files = e.dataTransfer.files;
                uploadFile();
            }
        }
    });
}

// 15. Keyboard Navigation for Media Viewer (Esc, Left Arrow, Right Arrow)
function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
        const previewModal = document.getElementById('fileEditorModal');
        if (previewModal && previewModal.classList.contains('show')) {
            const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
            if (tag === 'textarea' || tag === 'input') return;

            if (e.key === 'ArrowLeft') {
                previewPrevFile();
            } else if (e.key === 'ArrowRight') {
                previewNextFile();
            }
        }
    });

    const previewModal = document.getElementById('fileEditorModal');
    if (previewModal) {
        previewModal.addEventListener('hidden.bs.modal', () => {
            const container = document.getElementById('previewMediaContainer');
            if (container) {
                container.querySelectorAll('video, audio').forEach(el => {
                    try {
                        el.pause();
                        el.removeAttribute('src');
                        el.load();
                    } catch (e) {}
                });
            }
        });
    }
}

// 16. Lifecycle Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    fetchFiles();
    fetchStats();
    setInterval(fetchStats, 5000);
    initGlobalDragAndDrop();
    initKeyboardShortcuts();
});
