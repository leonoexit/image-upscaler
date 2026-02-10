/**
 * Image Upscaler — Frontend Logic
 */

// ==================== STATE ====================
let selectedFiles = [];
let currentScale = 4;
let currentModel = 'RealESRGAN_x4plus';
let currentSessionId = null;

// ==================== DOM ====================
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const previewGrid = document.getElementById('previewGrid');
const optionsPanel = document.getElementById('optionsPanel');
const scaleToggle = document.getElementById('scaleToggle');
const modelToggle = document.getElementById('modelToggle');
const upscaleBtn = document.getElementById('upscaleBtn');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressTitle = document.getElementById('progressTitle');
const progressSubtitle = document.getElementById('progressSubtitle');
const resultsSection = document.getElementById('resultsSection');
const resultsGrid = document.getElementById('resultsGrid');
const uploadSection = document.getElementById('uploadSection');
const newBatchBtn = document.getElementById('newBatchBtn');

// ==================== DRAG & DROP ====================
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
  addFiles(files);
});

fileInput.addEventListener('change', () => {
  const files = Array.from(fileInput.files);
  addFiles(files);
  fileInput.value = '';
});

// ==================== FILE HANDLING ====================
function addFiles(files) {
  const maxFiles = 50;
  const maxSize = 20 * 1024 * 1024; // 20MB per file

  for (const file of files) {
    if (selectedFiles.length >= maxFiles) {
      alert(`Tối đa ${maxFiles} ảnh mỗi lần.`);
      break;
    }
    if (file.size > maxSize) {
      alert(`"${file.name}" vượt quá 20MB, bỏ qua.`);
      continue;
    }
    if (!file.type.startsWith('image/')) {
      continue;
    }
    selectedFiles.push(file);
  }

  renderPreviews();
  updateUI();
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  renderPreviews();
  updateUI();
}

function renderPreviews() {
  previewGrid.innerHTML = '';

  selectedFiles.forEach((file, idx) => {
    const item = document.createElement('div');
    item.className = 'preview-item';
    item.style.animationDelay = `${idx * 0.05}s`;

    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.onload = () => URL.revokeObjectURL(img.src);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'preview-remove';
    removeBtn.innerHTML = '✕';
    removeBtn.onclick = (e) => { e.stopPropagation(); removeFile(idx); };

    const nameLabel = document.createElement('div');
    nameLabel.className = 'preview-name';
    nameLabel.textContent = file.name;

    item.append(img, removeBtn, nameLabel);
    previewGrid.appendChild(item);
  });
}

function updateUI() {
  if (selectedFiles.length > 0) {
    optionsPanel.style.display = 'flex';
  } else {
    optionsPanel.style.display = 'none';
  }
}

// ==================== TOGGLE BUTTONS ====================
scaleToggle.addEventListener('click', (e) => {
  if (e.target.classList.contains('toggle-btn')) {
    scaleToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentScale = parseInt(e.target.dataset.value);
  }
});

modelToggle.addEventListener('click', (e) => {
  if (e.target.classList.contains('toggle-btn')) {
    modelToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentModel = e.target.dataset.value;
  }
});

// ==================== UPSCALE ====================
upscaleBtn.addEventListener('click', startUpscale);

async function startUpscale() {
  if (selectedFiles.length === 0) return;

  // Show progress
  uploadSection.style.display = 'none';
  progressSection.style.display = 'block';
  resultsSection.style.display = 'none';
  progressBar.style.width = '0%';
  progressTitle.textContent = 'Đang xử lý...';
  progressSubtitle.textContent = `Đang upscale ${selectedFiles.length} ảnh với scale ${currentScale}x`;

  const formData = new FormData();
  selectedFiles.forEach(file => formData.append('images', file));
  formData.append('scale', currentScale);
  formData.append('model', currentModel);

  try {
    // Use XHR for progress tracking
    const response = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upscale');

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const uploadPct = (e.loaded / e.total) * 30; // Upload = 30%
          progressBar.style.width = uploadPct + '%';
          progressTitle.textContent = 'Đang tải ảnh lên...';
        }
      });

      xhr.addEventListener('loadstart', () => {
        progressBar.style.width = '30%';
        progressTitle.textContent = 'Đang upscale bằng AI...';
        progressSubtitle.textContent = 'Quá trình này có thể mất vài phút tùy kích thước ảnh';

        // Simulate progress during processing
        let progress = 30;
        const interval = setInterval(() => {
          if (progress < 90) {
            progress += Math.random() * 3;
            progressBar.style.width = Math.min(progress, 90) + '%';
          }
        }, 1000);
        xhr._progressInterval = interval;
      });

      xhr.addEventListener('load', () => {
        clearInterval(xhr._progressInterval);
        progressBar.style.width = '100%';
        if (xhr.status === 200) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.error || 'Processing failed'));
          } catch {
            reject(new Error('Processing failed'));
          }
        }
      });

      xhr.addEventListener('error', () => {
        clearInterval(xhr._progressInterval);
        reject(new Error('Network error'));
      });

      xhr.send(formData);
    });

    // Show results
    showResults(response);

  } catch (error) {
    progressSection.style.display = 'none';
    uploadSection.style.display = 'block';
    alert('Lỗi: ' + error.message);
  }
}

// ==================== RESULTS ====================
function showResults(data) {
  progressSection.style.display = 'none';
  resultsSection.style.display = 'block';
  resultsGrid.innerHTML = '';
  currentSessionId = data.session_id;

  // Build results header with Download ZIP button
  const header = document.querySelector('.results-header');
  // Remove old zip button if exists
  const oldZipBtn = document.getElementById('zipBtn');
  if (oldZipBtn) oldZipBtn.remove();

  const zipBtn = document.createElement('a');
  zipBtn.id = 'zipBtn';
  zipBtn.href = `/api/download-zip/${data.session_id}`;
  zipBtn.className = 'btn-secondary';
  zipBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3V11M8 11L5 8M8 11L11 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 13H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        Tải tất cả (ZIP)
    `;
  header.insertBefore(zipBtn, document.getElementById('newBatchBtn'));

  data.results.forEach((result, idx) => {
    const item = document.createElement('div');
    item.className = 'result-item';
    item.style.animationDelay = `${idx * 0.1}s`;

    item.innerHTML = `
            <div class="result-image-wrapper">
                <img src="${result.preview_url}" alt="${result.output_name}" loading="lazy">
            </div>
            <div class="result-info">
                <div class="result-name" title="${result.original_name}">${result.original_name}</div>
                <div class="result-dimensions">${result.width} × ${result.height}px • ${data.scale}x</div>
                <a href="${result.download_url}" class="btn-download">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 2V10M7 10L4 7M7 10L10 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M2 11H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    Tải xuống
                </a>
            </div>
        `;
    resultsGrid.appendChild(item);
  });
}

// ==================== NEW BATCH ====================
newBatchBtn.addEventListener('click', () => {
  selectedFiles = [];
  previewGrid.innerHTML = '';
  resultsSection.style.display = 'none';
  uploadSection.style.display = 'block';
  optionsPanel.style.display = 'none';
  progressBar.style.width = '0%';
  // Remove zip button
  const zipBtn = document.getElementById('zipBtn');
  if (zipBtn) zipBtn.remove();
  currentSessionId = null;
});
