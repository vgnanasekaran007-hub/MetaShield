/**
 * MetaShield – app.js
 * =====================
 * Complete frontend logic for the dashboard page.
 * Handles: upload, metadata display, GPS map, editing,
 *          cleaning, batch processing, histogram, palette,
 *          theme, keyboard shortcuts, toasts, ripple.
 */

'use strict';

/* ── State ─────────────────────────────────────────────────── */
const MS = {
  currentFile: null,          // uploaded filename (server-side)
  currentOriginal: null,      // original filename
  currentMetadata: null,      // full metadata object
  batchFiles: [],             // array of uploaded filenames (batch mode)
  batchMode: false,
  previewRotation: 0,
  leafletMap: null,
  leafletMarker: null,
  histogramChart: null,
  settings: {},               // persisted settings
};

/* ── Page init ─────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLoader();
  initSidebar();
  initUploadZone();
  initKeyboardShortcuts();
  initRipple();
  loadSettings();
  buildEditorFields();
});

/* ── Theme ──────────────────────────────────────────────────── */
function initTheme() {
  const root = document.documentElement;
  root.setAttribute('data-theme', localStorage.getItem('ms-theme') || 'dark');
  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('ms-theme', next);
  });
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ms-theme', theme);
  showToast(`Theme switched to ${theme}`, 'info');
}

/* ── Page loader ─────────────────────────────────────────────── */
function initLoader() {
  window.addEventListener('load', () => {
    setTimeout(() => document.getElementById('page-loader').classList.add('hidden'), 700);
  });
}

/* ── Sidebar ────────────────────────────────────────────────── */
function initSidebar() {
  document.getElementById('sidebarToggle').addEventListener('click', toggleSidebar);
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const mc = document.getElementById('mainContent');
  if (window.innerWidth > 991) {
    sb.classList.toggle('collapsed');
    mc.classList.toggle('expanded');
  } else {
    sb.classList.toggle('open');
  }
}

/* ── Section switching ───────────────────────────────────────── */
function switchSection(name) {
  document.querySelectorAll('main > section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-item-custom').forEach(n => n.classList.remove('active'));

  const el = document.getElementById('section-' + name);
  if (el) el.style.display = 'block';

  const navEl = document.getElementById('nav-' + name);
  if (navEl) navEl.classList.add('active');

  // Re-show the Leaflet map if switching to metadata/GPS tab
  if (name === 'metadata' && MS.leafletMap) {
    setTimeout(() => MS.leafletMap.invalidateSize(), 200);
  }

  // Close sidebar on mobile
  if (window.innerWidth <= 991) {
    document.getElementById('sidebar').classList.remove('open');
  }
}

/* ── Upload Zone ────────────────────────────────────────────── */
function initUploadZone() {
  const zone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');

  zone.addEventListener('click', () => fileInput.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener('change', e => handleFiles(e.target.files));
}

function handleFiles(files) {
  if (!files || !files.length) return;

  if (MS.batchMode) {
    uploadBatch(files);
  } else {
    uploadSingle(files[0]);
  }
}

/* ── Single upload ───────────────────────────────────────────── */
function uploadSingle(file) {
  showUploadProgress(true);
  const fd = new FormData();
  fd.append('file', file);

  simulateProgress();

  fetch('/upload', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      showUploadProgress(false);
      if (!data.success) { showToast(data.error || 'Upload failed', 'error'); return; }
      const fileData = data.files[0];
      if (!fileData || !fileData.success) {
        showToast(fileData?.error || 'Upload failed', 'error');
        return;
      }
      MS.currentFile = fileData.filename;
      MS.currentOriginal = fileData.original_name;
      MS.currentMetadata = fileData.metadata;

      renderPreview(fileData);
      renderQuickStats(fileData.metadata);

      showToast(`✓ ${fileData.original_name} uploaded!`, 'success');

      // Auto-switch to metadata tab if setting enabled
      if (MS.settings.autoSwitch !== false) {
        setTimeout(() => {
          switchSection('metadata');
          renderMetadata(fileData.metadata);
        }, 300);
      }
    })
    .catch(err => {
      showUploadProgress(false);
      showToast('Upload error: ' + err.message, 'error');
    });
}

