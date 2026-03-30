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

const TIER_ORDER = ['lowkey_entry', 'lowkey_select', 'lowkey_circle'];
const TIER_LABELS = {
  lowkey_entry: 'Lowkey Entry',
  lowkey_select: 'Lowkey Select',
  lowkey_circle: 'Lowkey Circle',
};

function el(id) { return document.getElementById(id); }
function formatMoney(item) {
  if (!item.unit_amount || !item.currency) return 'Configured in Stripe';
  return `${(item.unit_amount / 100).toFixed(2)} ${item.currency.toUpperCase()}`;
}

function setStatus(text, cls = 'loading') {
  el('market-grid').innerHTML = `<div class="${cls}">${text}</div>`;
}

function renderHero() {
  const label = state.user
    ? `Welcome ${state.user.first_name || state.user.username || 'member'} · private mode active`
    : 'Preview mode — open inside Telegram for live checkout and member state.';
  el('hero-user').textContent = label;
}

function renderFilters() {
  const root = el('filters');
  root.innerHTML = '';
  ['all', ...state.categories].forEach((category) => {
    const b = document.createElement('button');
    b.className = 'secondary';
    b.textContent = category === 'all' ? 'All Access' : category;
    b.onclick = () => {
      state.selectedCategory = category;
      applyFilters();
    };
    root.appendChild(b);
  });
}

function applyFilters() {
  state.filtered = state.catalog.filter((item) => state.selectedCategory === 'all' || item.category === state.selectedCategory);
  renderMarket();
  renderPlans();
}

function openDrawer(item) {
  el('detail-drawer').classList.add('open');
  el('drawer-title').textContent = item.title;
  el('drawer-desc').textContent = item.description || 'No description available.';
  el('drawer-price').textContent = formatMoney(item);
  el('drawer-meta').textContent = `${item.sku} · ${item.purchase_type || 'one_time'} · ${item.category || 'general'}`;
  el('drawer-buy').onclick = () => beginCheckout(item);
}

function closeDrawer() {
  el('detail-drawer').classList.remove('open');
}

async function beginCheckout(item) {
  if (!state.user?.id) return alert('Open this mini app inside Telegram to continue.');
  try {
    const response = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sku: item.sku,
        telegram_id: state.user.id,
        success_url: `${location.origin}/payments/success`,
        cancel_url: `${location.origin}/payments/cancel`,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `checkout failed (${response.status})`);
    window.open(payload.url, '_blank');
    state.tg?.HapticFeedback?.notificationOccurred('success');
  } catch (error) {
    state.tg?.HapticFeedback?.notificationOccurred('error');
    alert(`Checkout unavailable: ${error.message}`);
  }
}

