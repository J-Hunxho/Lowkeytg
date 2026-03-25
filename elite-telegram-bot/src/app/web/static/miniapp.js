const state = {
  tg: window.Telegram?.WebApp,
  user: null,
  catalog: [],
  filtered: [],
  categories: [],
  selectedCategory: 'all',
  account: null,
  dashboard: null,
};

function formatMoney(item) {
  if (!item.unit_amount || !item.currency) return 'Configured in Stripe';
  return `${(item.unit_amount / 100).toFixed(2)} ${item.currency.toUpperCase()}`;
}

function el(id) { return document.getElementById(id); }

function setStatus(text, cls='loading') {
  const root = el('market-grid');
  root.innerHTML = `<div class="${cls}">${text}</div>`;
}

function renderHero() {
  el('hero-user').textContent = state.user
    ? `Welcome @${state.user.username || state.user.first_name || state.user.id}`
    : 'Preview mode (outside Telegram)';
}

function renderFilters() {
  const root = el('filters');
  root.innerHTML = '';
  const items = ['all', ...state.categories];
  items.forEach((c) => {
    const b = document.createElement('button');
    b.textContent = c === 'all' ? 'All' : c;
    b.onclick = () => {
      state.selectedCategory = c;
      applyFilters();
    };
    root.appendChild(b);
  });
}

function applyFilters() {
  state.filtered = state.catalog.filter((i) => state.selectedCategory === 'all' || i.category === state.selectedCategory);
  renderMarket();
  renderPlans();
}

function openDrawer(item) {
  const drawer = el('detail-drawer');
  drawer.classList.add('open');
  el('drawer-title').textContent = item.title;
  el('drawer-desc').textContent = item.description || 'No description yet.';
  el('drawer-price').textContent = formatMoney(item);
  el('drawer-meta').textContent = `${item.sku} · ${item.purchase_type || 'one_time'} · ${item.category || 'general'}`;
  el('drawer-buy').onclick = () => beginCheckout(item);
}

function closeDrawer() { el('detail-drawer').classList.remove('open'); }

async function beginCheckout(item) {
  if (!state.user?.id) {
    alert('Open inside Telegram to purchase.');
    return;
  }
  try {
    const payload = {
      sku: item.sku,
      telegram_id: state.user.id,
      success_url: `${location.origin}/payments/success`,
      cancel_url: `${location.origin}/payments/cancel`,
    };
    const res = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `checkout failed (${res.status})`);
    }
    const data = await res.json();
    window.open(data.url, '_blank');
    state.tg?.HapticFeedback?.notificationOccurred('success');
  } catch (err) {
    state.tg?.HapticFeedback?.notificationOccurred('error');
    alert(`Checkout failed: ${err.message}`);
  }
}