function simulateProgress() {
  const bar = document.getElementById('uploadProgressBar');
  let pct = 0;
  const timer = setInterval(() => {
    pct = Math.min(pct + Math.random() * 15, 90);
    bar.style.width = pct + '%';
    if (pct >= 90) clearInterval(timer);
  }, 200);
}

function showUploadProgress(visible) {
  document.getElementById('uploadProgress').style.display = visible ? 'block' : 'none';
  if (!visible) document.getElementById('uploadProgressBar').style.width = '100%';
}

/* ── Render preview ──────────────────────────────────────────── */
function renderPreview(fileData) {
  const meta = fileData.metadata || {};
  const fi = meta.file_info || {};
  const ii = meta.image_info || {};

  // Show image
  const img = document.getElementById('previewImg');
  img.src = '/preview/' + fileData.filename;
  img.style.transform = 'rotate(0deg)';
  MS.previewRotation = 0;

  // Hide skeleton, show content
  document.getElementById('previewSkeleton').style.display = 'none';
  document.getElementById('previewContent').style.display = 'block';

  // File info chips
  const chips = document.getElementById('fileInfoChips');
  chips.innerHTML = [
    { icon: 'fa-file', text: fi.extension || '?', color: 'var(--primary)' },
    { icon: 'fa-expand', text: `${ii.width || '?'}×${ii.height || '?'}`, color: 'var(--accent)' },
    { icon: 'fa-weight-hanging', text: fi.size_human || '?', color: 'var(--success)' },
    { icon: 'fa-palette', text: ii.mode || '?', color: 'var(--warning)' },
  ].map(c => `<span class="info-chip"><i class="fas ${c.icon}" style="color:${c.color};"></i>${c.text}</span>`).join('');

  // Update editor & cleaner previews
  ['editorPreviewImg', 'cleanerPreviewImg'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.src = '/preview/' + fileData.filename;
  });

  // Show editor/cleaner sections
  ['editorPlaceholder','cleanerPlaceholder','histogramPlaceholder','palettePlaceholder'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  ['editorContent','cleanerContent','histogramContent','paletteContent'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
  });
}

/* ── Quick stats ─────────────────────────────────────────────── */
function renderQuickStats(meta) {
  if (!meta) return;
  const fi = meta.file_info || {};
  const ii = meta.image_info || {};
  const gps = meta.gps || {};

  const statsEl = document.getElementById('quickStats');
  if (statsEl) {
    statsEl.style.removeProperty('display');
    statsEl.style.display = 'flex';
  }

  setText('statFormat', fi.extension || '?');
  setText('statDims',   `${ii.width || '?'}×${ii.height || '?'}`);
  setText('statSize',   fi.size_human || '?');
  setText('statGPS',    gps.HasGPS ? '✓ Found' : '✗ None');
  if (gps.HasGPS) {
    const el = document.getElementById('statGPS');
    if (el) el.style.color = 'var(--danger)';
  }
}

