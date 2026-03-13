/* ── State ─────────────────────────────────────────────── */
let currentProjectId = null;
let currentProject   = null;
let searchPollTimer  = null;
let pendingReplaceNum = null;

/* ── API helpers ───────────────────────────────────────── */
const api = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(url, body) {
    const isForm = body instanceof FormData;
    const r = await fetch(url, {
      method: 'POST',
      headers: isForm ? {} : { 'Content-Type': 'application/json' },
      body: isForm ? body : JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async put(url, body) {
    const r = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async del(url) {
    const r = await fetch(url, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

/* ── Toast ─────────────────────────────────────────────── */
let toastTimer = null;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast${type ? ' ' + type : ''}`;
  el.classList.remove('hidden');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3000);
}

/* ── Navigation ────────────────────────────────────────── */
function navigate(view, projectId = null) {
  document.getElementById('view-home').classList.toggle('hidden', view !== 'home');
  document.getElementById('view-editor').classList.toggle('hidden', view !== 'editor');
  if (searchPollTimer) { clearInterval(searchPollTimer); searchPollTimer = null; }
  if (view === 'home') loadHome();
  if (view === 'editor' && projectId) loadEditor(projectId);
}

/* ══ HOME ══════════════════════════════════════════════════ */

async function loadHome() {
  currentProjectId = null;
  currentProject   = null;
  const grid  = document.getElementById('projects-grid');
  const empty = document.getElementById('home-empty');
  grid.innerHTML = '<p style="color:var(--muted);font-size:.875rem">Carregando...</p>';

  try {
    const projects = await api.get('/api/projects');
    grid.innerHTML = '';
    if (projects.length === 0) {
      empty.classList.remove('hidden');
    } else {
      empty.classList.add('hidden');
      projects.forEach(p => grid.insertAdjacentHTML('beforeend', projectCard(p)));
    }
  } catch (e) {
    grid.innerHTML = `<p style="color:var(--red)">${e.message}</p>`;
  }
}

function projectCard(p) {
  const date = p.updated_at ? new Date(p.updated_at).toLocaleDateString('pt-BR') : '';
  const logoHtml = p.has_logo
    ? `<img class="project-card-logo" src="/projects-data/${p.id}/logo.png" onerror="this.style.display='none'" alt=""/>`
    : `<div class="project-card-icon"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg></div>`;
  return `
    <div class="project-card" onclick="navigate('editor','${p.id}')">
      ${logoHtml}
      <h3>${esc(p.company_name)}</h3>
      ${p.cnpj ? `<p class="cnpj">${esc(p.cnpj)}</p>` : ''}
      <div class="project-card-meta">
        <span class="badge badge-blue">${p.product_count} produto${p.product_count !== 1 ? 's' : ''}</span>
        ${date ? `<span class="badge badge-gray">${date}</span>` : ''}
      </div>
    </div>`;
}

/* ── Modal: Novo Projeto ─────────────────────────────── */
function openNewProjectModal() {
  document.getElementById('modal-backdrop').classList.remove('hidden');
  document.getElementById('modal-new-project').classList.remove('hidden');
  document.getElementById('modal-name').focus();
}

function closeModal() {
  document.getElementById('modal-backdrop').classList.add('hidden');
  document.getElementById('modal-new-project').classList.add('hidden');
  document.getElementById('form-new-project').reset();
  document.getElementById('modal-logo-preview').classList.add('hidden');
  document.getElementById('modal-logo-placeholder').classList.remove('hidden');
}

document.getElementById('modal-logo-input').addEventListener('change', function () {
  const file = this.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('modal-logo-preview');
    img.src = e.target.result;
    img.classList.remove('hidden');
    document.getElementById('modal-logo-placeholder').classList.add('hidden');
  };
  reader.readAsDataURL(file);
});

async function submitNewProject(e) {
  e.preventDefault();
  const name = document.getElementById('modal-name').value.trim();
  const cnpj = document.getElementById('modal-cnpj').value.trim();
  const logoFile = document.getElementById('modal-logo-input').files[0];

  const fd = new FormData();
  fd.append('name', name);
  fd.append('cnpj', cnpj);
  if (logoFile) fd.append('logo', logoFile);

  try {
    const res = await api.post('/api/projects', fd);
    closeModal();
    navigate('editor', res.id);
  } catch (err) {
    toast('Erro ao criar projeto: ' + err.message, 'error');
  }
}

/* ══ EDITOR ════════════════════════════════════════════════ */

async function loadEditor(id) {
  currentProjectId = id;
  try {
    currentProject = await api.get(`/api/projects/${id}`);
    renderEditor();
    // Check if a search is already running
    pollIfSearching();
  } catch (e) {
    toast('Erro ao carregar projeto: ' + e.message, 'error');
  }
}

function renderEditor() {
  const p = currentProject;

  // Header
  document.getElementById('editor-title').textContent = p.company.name || 'Sem nome';

  // Company fields
  document.getElementById('field-name').value = p.company.name || '';
  document.getElementById('field-cnpj').value  = p.company.cnpj || '';

  // Logo
  if (p.company.logo_path) {
    const logoSrc = `/projects-data/${p.id}/logo.png`;
    const logoImg = document.getElementById('logo-preview');
    logoImg.src = logoSrc;
    logoImg.onerror = () => {
      // Try other extensions
      logoImg.onerror = null;
      const ext = p.company.logo_path.split('.').pop();
      logoImg.src = `/projects-data/${p.id}/logo.${ext}`;
    };
    logoImg.classList.remove('hidden');
    document.getElementById('logo-placeholder').classList.add('hidden');
  }

  renderProducts();
  updateStats();
}

function renderProducts() {
  const grid  = document.getElementById('products-grid');
  const empty = document.getElementById('products-empty');
  const products = currentProject.products || [];

  grid.innerHTML = '';
  if (products.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  products.forEach(p => grid.insertAdjacentHTML('beforeend', productCard(p)));
}

function productCard(p) {
  const imgSrc = p.image_path
    ? `/projects-data/${currentProjectId}/images/product_${String(p.number).padStart(3,'0')}.jpg`
    : '';

  const statusClass = p.custom_image ? 'status-custom' : (p.image_path ? 'status-ok' : 'status-none');

  return `
    <div class="product-card" id="pcard-${p.number}">
      <div class="product-img-wrap" onclick="triggerImageReplace(${p.number})">
        <span class="product-num-badge">#${p.number}</span>
        <span class="product-img-status ${statusClass}" title="${p.custom_image ? 'Imagem personalizada' : (p.image_path ? 'Imagem encontrada' : 'Sem imagem')}"></span>
        ${imgSrc
          ? `<img src="${imgSrc}?t=${Date.now()}" alt="" onerror="this.src=''" />`
          : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
               <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
             </div>`
        }
        <div class="product-img-overlay">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
          Trocar imagem
        </div>
      </div>
      <button class="product-delete" onclick="deleteProduct(event,${p.number})" title="Remover produto">×</button>
      <div class="product-body">
        <p class="product-desc">${esc(p.description)}</p>
        ${p.reference && p.reference !== 'S/N' ? `<span class="product-ref">Ref: ${esc(p.reference)}</span>` : ''}
      </div>
    </div>`;
}

function updateStats() {
  const products = currentProject.products || [];
  document.getElementById('stat-total').textContent = products.length;
  document.getElementById('stat-with-image').textContent = products.filter(p => p.image_path).length;
}

/* ── Save company info ───────────────────────────────── */
async function saveProject() {
  const name = document.getElementById('field-name').value.trim();
  const cnpj = document.getElementById('field-cnpj').value.trim();
  try {
    await api.put(`/api/projects/${currentProjectId}/company`, { name, cnpj });
    document.getElementById('editor-title').textContent = name || 'Sem nome';
    currentProject.company.name = name;
    currentProject.company.cnpj = cnpj;
    toast('Projeto salvo!', 'success');
  } catch (e) {
    toast('Erro ao salvar: ' + e.message, 'error');
  }
}

/* ── Logo upload (in editor) ─────────────────────────── */
document.getElementById('logo-input').addEventListener('change', async function () {
  const file = this.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('logo', file);
  try {
    const res = await api.post(`/api/projects/${currentProjectId}/logo`, fd);
    const img = document.getElementById('logo-preview');
    img.src = res.logo_url + '?t=' + Date.now();
    img.classList.remove('hidden');
    document.getElementById('logo-placeholder').classList.add('hidden');
    toast('Logo atualizado!', 'success');
  } catch (e) {
    toast('Erro ao enviar logo: ' + e.message, 'error');
  }
});

/* ── Add products from TXT ────────────────────────────── */
document.getElementById('txt-input').addEventListener('change', async function () {
  const files = Array.from(this.files);
  if (!files.length) return;
  let totalAdded = 0;
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post(`/api/projects/${currentProjectId}/products/add-txt`, fd);
      totalAdded += res.added;
    } catch (e) {
      toast(`Erro ao importar ${file.name}: ${e.message}`, 'error');
    }
  }
  currentProject = await api.get(`/api/projects/${currentProjectId}`);
  renderProducts();
  updateStats();
  if (totalAdded > 0) {
    toast(`${totalAdded} produto(s) adicionado(s)!`, 'success');
  } else {
    toast('Nenhum produto novo encontrado no arquivo.', 'error');
  }
  this.value = '';
});

/* ── Paste area ──────────────────────────────────────── */
function togglePasteArea() {
  const area = document.getElementById('paste-area');
  const isHidden = area.classList.contains('hidden');
  area.classList.toggle('hidden', !isHidden);
  if (isHidden) {
    document.getElementById('paste-textarea').focus();
  } else {
    document.getElementById('paste-textarea').value = '';
    document.getElementById('paste-preview').classList.add('hidden');
  }
}

async function previewPaste() {
  const text = document.getElementById('paste-textarea').value.trim();
  if (!text) { toast('Cole algum texto primeiro.', 'error'); return; }
  try {
    const res = await api.post(`/api/projects/${currentProjectId}/products/preview-text`, { text });
    const preview = document.getElementById('paste-preview');
    preview.classList.remove('hidden');
    const items = res.preview.map(p =>
      `<div class="preview-item">#${p.number} — ${esc(p.description)}</div>`
    ).join('');
    const more = res.count > 5 ? `<div class="preview-item" style="color:var(--blue)">…e mais ${res.count - 5} produto(s)</div>` : '';
    preview.innerHTML = `<div class="preview-count">${res.count} produto(s) detectado(s)</div>${items}${more}`;
  } catch (e) {
    toast('Erro: ' + e.message, 'error');
  }
}

async function importPaste() {
  const text = document.getElementById('paste-textarea').value.trim();
  if (!text) { toast('Cole algum texto primeiro.', 'error'); return; }
  const btn = document.getElementById('btn-import-paste');
  btn.disabled = true;
  try {
    const res = await api.post(`/api/projects/${currentProjectId}/products/add-text`, { text });
    toast(`${res.added} produto(s) adicionado(s)!`, 'success');
    currentProject = await api.get(`/api/projects/${currentProjectId}`);
    renderProducts();
    updateStats();
    // Reset paste area
    document.getElementById('paste-textarea').value = '';
    document.getElementById('paste-preview').classList.add('hidden');
    document.getElementById('paste-area').classList.add('hidden');
  } catch (e) {
    toast('Erro ao importar: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

/* ── Delete product ──────────────────────────────────── */
async function deleteProduct(e, num) {
  e.stopPropagation();
  if (!confirm(`Remover produto #${num}?`)) return;
  try {
    await api.del(`/api/projects/${currentProjectId}/products/${num}`);
    currentProject.products = currentProject.products.filter(p => p.number !== num);
    document.getElementById(`pcard-${num}`)?.remove();
    updateStats();
    toast('Produto removido.', 'success');
  } catch (err) {
    toast('Erro: ' + err.message, 'error');
  }
}

/* ── Image replacement ───────────────────────────────── */
function triggerImageReplace(productNum) {
  pendingReplaceNum = productNum;
  document.getElementById('image-replace-input').click();
}

document.getElementById('image-replace-input').addEventListener('change', async function () {
  const file = this.files[0];
  if (!file || pendingReplaceNum == null) return;
  const num = pendingReplaceNum;
  pendingReplaceNum = null;

  const fd = new FormData();
  fd.append('image', file);
  try {
    const res = await api.post(
      `/api/projects/${currentProjectId}/products/${num}/image`,
      fd,
    );
    // Update in memory
    const prod = currentProject.products.find(p => p.number === num);
    if (prod) { prod.image_path = res.image_url; prod.custom_image = true; }

    // Re-render just this card
    const card = document.getElementById(`pcard-${num}`);
    if (card) card.outerHTML = productCard(prod);
    updateStats();
    toast('Imagem atualizada!', 'success');
  } catch (e) {
    toast('Erro ao enviar imagem: ' + e.message, 'error');
  }
  this.value = '';
});

/* ── Image search ────────────────────────────────────── */
async function startImageSearch() {
  const btn = document.getElementById('btn-search');
  btn.disabled = true;
  try {
    const res = await api.post(`/api/projects/${currentProjectId}/search-images`, {});
    if (res.status === 'already_running') {
      toast('Busca já em andamento…');
    } else {
      toast('Busca iniciada!');
    }
    showSearchProgress();
    startPolling();
  } catch (e) {
    btn.disabled = false;
    toast('Erro: ' + e.message, 'error');
  }
}

function showSearchProgress() {
  document.getElementById('search-progress-wrap').classList.remove('hidden');
}

function startPolling() {
  if (searchPollTimer) clearInterval(searchPollTimer);
  searchPollTimer = setInterval(pollSearchProgress, 2000);
}

async function pollSearchProgress() {
  if (pollSearchProgress._running) return;
  pollSearchProgress._running = true;
  try {
    const prog = await api.get(`/api/projects/${currentProjectId}/search-progress`);
    const pct = prog.total > 0 ? (prog.done / prog.total) * 100 : 0;

    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('progress-text').textContent = `${prog.done} / ${prog.total}`;
    document.getElementById('progress-current').textContent = prog.current || '';

    if (prog.status === 'done' || prog.status === 'idle') {
      clearInterval(searchPollTimer);
      searchPollTimer = null;
      document.getElementById('btn-search').disabled = false;

      if (prog.status === 'done') {
        // Reload first — toast only after success
        currentProject = await api.get(`/api/projects/${currentProjectId}`);
        renderProducts();
        updateStats();
        toast('Busca concluída! ' + currentProject.products.filter(p => p.image_path).length + ' imagens encontradas.', 'success');
      }
    }
  } catch (e) {
    toast('Erro ao verificar progresso: ' + e.message, 'error');
  } finally {
    pollSearchProgress._running = false;
  }
}

function pollIfSearching() {
  // Check immediately if a search is running when loading the editor
  api.get(`/api/projects/${currentProjectId}/search-progress`).then(prog => {
    if (prog.status === 'running') {
      showSearchProgress();
      document.getElementById('btn-search').disabled = true;
      startPolling();
    }
  }).catch(() => {});
}

/* ── Export report ───────────────────────────────────── */
async function exportReport() {
  // Auto-save company info first
  await saveProject();
  try {
    const url = `/api/projects/${currentProjectId}/export`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    a.click();
    toast('Relatório exportado!', 'success');
  } catch (e) {
    toast('Erro ao exportar: ' + e.message, 'error');
  }
}

/* ── Utilities ───────────────────────────────────────── */
function esc(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Init ────────────────────────────────────────────── */
navigate('home');