function renderMarket() {
  const root = el('market-grid');
  if (!state.filtered.length) return setStatus('No products match this filter.', 'empty');
  root.innerHTML = '';
  state.filtered.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <h3>${item.title}</h3>
      <p>${item.description || ''}</p>
      <div class="price">${formatMoney(item)}</div>
      <div class="meta">
        ${item.featured ? '<span class="badge featured">Featured</span>' : ''}
        <span>${item.purchase_type || 'one_time'}</span>
        <span>${item.recurring_interval || 'one-time'}</span>
      </div>
      <div class="actions">
        <button class="secondary" data-detail="${item.sku}">Details</button>
        <button class="buy" data-buy="${item.sku}">${item.button_label || 'Buy'}</button>
      </div>
    `;
    card.querySelector('[data-detail]').onclick = () => openDrawer(item);
    card.querySelector('[data-buy]').onclick = () => beginCheckout(item);
    root.appendChild(card);
  });
}

function renderPlans() {
  const plans = state.filtered.filter((p) => p.purchase_type === 'recurring');
  const root = el('plans-grid');
  root.innerHTML = '';
  if (!plans.length) {
    root.innerHTML = '<div class="empty">No subscription plans yet.</div>';
    return;
  }
  plans.forEach((p) => {
    const n = document.createElement('div');
    n.className = 'card';
    n.innerHTML = `<h3>${p.title}</h3><p>${p.description || ''}</p><div class="price">${formatMoney(p)}</div><button class="buy">Choose Plan</button>`;
    n.querySelector('button').onclick = () => beginCheckout(p);
    root.appendChild(n);
  });
}

function renderFeatured() {
  const featured = state.catalog.filter((i) => i.featured).slice(0, 4);
  const root = el('featured-grid');
  root.innerHTML = '';
  if (!featured.length) {
    root.innerHTML = '<div class="empty">No featured offers yet.</div>';
    return;
  }
  featured.forEach((f) => {
    const n = document.createElement('div');
    n.className = 'card';
    n.innerHTML = `<h3>${f.title}</h3><p>${f.description || ''}</p><div class="price">${formatMoney(f)}</div><button class="buy">${f.button_label || 'Buy now'}</button>`;
    n.querySelector('button').onclick = () => beginCheckout(f);
    root.appendChild(n);
  });
}

function renderAccount() {
  if (!state.account) return;
  el('orders-count').textContent = state.account.orders_count;
  el('subs-count').textContent = state.account.subscriptions_count;
  el('access-count').textContent = state.account.active_access_count;
  el('account-note').textContent = state.account.is_admin
    ? 'Admin detected: control panel loaded below.'
    : 'User account detected.';
  const ai = state.account.ai || {};
  el('ai-status').textContent = `Tier: ${ai.tier || 'free'} · Used today: ${ai.used_today || 0}/${ai.daily_limit || 0} · Remaining: ${ai.remaining_today || 0}`;

  const adminActions = el('admin-actions');
  if (!state.account.is_admin) {
    adminActions.innerHTML = '';
    return;
  }

  adminActions.innerHTML = `
    <button class="secondary" id="btn-sync">Sync products</button>
    <button class="secondary" id="btn-settings">Load settings</button>
    <button class="secondary" id="btn-dashboard">Refresh Admin Panel</button>
  `;

  el('btn-sync').onclick = async () => {
    const res = await fetch('/admin/sync-products', { method: 'POST', headers: { 'X-Admin-Telegram-Id': state.user.id } });
    const data = await res.json().catch(() => ({}));
    alert(res.ok ? `Synced: ${data.synced}` : `Sync failed: ${data.detail || res.status}`);
  };
  el('btn-settings').onclick = async () => {
    const res = await fetch('/api/admin/settings', { headers: { 'X-Admin-Telegram-Id': state.user.id } });
    const data = await res.json().catch(() => ({}));
    alert(res.ok ? `Settings keys: ${(data.items || []).map((i)=>i.key).join(', ') || 'none'}` : `Failed: ${data.detail || res.status}`);
  };
  el('btn-dashboard').onclick = loadDashboard;

  loadDashboard();
}

async function sendAI() {
  if (!state.user?.id) return alert('Open inside Telegram to use AI.');
  const prompt = (el('ai-prompt').value || '').trim();
  if (!prompt) return;
  const responseNode = el('ai-response');
  responseNode.textContent = 'Processing...';
  const res = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: state.user.id, prompt }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    responseNode.textContent = `Error: ${data.detail || res.status}`;
    return;
  }
  responseNode.textContent = `${data.reply}\n\nModel: ${data.model} · Tier: ${data.tier}`;
  await loadAccount();
  renderAccount();
}

async function loadDashboard() {
  if (!state.user?.id) return;
  const res = await fetch('/api/admin/dashboard', { headers: { 'X-Admin-Telegram-Id': state.user.id } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return;
  state.dashboard = data;
  renderAdminPanel();
}

function renderAdminPanel() {
  if (!state.dashboard || !state.account?.is_admin) return;
  let panel = document.getElementById('admin-panel');
  if (!panel) {
    panel = document.createElement('section');
    panel.id = 'admin-panel';
    panel.className = 'section';
    panel.innerHTML = '<h2>Admin Control Panel</h2><div id="admin-body"></div>';
    document.querySelector('.wrap').appendChild(panel);
  }

  const rows = (state.dashboard.products || []).slice(0, 12).map((p) => `
    <div class="card">
      <h3>${p.title}</h3>
      <div class="meta"><span>${p.sku}</span><span>${p.category || 'general'}</span></div>
      <div class="actions">
        <button class="secondary" data-feature="${p.sku}">${p.featured ? 'Unfeature' : 'Feature'}</button>
        <button class="secondary" data-visibility="${p.sku}">${p.active ? 'Hide' : 'Show'}</button>
      </div>
    </div>`).join('');

  document.getElementById('admin-body').innerHTML = `
    <p class="notice">Sync runs: ${(state.dashboard.sync_runs || []).length} · Events: ${(state.dashboard.events || []).length}</p>
    <div class="grid">${rows || '<div class="empty">No products</div>'}</div>
    <div class="actions" style="margin-top:8px;">
      <button class="secondary" id="maintenance-toggle">Toggle Maintenance</button>
      <button class="secondary" id="public-toggle">Toggle Public Visibility</button>
    </div>
  `;

  document.querySelectorAll('[data-feature]').forEach((btn) => {
    btn.onclick = () => updateProduct(btn.dataset.feature, { featured: !btn.textContent.includes('Unfeature') });
  });
  document.querySelectorAll('[data-visibility]').forEach((btn) => {
    btn.onclick = () => updateProduct(btn.dataset.visibility, { active: !btn.textContent.includes('Hide') });
  });
  document.getElementById('maintenance-toggle').onclick = () => updateSetting('maintenance_mode', !(state.dashboard.settings?.maintenance_mode || false));
  document.getElementById('public-toggle').onclick = () => updateSetting('public_visibility', !(state.dashboard.settings?.public_visibility || false));
}

async function updateProduct(sku, payload) {
  const res = await fetch(`/api/admin/products/${sku}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Telegram-Id': state.user.id },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return alert('Failed to update product');
  await loadDashboard();
  await loadCatalog();
  applyFilters();
}

async function updateSetting(key, value) {
  const res = await fetch(`/api/admin/settings/${key}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Telegram-Id': state.user.id },
    body: JSON.stringify(value),
  });
  if (!res.ok) return alert('Failed to update setting');
  await loadDashboard();
  await loadCatalog();
  applyFilters();
}

async function loadCatalog() {
  const r = await fetch('/api/catalog');
  if (!r.ok) throw new Error('catalog endpoint failed');
  const data = await r.json();
  state.catalog = data.items || [];
  state.categories = [...new Set(state.catalog.map((i) => i.category).filter(Boolean))];
}

async function loadAccount() {
  if (!state.user?.id) return;
  const r = await fetch(`/api/account/state?telegram_id=${state.user.id}`);
  if (!r.ok) return;
  state.account = await r.json();
}

async function init() {
  state.tg?.ready();
  state.tg?.expand();
  state.user = state.tg?.initDataUnsafe?.user || null;
  renderHero();
  try {
    setStatus('Loading marketplace…', 'loading');
    await Promise.all([loadCatalog(), loadAccount()]);
    renderFilters();
    applyFilters();
    renderFeatured();
    renderAccount();
    el('ai-send').onclick = sendAI;
  } catch (err) {
    setStatus(`Failed to load catalog: ${err.message}`, 'error');
  }
}

window.addEventListener('DOMContentLoaded', init);
window.closeDrawer = closeDrawer;