/* ── Metadata renderer ───────────────────────────────────────── */
function renderMetadata(meta) {
  if (!meta) return;

  // Show content, hide placeholder
  document.getElementById('metaPlaceholder').style.display = 'none';
  document.getElementById('metaContent').style.display = 'block';
  setText('metaFilename', MS.currentOriginal || 'Unknown file');

  // File info
  const fi = meta.file_info || {};
  const ii = meta.image_info || {};
  document.getElementById('fileInfoRows').innerHTML =
    metaRows({ ...fi }) +
    '<div style="height:.5rem;"></div>';

  document.getElementById('imageInfoRows').innerHTML = metaRows({ ...ii });

  // EXIF
  const exif = meta.exif || {};
  const exifKeys = Object.keys(exif);
  if (exifKeys.length) {
    document.getElementById('exifRows').innerHTML = metaRows(exif);
    document.getElementById('noExifMsg').style.display = 'none';
  } else {
    document.getElementById('exifRows').innerHTML = '';
    document.getElementById('noExifMsg').style.display = 'block';
  }

  // GPS
  renderGPS(meta.gps || {});

  // Raw EXIF
  const raw = meta.raw_exif || {};
  const rawKeys = Object.keys(raw);
  if (rawKeys.length) {
    document.getElementById('rawExifBody').innerHTML = rawKeys.map(k =>
      `<tr><td class="key-col">${escHtml(k)}</td><td>${escHtml(raw[k])}</td></tr>`
    ).join('');
    document.getElementById('noRawMsg').style.display = 'none';
  } else {
    document.getElementById('rawExifBody').innerHTML = '';
    document.getElementById('noRawMsg').style.display = 'block';
  }

  // ICC Profile
  const icc = meta.icc_profile || {};
  document.getElementById('iccInfo').innerHTML = icc.present
    ? `<div class="meta-row"><span class="meta-key">Status</span><span class="meta-val badge-success">Present</span></div>
       <div class="meta-row"><span class="meta-key">Size</span><span class="meta-val">${icc.size_bytes} bytes</span></div>
       <div class="meta-row"><span class="meta-key">Description</span><span class="meta-val">${escHtml(icc.description || 'N/A')}</span></div>`
    : '<p style="color:var(--text-muted);font-size:.85rem;">No ICC profile found.</p>';

  // Thumbnail
  if (meta.thumbnail) {
    document.getElementById('thumbnailContent').innerHTML =
      `<img src="${meta.thumbnail}" alt="Embedded thumbnail" style="max-width:100%;border-radius:var(--radius-sm);border:1px solid var(--border);" />
       <div style="font-size:.75rem;color:var(--text-muted);margin-top:.5rem;">Embedded JPEG thumbnail</div>`;
  } else {
    document.getElementById('thumbnailContent').innerHTML =
      '<p style="font-size:.85rem;color:var(--text-muted);">No embedded thumbnail.</p>';
  }

  // Histogram
  if (meta.histogram && meta.histogram.labels) {
    renderHistogram(meta.histogram);
  }

  // Color palette
  if (meta.color_palette && meta.color_palette.length) {
    renderPalette(meta.color_palette);
  }

  // Editor current values
  if (meta.editable) {
    populateEditorValues(meta.editable);
  }
}

function metaRows(obj) {
  if (!obj || !Object.keys(obj).length) return '<p style="color:var(--text-muted);font-size:.85rem;">No data</p>';
  return Object.entries(obj).map(([k, v]) => {
    if (v === null || v === undefined || v === '') return '';
    const display = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return `<div class="meta-row">
      <span class="meta-key">${escHtml(k)}</span>
      <span class="meta-val" title="${escHtml(display)}">${escHtml(display.length > 120 ? display.slice(0, 120) + '…' : display)}</span>
    </div>`;
  }).join('');
}

/* ── GPS / Map ───────────────────────────────────────────────── */
function renderGPS(gps) {
  const hasGPS = gps && gps.HasGPS;

  document.getElementById('noGpsMsg').style.display = hasGPS ? 'none' : 'block';
  document.getElementById('gpsMap').style.display = hasGPS ? 'block' : 'none';

  const rows = document.getElementById('gpsRows');
  if (hasGPS) {
    rows.innerHTML = metaRows({
      Latitude:  gps.Latitude,
      Longitude: gps.Longitude,
      Altitude:  gps.Altitude || null,
      LatRef:    gps.LatitudeRef || null,
      LonRef:    gps.LongitudeRef || null,
    });

    // Google Maps link
    const link = document.getElementById('googleMapsLink');
    if (link) link.href = gps.MapsURL || '#';

    // Leaflet map
    if (MS.settings.showGpsMap !== false) {
      initLeafletMap(gps.Latitude, gps.Longitude);
    }
  } else {
    rows.innerHTML = '';
  }
}

function initLeafletMap(lat, lng) {
  const mapEl = document.getElementById('leafletMap');
  if (!mapEl) return;

  // Add map div
  mapEl.innerHTML = '<div id="gps-map"></div>';

  setTimeout(() => {
    if (MS.leafletMap) {
      MS.leafletMap.remove();
      MS.leafletMap = null;
    }

    MS.leafletMap = L.map('gps-map').setView([lat, lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
    }).addTo(MS.leafletMap);

    MS.leafletMarker = L.marker([lat, lng]).addTo(MS.leafletMap);
    MS.leafletMarker.bindPopup(`📍 ${lat.toFixed(6)}, ${lng.toFixed(6)}`).openPopup();
  }, 100);
}

