const API = (location.protocol === 'http:' && location.port === '5050') ? '/api' : 'http://127.0.0.1:5050/api';
const PAL = ['#f5a623', '#38bdf8', '#34d399', '#a78bfa', '#f87171', '#fbbf24', '#60a5fa', '#f472b6'];
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const inr = n => '₹' + Math.round(n || 0).toLocaleString('en-IN');
let editing = null, DEMO = false, charts = {};

async function api(path, opts = {}) {
  const t = performance.now(); let ok, status, data;
  if (DEMO) { const r = await window.demoApi(path, opts); status = r.status; ok = status < 400; data = r.data; }
  else {
    const res = await fetch(API + path, { ...opts, headers: { 'Content-Type': 'application/json' }, body: opts.body ? JSON.stringify(opts.body) : undefined });
    ok = res.ok; status = res.status; data = await res.json().catch(() => ({}));
  }
  if (data.query) { $('#q').textContent = data.query; $('#ms').textContent = (performance.now() - t).toFixed(0) + ' ms'; }
  if (!ok) throw new Error(data.error || 'Request failed (' + status + ')');
  return data;
}
function toast(msg, bad) { const t = $('#toast'); t.textContent = msg; t.className = 'show' + (bad ? ' bad' : ''); clearTimeout(t._h); t._h = setTimeout(() => t.className = '', 2800); }
async function run(fn) { try { await fn(); } catch (e) { toast(e.message, true); } }
function killCharts() { Object.values(charts).forEach(c => c.destroy()); charts = {}; }
function mk(id, cfg) {
  if (!window.Chart) return;
  Chart.defaults.color = '#9aa6bd'; Chart.defaults.borderColor = '#2a3f66'; Chart.defaults.font.family = '"Segoe UI", sans-serif';
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false }, cfg.options || {});
  charts[id] = new Chart($('#' + id), cfg);
}
const growth = g => g == null ? '<span class="up">new</span>' : `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '▲' : '▼'} ${Math.abs(g)}% vs previous period</span>`;
const rupeeAxis = { ticks: { callback: v => '₹' + (v >= 1000 ? v / 1000 + 'k' : v) } };