function renderCatalogCards(items, nodeId, emptyText) {
  const root = el(nodeId);
  root.innerHTML = '';
  if (!items.length) {
    root.innerHTML = `<div class="empty">${emptyText}</div>`;
    return;
  }
  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <h3>${item.title}</h3>
      <p>${item.description || ''}</p>
      <div class="price">${formatMoney(item)}</div>
      <div class="meta">
        ${item.featured ? '<span class="badge">Featured</span>' : ''}
        <span>${item.recurring_interval || 'one-time'}</span>
      </div>
      <div class="actions">
        <button class="secondary" data-detail="${item.sku}">Details</button>
        <button class="buy" data-buy="${item.sku}">${item.button_label || 'Secure Access'}</button>
      </div>
    `;
    card.querySelector('[data-detail]').onclick = () => openDrawer(item);
    card.querySelector('[data-buy]').onclick = () => beginCheckout(item);
    root.appendChild(card);
  });
}

function renderMarket() {
  renderCatalogCards(state.filtered, 'market-grid', 'No access drops are available for this category yet.');
}

function renderPlans() {
  const recurring = state.catalog.filter((item) => item.purchase_type === 'recurring');
  const sorted = recurring.sort((a, b) => {
    const ai = TIER_ORDER.indexOf(String(a.sku).toLowerCase());
    const bi = TIER_ORDER.indexOf(String(b.sku).toLowerCase());
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  }).map((item) => ({ ...item, title: TIER_LABELS[String(item.sku).toLowerCase()] || item.title }));
  renderCatalogCards(sorted, 'plans-grid', 'Membership tiers will appear after catalog sync.');
}

function renderFeatured() {
  const featured = state.catalog.filter((item) => item.featured).slice(0, 4);
  renderCatalogCards(featured, 'featured-grid', 'Priority releases are being prepared.');
}

function renderAccount() {
  if (!state.account) return;
  el('orders-count').textContent = state.account.orders_count;
  el('subs-count').textContent = state.account.subscriptions_count;
  el('access-count').textContent = state.account.active_access_count;
  el('account-note').textContent = state.account.is_admin
    ? 'Admin session detected · operator controls enabled.'
    : `Member profile loaded · streak ${state.account.streak_days || 0} day(s) · ${state.account.badges?.join(', ') || 'no badges yet'}.`;

  const ai = state.account.ai || {};
  el('ai-status').textContent = `Tier: ${ai.tier || 'free'} · Daily usage: ${ai.used_today || 0}/${ai.daily_limit || 0}`;

  const admin = el('admin-actions');
  if (!state.account.is_admin) {
    admin.innerHTML = '';
    return;
  }
  admin.innerHTML = `<button class="secondary" id="btn-sync">Sync Stripe Catalog</button>`;
  el('btn-sync').onclick = async () => {
    const response = await fetch('/admin/sync-products', { method: 'POST', headers: { 'X-Admin-Telegram-Id': state.user.id } });
    const payload = await response.json().catch(() => ({}));
    alert(response.ok ? `Catalog synced: ${payload.synced}` : `Sync failed: ${payload.detail || response.status}`);
  };
}

async function sendAI() {
  if (!state.user?.id) return alert('Open in Telegram for AI access.');
  const prompt = (el('ai-prompt').value || '').trim();
  if (!prompt) return;
  const out = el('ai-response');
  out.textContent = 'AI concierge is preparing your response…';
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: state.user.id, prompt }),
  });
  const payload = await response.json().catch(() => ({}));
  out.textContent = response.ok
    ? `${payload.reply}\n\nModel: ${payload.model} · Tier: ${payload.tier}`
    : `Unable to respond: ${payload.detail || response.status}`;
  await loadAccount();
  renderAccount();
}

async function loadCatalog() {
  const response = await fetch('/api/catalog');
  if (!response.ok) throw new Error('catalog endpoint failed');
  const payload = await response.json();
  state.catalog = payload.items || [];
  state.categories = [...new Set(state.catalog.map((item) => item.category).filter(Boolean))];
}

async function loadAccount() {
  if (!state.user?.id) return;
  const response = await fetch(`/api/account/state?telegram_id=${state.user.id}`);
  if (!response.ok) return;
  state.account = await response.json();
}

function bindHeroActions() {
  el('hero-shop').onclick = () => document.getElementById('marketplace').scrollIntoView({ behavior: 'smooth' });
  el('hero-plans').onclick = () => document.getElementById('plans-grid').scrollIntoView({ behavior: 'smooth' });
}

async function init() {
  state.tg?.ready();
  state.tg?.expand();
  state.user = state.tg?.initDataUnsafe?.user || null;
  renderHero();
  bindHeroActions();

  try {
    setStatus('Loading access drops…', 'loading');
    await Promise.all([loadCatalog(), loadAccount()]);
    renderFilters();
    applyFilters();
    renderFeatured();
    renderAccount();
    el('ai-send').onclick = sendAI;
  } catch (error) {
    setStatus(`Unable to load catalog: ${error.message}`, 'error');
  }
}

window.addEventListener('DOMContentLoaded', init);
window.closeDrawer = closeDrawer;