/* ── Metadata search ─────────────────────────────────────────── */
function filterMeta(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('.meta-row').forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = q === '' || text.includes(q) ? '' : 'none';
  });
}

/* ── Tab switching (metadata) ────────────────────────────────── */
function switchMetaTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#metaTabs .tab-btn').forEach(b => b.classList.remove('active'));

  const pane = document.getElementById('tab-' + name);
  if (pane) pane.classList.add('active');

  // Find matching button
  document.querySelectorAll('#metaTabs .tab-btn').forEach(b => {
    if (b.textContent.trim().toLowerCase().startsWith(name)) b.classList.add('active');
  });
}

/* ── Copy all metadata ───────────────────────────────────────── */
function copyAllMeta() {
  if (!MS.currentMetadata) { showToast('No metadata loaded', 'warning'); return; }
  const text = JSON.stringify(MS.currentMetadata, null, 2);
  navigator.clipboard.writeText(text).then(
    () => showToast('Metadata copied to clipboard!', 'success'),
    () => showToast('Copy failed', 'error')
  );
}

/* ── Export metadata ─────────────────────────────────────────── */
function exportMeta(format) {
  if (!MS.currentFile) { showToast('Upload an image first', 'warning'); return; }
  const url = `/export/${MS.currentFile}/${format}`;
  showToast(`Exporting as ${format.toUpperCase()}…`, 'info');
  window.open(url, '_blank');
}

/* ── Editor ──────────────────────────────────────────────────── */
function buildEditorFields() {
  if (typeof EDITABLE_FIELDS === 'undefined') return;

  const container = document.getElementById('editorFields');
  if (!container) return;

  const fieldDefs = Object.entries(EDITABLE_FIELDS);
  container.innerHTML = fieldDefs.map(([fieldName, meta]) => `
    <div class="col-md-6">
      <div class="editor-field">
        <label class="form-label-custom" for="ef-${fieldName}">${escHtml(meta.label)}</label>
        <input type="${meta.type === 'datetime' ? 'datetime-local' : 'text'}"
               class="form-control-custom"
               id="ef-${fieldName}"
               name="${fieldName}"
               placeholder="${escHtml(meta.label)}"
               autocomplete="off" />
      </div>
    </div>
  `).join('');
}

function populateEditorValues(editable) {
  if (!editable) return;
  Object.entries(editable).forEach(([key, val]) => {
    const el = document.getElementById('ef-' + key);
    if (el && val) {
      if (el.type === 'datetime-local' && val) {
        // Convert EXIF datetime "YYYY:MM:DD HH:MM:SS" → ISO
        try {
          const normalized = val.replace(/^(\d{4}):(\d{2}):(\d{2})/, '$1-$2-$3');
          el.value = new Date(normalized).toISOString().slice(0, 16);
        } catch {
          el.value = '';
        }
      } else {
        el.value = val;
      }
    }
  });

  // Show current meta summary
  const summary = document.getElementById('editorCurrentMeta');
  if (summary) {
    const pairs = Object.entries(editable).filter(([, v]) => v).slice(0, 6);
    summary.innerHTML = pairs.map(([k, v]) =>
      `<div class="meta-row"><span class="meta-key">${escHtml(k)}</span><span class="meta-val" style="font-size:.78rem;">${escHtml(String(v).slice(0,60))}</span></div>`
    ).join('');
  }
}

function clearEditorFields() {
  document.querySelectorAll('#editorFields input').forEach(el => el.value = '');
  showToast('Editor fields cleared', 'info');
}