const views = {
  async dashboard(v) {
    v.innerHTML = `<div class="bar"><b>Period:</b><select id="days"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="60">Last 60 days</option></select></div>
      <div class="grid g4" id="kpis"></div><div class="grid g3" style="margin-top:16px">
      <div class="card span2"><h2>Revenue and profit per day</h2><div class="chart"><canvas id="c-line"></canvas></div></div>
      <div class="card"><h2>Payment methods</h2><div class="chart"><canvas id="c-pay"></canvas></div></div>
      <div class="card"><h2>Revenue by category</h2><div class="chart"><canvas id="c-cat"></canvas></div></div>
      <div class="card"><h2>Top products by revenue</h2><div class="chart"><canvas id="c-top"></canvas></div></div>
      <div class="card"><h2>Peak hours (orders)</h2><div class="chart"><canvas id="c-hour"></canvas></div></div>
      <div class="card"><h2>Sales by weekday</h2><div class="chart"><canvas id="c-wd"></canvas></div></div>
      <div class="card"><h2>Restock soon</h2><div id="low"></div></div>
      <div class="card"><h2>Best customers</h2><div id="best"></div></div></div>`;
    const load = async () => {
      killCharts(); const a = await api('/analytics?days=' + $('#days').value), k = a.kpis;
      $('#kpis').innerHTML = [['Revenue', inr(k.revenue), growth(a.growth.revenue)], ['Profit', inr(k.profit), `<span class="up">${k.margin}% margin</span>`],
        ['Orders', k.orders.toLocaleString('en-IN'), growth(a.growth.orders)], ['Average order', inr(k.aov), `<span style="color:var(--mute)">${k.units.toLocaleString('en-IN')} items sold</span>`]]
        .map(([l, val, sub]) => `<div class="card stat"><span>${l}</span><b>${val}</b>${sub}</div>`).join('');
      if (!k.orders) { $('#low').innerHTML = $('#best').innerHTML = '<div class="empty">No orders in this period. Try Tools > Load sample data.</div>'; return; }
      const d = a.daily;
      mk('c-line', { type: 'line', data: { labels: d.labels.map(x => x.slice(5)), datasets: [
        { label: 'Revenue', data: d.revenue, borderColor: PAL[0], backgroundColor: 'rgba(245,166,35,.15)', fill: true, tension: .3, pointRadius: 0 },
        { label: 'Profit', data: d.profit, borderColor: PAL[2], tension: .3, pointRadius: 0 }] },
        options: { interaction: { mode: 'index', intersect: false }, scales: { y: rupeeAxis, x: { ticks: { maxTicksLimit: 10 } } }, plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${inr(c.parsed.y)}` } } } } });
      const money = { plugins: { tooltip: { callbacks: { label: c => `${c.label}: ${inr(c.parsed)}` } }, legend: { position: 'bottom' } } };
      mk('c-pay', { type: 'doughnut', data: { labels: a.payment.labels, datasets: [{ data: a.payment.values, backgroundColor: PAL, borderWidth: 0 }] }, options: money });
      mk('c-cat', { type: 'doughnut', data: { labels: a.category.labels, datasets: [{ data: a.category.values, backgroundColor: PAL, borderWidth: 0 }] }, options: money });
      mk('c-top', { type: 'bar', data: { labels: a.top_products.labels, datasets: [{ data: a.top_products.values, backgroundColor: PAL[1] }] },
        options: { indexAxis: 'y', scales: { x: rupeeAxis }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => inr(c.parsed.x), afterLabel: c => a.top_products.units[c.dataIndex] + ' sold' } } } } });
      mk('c-hour', { type: 'bar', data: { labels: a.hours.labels, datasets: [{ data: a.hours.values, backgroundColor: PAL[3] }] }, options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { maxRotation: 60 } } } } });
      mk('c-wd', { type: 'bar', data: { labels: a.weekday.labels, datasets: [{ data: a.weekday.values, backgroundColor: a.weekday.labels.map((_, i) => i > 4 ? PAL[0] : PAL[1]) }] },
        options: { scales: { y: rupeeAxis }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => inr(c.parsed.y) } } } } });
      $('#low').innerHTML = a.low_stock.length ? `<table>${a.low_stock.map(p => `<tr><td>${esc(p.name)}</td><td><span class="tag hot">${p.stock} left</span></td></tr>`).join('')}</table><p style="color:var(--mute);font-size:12px">Stock value: ${inr(a.inventory_value)}</p>` : '<span class="tag good">All products above reorder level</span>';
      $('#best').innerHTML = a.top_customers.length ? `<table>${a.top_customers.map(c => `<tr><td>${esc(c.name)}</td><td><b>${inr(c.spent)}</b></td></tr>`).join('')}</table>` : '<div class="empty">No customer orders yet</div>';
    };
    $('#days').onchange = () => run(load); await load();
  },

  async products(v) {
    v.innerHTML = `<div class="bar"><input id="f-q" placeholder="Search product…"><select id="f-cat"><option value="">All categories</option></select>
      <label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="f-low"> Low stock only</label><button class="btn" id="add">＋ Add product</button></div><div id="form"></div><div class="card" id="list"></div>`;
    const load = async () => {
      const p = new URLSearchParams({ q: $('#f-q').value, category: $('#f-cat').value, low: $('#f-low').checked ? '1' : '' });
      for (const [k, val] of [...p]) if (!val) p.delete(k);
      const cats = [...new Set((await api('/products')).items.map(x => x.category))].sort(), cur = $('#f-cat').value;
      $('#f-cat').innerHTML = '<option value="">All categories</option>' + cats.map(c => `<option${c === cur ? ' selected' : ''}>${esc(c)}</option>`).join('');
      const d = await api('/products?' + p);
      $('#list').innerHTML = d.items.length ? `<table><tr><th>SKU</th><th>Product</th><th>Category</th><th>Price</th><th>Cost</th><th>Margin</th><th>Stock</th><th></th></tr>${d.items.map(x => { const low = x.stock <= x.reorder_level;
        return `<tr><td>${esc(x.sku)}</td><td><b>${esc(x.name)}</b></td><td>${esc(x.category)}</td><td>${inr(x.price)}</td><td>${inr(x.cost)}</td><td>${Math.round(100 * (x.price - x.cost) / x.price)}%</td>
        <td><span class="meter"><i class="${low ? 'low' : ''}" style="width:${Math.min(100, 100 * x.stock / (x.reorder_level * 4 || 1))}%"></i></span>${x.stock}${low ? ' <span class="tag hot">low</span>' : ''}</td>
        <td><button class="btn ghost sm" data-edit="${x.id}">Edit</button> <button class="btn red sm" data-del="${x.id}">Delete</button></td></tr>`; }).join('')}</table>` : '<div class="empty">No products match.</div>';
      $('#list').onclick = e => { const ed = e.target.dataset.edit, dl = e.target.dataset.del;
        if (ed) { editing = d.items.find(x => x.id == ed); form(); }
        if (dl && confirm('Delete this product? Past orders keep their own copy of the details.')) run(async () => { await api('/products/' + dl, { method: 'DELETE' }); toast('Product deleted'); load(); }); };
    };
    const form = () => {
      const p = editing || { sku: '', name: '', category: '', price: '', cost: '', stock: 0, reorder_level: 15 };
      $('#form').innerHTML = `<form class="card" id="pf"><label>SKU<input name="sku" value="${esc(p.sku)}" required></label><label>Name<input name="name" value="${esc(p.name)}" required></label>
        <label>Category<input name="category" value="${esc(p.category)}" list="cats" required></label><datalist id="cats"><option>Beverages<option>Bakery<option>Snacks<option>Meals</datalist>
        <label>Price (₹)<input name="price" type="number" step="0.01" min="0.01" value="${p.price}" required></label><label>Cost (₹)<input name="cost" type="number" step="0.01" min="0" value="${p.cost}" required></label>
        <label>Stock<input name="stock" type="number" min="0" value="${p.stock}"></label><label>Reorder level<input name="reorder_level" type="number" min="0" value="${p.reorder_level}"></label>
        <span class="full"><button class="btn">${editing ? 'Save changes' : 'Add product'}</button> <button type="button" class="btn ghost" id="cancel">Cancel</button></span></form>`;
      $('#cancel').onclick = () => { editing = null; $('#form').innerHTML = ''; };
      $('#pf').onsubmit = e => { e.preventDefault(); const body = Object.fromEntries(new FormData(e.target));
        run(async () => { await api(editing ? '/products/' + editing.id : '/products', { method: editing ? 'PUT' : 'POST', body }); toast(editing ? 'Product updated' : 'Product added'); editing = null; $('#form').innerHTML = ''; load(); }); };
    };
    $('#add').onclick = () => { editing = null; form(); };
    ['#f-q', '#f-cat', '#f-low'].forEach(s => $(s).oninput = () => run(load)); await load();
  },

  async customers(v) {
    const d = await api('/customers');
    v.innerHTML = `<form class="card" id="cf"><label>Name<input name="name" required></label><label>Phone<input name="phone"></label><label>Email (optional)<input name="email"></label><label>&nbsp;<button class="btn">Add customer</button></label></form>
      <div class="card">${d.items.length ? `<table><tr><th>Name</th><th>Phone</th><th>Email</th><th>Orders</th><th>Spent</th><th></th></tr>${d.items.map(c => `<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.phone)}</td><td>${esc(c.email || '-')}</td><td>${c.orders}</td><td>${inr(c.spent)}</td><td><button class="btn red sm" data-del="${c.id}">Delete</button></td></tr>`).join('')}</table>` : '<div class="empty">No customers yet.</div>'}</div>
      <p style="color:var(--mute);font-size:13px">Email is an optional field: some documents have it, some do not. TinyDB needs no schema change.</p>`;
    $('#cf').onsubmit = e => { e.preventDefault(); run(async () => { await api('/customers', { method: 'POST', body: Object.fromEntries(new FormData(e.target)) }); toast('Customer added'); show('customers'); }); };
    v.onclick = e => { const dl = e.target.dataset.del; if (dl && confirm('Delete this customer? Their orders stay as history.')) run(async () => { await api('/customers/' + dl, { method: 'DELETE' }); toast('Customer deleted'); show('customers'); }); };
  },

  async sales(v) {
    const [pr, cu, od] = await Promise.all([api('/products'), api('/customers'), api('/orders?limit=15')]); let cart = [{ sku: pr.items[0]?.sku, qty: 1 }];
    v.innerHTML = `<div class="grid g2" style="grid-template-columns:420px 1fr"><div class="card"><h2>New sale</h2>
      <div class="bar"><select id="o-cust" style="flex:1"><option value="">Walk-in customer</option>${cu.items.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>
      <select id="o-pay"><option value="upi">UPI</option><option value="cash">Cash</option><option value="card">Card</option></select></div><div id="cart"></div>
      <button class="btn ghost sm" id="o-add">＋ Add item</button><h2 style="margin-top:16px">Total: <span id="o-total" style="color:var(--ink)"></span></h2><button class="btn" id="o-go">Complete sale</button></div>
      <div class="card"><h2>Recent orders (${od.count.toLocaleString('en-IN')} total)</h2><table><tr><th>When</th><th>Customer</th><th>Items</th><th>Pay</th><th>Total</th></tr>${od.items.map(o => `<tr><td>${esc(o.ts.replace('T', ' '))}</td><td>${esc(o.customer)}</td>
      <td style="color:var(--mute);font-size:13px">${o.items.map(i => i.qty + '× ' + esc(i.name)).join(', ')}</td><td><span class="tag">${esc(o.payment)}</span></td><td><b>${inr(o.total)}</b></td></tr>`).join('')}</table></div></div>`;
    const draw = () => {
      $('#cart').innerHTML = cart.map((c, i) => `<div class="row"><select data-i="${i}" data-k="sku">${pr.items.map(p => `<option value="${esc(p.sku)}"${p.sku === c.sku ? ' selected' : ''}>${esc(p.name)} · ${inr(p.price)} · ${p.stock} left</option>`).join('')}</select>
        <input type="number" min="1" value="${c.qty}" data-i="${i}" data-k="qty"><button class="btn red sm" data-rm="${i}">✕</button></div>`).join('');
      $('#o-total').textContent = inr(cart.reduce((n, c) => n + (pr.items.find(p => p.sku === c.sku)?.price || 0) * (+c.qty || 0), 0));
    };
    $('#cart').oninput = e => { const i = e.target.dataset.i; if (i != null) { cart[i][e.target.dataset.k] = e.target.value; draw2(); } };
    const draw2 = () => $('#o-total').textContent = inr(cart.reduce((n, c) => n + (pr.items.find(p => p.sku === c.sku)?.price || 0) * (+c.qty || 0), 0));
    $('#cart').onclick = e => { const r = e.target.dataset.rm; if (r != null) { cart.splice(+r, 1); draw(); } };
    $('#o-add').onclick = () => { cart.push({ sku: pr.items[0]?.sku, qty: 1 }); draw(); };
    $('#o-go').onclick = () => run(async () => { await api('/orders', { method: 'POST', body: { customer_id: $('#o-cust').value || null, payment: $('#o-pay').value, items: cart.map(c => ({ sku: c.sku, qty: c.qty })) } }); toast('Sale recorded'); show('sales'); });
    draw();
  },

  async tables(v) {
    const cell = x => { if (x == null) return '<span style="color:var(--mute)">-</span>'; if (Array.isArray(x)) return '<span class="tag">' + x.length + ' nested</span> ' + esc(x.map(i => i.qty + 'x ' + i.name).join(', ')); if (typeof x === 'object') return esc(JSON.stringify(x)); return esc(x); };
    const load = async name => {
      const d = await api('/tables' + (name ? '?name=' + encodeURIComponent(name) : '')), cols = ['id', ...d.fields.map(f => f.name)];
      v.innerHTML = `<div class="bar">${d.tables.map(t => `<button class="btn ${t.name === d.name ? '' : 'ghost'}" data-t="${esc(t.name)}">${esc(t.name)} (${t.count})</button>`).join('')}</div>
        <div class="card"><h2>Fields found in <code>${esc(d.name)}</code> (TinyDB has no fixed schema)</h2>
        <table><tr>${d.fields.map(f => `<th>${esc(f.name)}</th>`).join('')}</tr><tr>${d.fields.map(f => `<td>${f.count} / ${d.total} docs${f.count < d.total ? ' <span class="tag hot">optional</span>' : ''}</td>`).join('')}</tr></table></div>
        <div class="card" style="margin-top:16px;overflow:auto"><h2>${esc(d.name)}: showing ${d.rows.length} of ${d.total} documents (newest first)</h2>
        ${d.rows.length ? `<table><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>${d.rows.map(r => `<tr>${cols.map(c => `<td>${cell(r[c])}</td>`).join('')}</tr>`).join('')}</table>` : '<div class="empty">' + esc(d.note || 'Table is empty') + '</div>'}</div>`;
      v.onclick = e => { const t = e.target.dataset.t; if (t) run(() => load(t)); };
    };
    await load();
  },

  async tools(v) {
    v.innerHTML = `<div class="grid g2"><div class="card"><h2>Data tools</h2><div class="grid">
      <button class="btn" id="t-seed">Load sample data (60 days, resets everything)</button><button class="btn ghost" id="t-merge">Merge another outlet's file…</button>
      <button class="btn ghost" id="t-backup">Back up database…</button><button class="btn ghost" id="t-raw">Show raw JSON file</button></div></div>
      <div class="card"><h2>Performance test (10,000 orders)</h2><button class="btn" id="t-bench">Run benchmark</button><div class="chart" style="margin-top:12px;height:230px"><canvas id="c-bench"></canvas></div></div></div><div id="raw" style="margin-top:16px"></div>`;
    $('#t-seed').onclick = () => confirm('This deletes all current data. Continue?') && run(async () => { await api('/seed', { method: 'POST' }); toast('Sample data loaded'); });
    $('#t-merge').onclick = () => run(async () => { const p = DEMO ? 'demo.json' : window.relief ? await window.relief.pickJson() : prompt('Path to .json file'); if (!p) return;
      const r = await api('/merge', { method: 'POST', body: { path: p } }); toast(`Merged: ${r.added} orders added, ${r.skipped} skipped, ${r.new_products} new products`); });
    $('#t-backup').onclick = () => run(async () => { const p = DEMO ? 'demo.json' : window.relief ? await window.relief.pickSave() : prompt('Save path (.json)'); if (!p) return; await api('/backup', { method: 'POST', body: { path: p } }); toast('Backup saved'); });
    $('#t-raw').onclick = () => run(async () => { const r = await api('/raw'); $('#raw').innerHTML = `<div class="card"><h2>${esc(r.path)}</h2><p style="color:var(--mute);font-size:12px">${esc(r.note || '')}</p><pre>${esc(JSON.stringify(r.data, null, 2))}</pre></div>`; });
    $('#t-bench').onclick = () => run(async () => { killCharts(); const b = await api('/benchmark');
      mk('c-bench', { type: 'bar', data: { labels: ['Insert 10,000', 'Aggregate by day', 'Scan search', 'doc_id lookup', '200 inserts plain', '200 inserts cached'],
        datasets: [{ data: [b.insert_ms, b.aggregate_ms, b.scan_ms, b.doc_id_ms, b.plain_200_ms, b.cached_200_ms], backgroundColor: PAL }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.parsed.x + ' ms' } } }, scales: { x: { title: { display: true, text: 'milliseconds (lower is faster)' } } } } }); });
  }
};
const titles = { dashboard: 'Business Dashboard', products: 'Products and Stock', customers: 'Customers', sales: 'Sales', tables: 'Database Tables', tools: 'Tools and Performance' };
async function show(tab) {
  editing = null; killCharts(); $('#view').onclick = null;
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  $('#title').textContent = titles[tab]; await run(() => views[tab]($('#view')));
}
$('#nav').innerHTML = Object.keys(titles).map(k => `<button data-tab="${k}">${titles[k]}</button>`).join('');
$('#nav').onclick = e => e.target.dataset.tab && show(e.target.dataset.tab);
(async function boot() {
  try {
    const c = new AbortController(); setTimeout(() => c.abort(), 1500);
    const h = await (await fetch(API + '/health', { signal: c.signal })).json();
    $('#dot').classList.add('ok'); $('#status').textContent = 'TinyDB ' + h.tinydb + ' online';
  } catch {
    DEMO = true; $('#dot').classList.add('ok'); $('#status').textContent = 'Demo mode: data stays in this browser';
    $('#title').insertAdjacentHTML('afterend', '<div class="card" style="margin:-6px 0 16px;font-size:13px">Demo mode: no backend found, so data is stored in your browser. Run the desktop app to use the real TinyDB backend.</div>');
    if (!window.demoHasData()) await window.demoApi('/seed', { method: 'POST' });
  }
  show('dashboard');
})();