function saveMetadata() {
  if (!MS.currentFile) { showToast('Upload an image first', 'warning'); return; }

  const edits = {};
  document.querySelectorAll('#editorFields input').forEach(el => {
    if (el.value.trim()) edits[el.name] = el.value.trim();
  });

  if (!Object.keys(edits).length) { showToast('Enter at least one field to save', 'warning'); return; }

  showToast('Saving metadata…', 'info');

  fetch('/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: MS.currentFile, edits }),
  })
  .then(r => r.json())
  .then(data => {
    if (!data.success) { showToast(data.error || 'Save failed', 'error'); return; }
    showToast(`✓ Saved! Downloading edited image…`, 'success');
    window.location.href = '/download/' + data.download_name;
  })
  .catch(() => showToast('Save error', 'error'));
}

/* ── Cleaner ──────────────────────────────────────────────────── */
function toggleCleanOpt(row, key) {
  const cb = row.querySelector('input[type="checkbox"]');
  if (cb && event && event.target !== cb) cb.checked = !cb.checked;
}

function checkAllClean(checked) {
  document.querySelectorAll('#cleanerOptions input[type="checkbox"]').forEach(cb => cb.checked = checked);
}

function getCleanOptions() {
  return Array.from(document.querySelectorAll('#cleanerOptions input[type="checkbox"]'))
    .filter(cb => cb.checked)
    .map(cb => cb.dataset.key);
}

function cleanMetadata() {
  if (!MS.currentFile) { showToast('Upload an image first', 'warning'); return; }

  const options = getCleanOptions();
  const quality = parseInt(document.getElementById('qualitySlider').value);

  showToast('Stripping metadata…', 'info');

  fetch('/remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: MS.currentFile, options, quality }),
  })
  .then(r => r.json())
  .then(data => {
    if (!data.success) { showToast(data.error || 'Clean failed', 'error'); return; }

    // Show results
    const resultsEl = document.getElementById('cleanerResults');
    resultsEl.style.display = 'block';
    document.getElementById('cleanerResultContent').innerHTML = `
      <div class="meta-row"><span class="meta-key">Removed</span><span class="meta-val">${data.removed.join(', ')}</span></div>
      <div class="meta-row"><span class="meta-key">Original Size</span><span class="meta-val">${data.size_before_human}</span></div>
      <div class="meta-row"><span class="meta-key">Clean Size</span><span class="meta-val" style="color:var(--success);">${data.size_after_human}</span></div>
      <div class="meta-row"><span class="meta-key">Space Saved</span><span class="meta-val" style="color:var(--success);font-weight:700;">${data.savings_pct}%</span></div>
      <div class="mt-3">
        <div class="progress-custom"><div class="progress-bar-custom" style="width:${100 - data.savings_pct}%;"></div></div>
        <div style="font-size:.75rem;color:var(--text-muted);margin-top:.3rem;">${data.savings_pct}% size reduction</div>
      </div>
    `;

    showToast('✓ Metadata removed! Downloading…', 'success');
    setTimeout(() => { window.location.href = '/download/' + data.download_name; }, 800);
  })
  .catch(() => showToast('Clean error', 'error'));
}

function toggleBatchMode() {
  MS.batchMode = !MS.batchMode;
  document.getElementById('batchModeBtn').classList.toggle('btn-primary-custom', MS.batchMode);
  document.getElementById('batchFileList').style.display = MS.batchMode ? 'block' : 'none';
  showToast(`Batch mode ${MS.batchMode ? 'ON' : 'OFF'}`, 'info');
}

function uploadBatch(files) {
  const promises = Array.from(files).map(file => {
    const fd = new FormData();
    fd.append('file', file);
    return fetch('/upload', { method:'POST', body:fd })
      .then(r => r.json())
      .then(data => {
        if (data.success && data.files[0]?.success) {
          MS.batchFiles.push(data.files[0].filename);
          return data.files[0];
        }
        return null;
      });
  });

  Promise.all(promises).then(results => {
    const ok = results.filter(Boolean);
    updateBatchFileList(ok);
    showToast(`${ok.length} files ready for batch processing`, 'success');
  });
}

function updateBatchFileList(fileDataArray) {
  document.getElementById('batchFileList').innerHTML = `
    <div class="section-title mt-3"><i class="fas fa-layer-group"></i> Batch Files (${fileDataArray.length})</div>
    ${fileDataArray.map(f => `
      <div class="meta-row">
        <span class="meta-key"><i class="fas fa-image me-1" style="color:var(--primary);"></i>${escHtml(f.original_name)}</span>
        <span class="badge-success">Ready</span>
      </div>
    `).join('')}
  `;
}

function batchClean() {
  if (!MS.batchFiles.length) { showToast('Upload files first (batch mode)', 'warning'); return; }

  const options = getCleanOptions();
  const quality = parseInt(document.getElementById('qualitySlider').value);

  showToast('Batch cleaning…', 'info');

  fetch('/batch_remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filenames: MS.batchFiles, options, quality }),
  })
  .then(r => r.json())
  .then(data => {
    if (!data.success) { showToast(data.error || 'Batch failed', 'error'); return; }
    showToast(`✓ ${data.results.filter(r=>r.success).length} files cleaned! Downloading ZIP…`, 'success');
    setTimeout(() => { window.location.href = '/download_zip/' + data.zip_name; }, 800);
  })
  .catch(() => showToast('Batch error', 'error'));
}

/* ── Histogram ───────────────────────────────────────────────── */
function renderHistogram(histData) {
  const canvas = document.getElementById('histogramChart');
  if (!canvas) return;

  if (MS.histogramChart) {
    MS.histogramChart.destroy();
    MS.histogramChart = null;
  }

  // Downsample to every 4 values for performance
  const step = 4;
  const labels = histData.labels.filter((_, i) => i % step === 0);
  const red    = histData.red.filter((_, i) => i % step === 0);
  const green  = histData.green.filter((_, i) => i % step === 0);
  const blue   = histData.blue.filter((_, i) => i % step === 0);

  Chart.defaults.color = '#94A3B8';
  MS.histogramChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Red',   data: red,   borderColor:'#EF4444', backgroundColor:'rgba(239,68,68,.12)',  fill:true, tension:.4, pointRadius:0, borderWidth:1.5 },
        { label: 'Green', data: green, borderColor:'#22C55E', backgroundColor:'rgba(34,197,94,.12)',  fill:true, tension:.4, pointRadius:0, borderWidth:1.5 },
        { label: 'Blue',  data: blue,  borderColor:'#38BDF8', backgroundColor:'rgba(56,189,248,.12)', fill:true, tension:.4, pointRadius:0, borderWidth:1.5 },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode:'index', intersect:false },
      plugins: { legend: { position:'bottom', labels:{ padding:16, font:{size:11} } } },
      scales: {
        x: { grid:{ color:'rgba(99,116,143,.1)' }, ticks:{ maxTicksLimit:10 } },
        y: { grid:{ color:'rgba(99,116,143,.1)' }, beginAtZero:true },
      }
    }
  });
}

/* ── Color Palette ───────────────────────────────────────────── */
function renderPalette(colors) {
  const grid = document.getElementById('paletteGrid');
  const details = document.getElementById('paletteDetails');
  if (!grid) return;

  grid.innerHTML = colors.map(hex => `
    <div class="palette-swatch" data-color="${hex}" style="background:${hex};width:56px;height:56px;"
         onclick="copyHex('${hex}')" title="${hex}"></div>
  `).join('');

  details.innerHTML = colors.map(hex => {
    const rgb = hexToRgb(hex);
    return `<div class="col-6 col-md-3">
      <div style="background:${hex};height:40px;border-radius:var(--radius-sm) var(--radius-sm) 0 0;"></div>
      <div style="background:var(--bg-input);border-radius:0 0 var(--radius-sm) var(--radius-sm);padding:.5rem;font-size:.75rem;">
        <div style="font-family:var(--font-mono);font-weight:700;">${hex.toUpperCase()}</div>
        <div style="color:var(--text-muted);">rgb(${rgb})</div>
      </div>
    </div>`;
  }).join('');
}

function copyHex(hex) {
  navigator.clipboard.writeText(hex).then(
    () => showToast(`Copied ${hex}`, 'success'),
    () => showToast('Copy failed', 'error')
  );
}

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `${r}, ${g}, ${b}`;
}

/* ── Image preview controls ──────────────────────────────────── */
function rotatePreview() {
  MS.previewRotation = (MS.previewRotation + 90) % 360;
  document.getElementById('previewImg').style.transform = `rotate(${MS.previewRotation}deg)`;
}

function zoomImage() {
  const src = document.getElementById('previewImg').src;
  document.getElementById('fullscreenImg').src = src;
  document.getElementById('fullscreenOverlay').classList.add('open');
}

function closeFullscreen() {
  document.getElementById('fullscreenOverlay').classList.remove('open');
}

function downloadOriginal() {
  if (MS.currentFile) {
    window.location.href = '/download/' + MS.currentFile;
  }
}

/* ── Settings ────────────────────────────────────────────────── */
function loadSettings() {
  try {
    MS.settings = JSON.parse(localStorage.getItem('ms-settings') || '{}');
  } catch {
    MS.settings = {};
  }

  // Apply toggles
  applyToggle('gpsMapToggle', MS.settings.showGpsMap !== false);
  applyToggle('autoSwitchToggle', MS.settings.autoSwitch !== false);

  const defQuality = document.getElementById('defaultQuality');
  if (defQuality && MS.settings.quality) {
    defQuality.value = MS.settings.quality;
    document.getElementById('defQualVal').textContent = MS.settings.quality + '%';
  }
}

function saveSetting(key, value) {
  MS.settings[key] = value;
  localStorage.setItem('ms-settings', JSON.stringify(MS.settings));
}

function toggleSetting(key, btn) {
  const current = MS.settings[key] !== false;
  MS.settings[key] = !current;
  localStorage.setItem('ms-settings', JSON.stringify(MS.settings));
  applyToggle(btn.id, MS.settings[key]);
  showToast(`${key} ${MS.settings[key] ? 'enabled' : 'disabled'}`, 'info');
}

function applyToggle(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  if (value) {
    el.setAttribute('data-theme', 'light'); // reuse light styling for ON state
    el.style.background = 'var(--primary)';
    el.style.setProperty('--toggle-x', '20px');
  } else {
    el.style.background = '';
  }
}

/* ── Keyboard shortcuts ──────────────────────────────────────── */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.ctrlKey) {
      switch (e.key.toLowerCase()) {
        case 'u': e.preventDefault(); switchSection('upload'); break;
        case 'm': e.preventDefault(); switchSection('metadata'); break;
        case 'e': e.preventDefault(); switchSection('editor'); break;
        case 'd': e.preventDefault(); switchSection('cleaner'); break;
        case 'b': e.preventDefault(); toggleSidebar(); break;
        case 't': e.preventDefault(); {
          const cur = document.documentElement.getAttribute('data-theme');
          setTheme(cur === 'dark' ? 'light' : 'dark');
        } break;
      }
    }

    if (e.key === 'f' || e.key === 'F') {
      if (MS.currentFile) zoomImage();
    }
    if (e.key === 'Escape') {
      closeFullscreen();
    }
  });
}

/* ── Toast notifications ─────────────────────────────────────── */
function showToast(msg, type = 'info') {
  const icons  = { success:'fa-check-circle', error:'fa-circle-xmark', info:'fa-circle-info', warning:'fa-triangle-exclamation' };
  const colors = { success:'var(--success)', error:'var(--danger)', info:'var(--info)', warning:'var(--warning)' };
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-custom ${type}`;
  toast.innerHTML = `
    <i class="fas ${icons[type] || 'fa-circle-info'}" style="color:${colors[type]};font-size:1.1rem;flex-shrink:0;"></i>
    <span style="flex:1;">${escHtml(msg)}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:0 0 0 .5rem;font-size:.9rem;">✕</button>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Ripple effect ───────────────────────────────────────────── */
function initRipple() {
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('.ripple');
    if (!btn) return;
    const r = document.createElement('span');
    r.className = 'ripple-effect';
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    r.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX-rect.left-size/2}px;top:${e.clientY-rect.top-size/2}px;`;
    btn.appendChild(r);
    setTimeout(() => r.remove(), 600);
  });
}

/* ── Utility ─────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
