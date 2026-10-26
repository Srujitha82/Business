// Demo mode: an in-browser stand-in for the Flask/TinyDB API so ShopPulse also works on GitHub Pages.
// Data lives in this browser's localStorage. The real TinyDB runs in backend/app.py.
(function () {
  const KEY = 'shoppulse_demo_v1', PAYMENTS = ['upi', 'cash', 'card'];
  const CATALOG = [['BEV01', 'Filter Coffee', 'Beverages', 40, 12], ['BEV02', 'Masala Chai', 'Beverages', 20, 6], ['BEV03', 'Cold Coffee', 'Beverages', 90, 30], ['BEV04', 'Fresh Lime Soda', 'Beverages', 50, 14],
    ['BAK01', 'Butter Croissant', 'Bakery', 70, 25], ['BAK02', 'Chocolate Muffin', 'Bakery', 60, 22], ['BAK03', 'Whole Wheat Bread', 'Bakery', 55, 30], ['BAK04', 'Sourdough Loaf', 'Bakery', 150, 70],
    ['SNK01', 'Veg Puff', 'Snacks', 30, 12], ['SNK02', 'Samosa', 'Snacks', 20, 7], ['SNK03', 'Club Sandwich', 'Snacks', 80, 32], ['SNK04', 'Cookie Pack', 'Snacks', 90, 40],
    ['MEL01', 'Veg Biryani', 'Meals', 140, 60], ['MEL02', 'Paneer Wrap', 'Meals', 110, 45], ['MEL03', 'Pasta Bowl', 'Meals', 160, 65], ['MEL04', 'Idli Combo', 'Meals', 60, 22]];
  const PEOPLE = ['Aarav', 'Meera', 'Karthik', 'Divya', 'Rohan', 'Ananya', 'Vikram', 'Priya', 'Suresh', 'Lakshmi', 'Arjun', 'Nisha'];
  const HOUR_W = { 8: 7, 9: 9, 10: 6, 11: 4, 12: 8, 13: 10, 14: 6, 15: 4, 16: 5, 17: 8, 18: 9, 19: 7, 20: 4, 21: 2 };
  const catByHour = h => h < 11 ? { Beverages: 5, Bakery: 4, Snacks: 1, Meals: 1 } : h < 15 ? { Meals: 6, Snacks: 3, Beverages: 3, Bakery: 1 } : { Snacks: 5, Beverages: 5, Bakery: 3, Meals: 2 };
  let db; try { db = JSON.parse(localStorage.getItem(KEY)); } catch { db = null; }
  db = db || { products: [], customers: [], orders: [], nid: { p: 1, c: 1, o: 1 } };
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) { } };
  const pad = n => String(n).padStart(2, '0'), isoDate = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const fail = (m, c = 400) => { const e = new Error(m); e.code = c; throw e; };
  const out = (data, query, status = 200) => ({ status, data: Object.assign(data, { query: 'demo · ' + query }) });
  function rng(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const pick = (r, a) => a[Math.floor(r() * a.length)];
  const wpick = (r, items, w) => { let x = r() * w.reduce((a, b) => a + b, 0); for (let i = 0; i < items.length; i++) { x -= w[i]; if (x < 0) return items[i]; } return items[items.length - 1]; };

  function seed() {
    const r = rng(42); db = { products: [], customers: [], orders: [], nid: { p: 1, c: 1, o: 1 } };
    CATALOG.forEach(([sku, name, category, price, cost]) => db.products.push({ id: db.nid.p++, sku, name, category, price, cost, stock: 4 + Math.floor(r() * 67), reorder_level: 15 }));
    PEOPLE.forEach((name, i) => db.customers.push(Object.assign({ id: db.nid.c++, name, phone: '98' + String(Math.floor(r() * 1e8)).padStart(8, '0') }, i % 3 === 0 ? { email: name.toLowerCase() + '@example.com' } : {})));
    const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate()), days = 60, hours = Object.keys(HOUR_W).map(Number), hw = Object.values(HOUR_W);
    for (let k = days; k >= 0; k--) {
      const day = new Date(today); day.setDate(day.getDate() - k);
      let n = Math.floor(14 * (1 + 0.35 * (days - k) / days) * (day.getDay() === 0 || day.getDay() === 6 ? 1.5 : 1) * (0.8 + 0.4 * r())); if (k === 0) n = Math.max(3, Math.floor(n / 3));
      for (let j = 0; j < n; j++) {
        let h = wpick(r, hours, hw); if (k === 0 && h > now.getHours()) h = Math.max(8, now.getHours() - 1);
        const w = catByHour(h), chosen = {}, lines = pick(r, [1, 1, 2, 2, 3, 4]);
        for (let q = 0; q < lines; q++) { const cat = wpick(r, Object.keys(w), Object.values(w)), s = pick(r, CATALOG.filter(c => c[2] === cat))[0]; chosen[s] = (chosen[s] || 0) + pick(r, [1, 1, 1, 2, 3]); }
        const items = Object.entries(chosen).map(([s, qty]) => { const c = CATALOG.find(x => x[0] === s); return { sku: s, name: c[1], category: c[2], qty, price: c[3], cost: c[4] }; });
        const total = items.reduce((a, i) => a + i.qty * i.price, 0), cost = items.reduce((a, i) => a + i.qty * i.cost, 0);
        db.orders.push({ id: db.nid.o++, ref: Math.floor(r() * 4294967296).toString(16).padStart(8, '0'), customer_id: r() < 0.4 ? pick(r, db.customers).id : null, items, total, profit: total - cost,
          payment: wpick(r, PAYMENTS, [55, 30, 15]), ts: `${isoDate(day)}T${pad(h)}:${pad(Math.floor(r() * 60))}` });
      }
    }
  }
  const summarize = rows => { const rev = rows.reduce((a, o) => a + o.total, 0), prof = rows.reduce((a, o) => a + o.profit, 0);
    return { revenue: rev, profit: prof, orders: rows.length, units: rows.reduce((a, o) => a + o.items.reduce((b, i) => b + i.qty, 0), 0), aov: rows.length ? Math.round(rev / rows.length * 10) / 10 : 0, margin: rev ? Math.round(1000 * prof / rev) / 10 : 0 }; };
  const cleanProduct = d => { const sku = String(d.sku || '').trim().toUpperCase(), name = String(d.name || '').trim(), category = String(d.category || '').trim();
    if (!sku || !name || !category) fail('SKU, name and category are required'); const price = parseFloat(d.price), cost = parseFloat(d.cost), stock = parseInt(d.stock), reorder_level = parseInt(d.reorder_level ?? 15);
    if (!(price >= 0.01)) fail('Price cannot be below 0.01'); if (!(cost >= 0)) fail('Cost cannot be below 0'); if (!(stock >= 0)) fail('Stock cannot be below 0'); if (!(reorder_level >= 0)) fail('Reorder level cannot be below 0');
    return { sku, name, category, price, cost, stock, reorder_level }; };

  window.demoApi = async function (path, opts = {}) {
    const m = (opts.method || 'GET').toUpperCase(), b = opts.body || {}, u = new URL('http://x' + path), p = u.pathname, a = u.searchParams, mt = re => p.match(re);
    try {
      if (p === '/health') return { status: 200, data: { ok: true, tinydb: 'demo mode' } };
      if (p === '/seed') { seed(); save(); return out({ ok: true, orders: db.orders.length }, 'db.drop_tables(); products.insert_multiple([...]); customers.insert_multiple([...]); orders.insert_multiple([...])'); }
      if (p === '/products' && m === 'GET') {
        let rows = db.products, parts = [];
        if (a.get('category')) { rows = rows.filter(x => x.category === a.get('category')); parts.push(`(Q.category == '${a.get('category')}')`); }
        if (a.get('q')) { rows = rows.filter(x => x.name.toLowerCase().includes(a.get('q').toLowerCase())); parts.push(`Q.name.search('${a.get('q')}')`); }
        if (a.get('low')) { rows = rows.filter(x => x.stock <= x.reorder_level); parts.push('stock <= reorder_level'); }
        return out({ items: rows }, parts.length ? `products.search(${parts.join(' & ')})` : 'products.all()');
      }
      if (p === '/products' && m === 'POST') { const d = cleanProduct(b); if (db.products.some(x => x.sku === d.sku)) fail('That SKU already exists', 409); const id = db.nid.p++; db.products.push({ id, ...d }); save(); return out({ id }, `products.insert(${JSON.stringify(d)})`, 201); }
      let r = mt(/^\/products\/(\d+)$/);
      if (r) { const i = +r[1], k = db.products.findIndex(x => x.id === i); if (k < 0) fail('Not found', 404);
        if (m === 'PUT') { const d = cleanProduct(b); if (db.products.some(x => x.sku === d.sku && x.id !== i)) fail('That SKU already exists', 409); db.products[k] = { id: i, ...d }; save(); return out({ id: i }, `products.update({...}, doc_ids=[${i}])`); }
        if (m === 'DELETE') { db.products.splice(k, 1); save(); return out({ ok: true }, `products.remove(doc_ids=[${i}])`); } }
      if (p === '/customers' && m === 'GET') { const sp = {}, ct = {}; db.orders.forEach(o => { if (o.customer_id) { sp[o.customer_id] = (sp[o.customer_id] || 0) + o.total; ct[o.customer_id] = (ct[o.customer_id] || 0) + 1; } });
        return out({ items: db.customers.map(c => ({ ...c, orders: ct[c.id] || 0, spent: sp[c.id] || 0 })) }, 'customers.all() + aggregate orders by customer_id  # manual join'); }
      if (p === '/customers' && m === 'POST') { const name = String(b.name || '').trim(); if (!name) fail('Name is required'); const d = { name, phone: String(b.phone || '').trim() }; if (String(b.email || '').trim()) d.email = String(b.email).trim();
        const id = db.nid.c++; db.customers.push({ id, ...d }); save(); return out({ id }, `customers.insert(${JSON.stringify(d)})`, 201); }
      r = mt(/^\/customers\/(\d+)$/);
      if (r && m === 'DELETE') { const k = db.customers.findIndex(x => x.id === +r[1]); if (k < 0) fail('Not found', 404); db.customers.splice(k, 1); save(); return out({ ok: true }, `customers.remove(doc_ids=[${r[1]}])`); }
      if (p === '/orders' && m === 'GET') { const lim = parseInt(a.get('limit') || 15); let rows = a.get('payment') ? db.orders.filter(o => o.payment === a.get('payment')) : db.orders;
        rows = [...rows].sort((x, y) => x.ts < y.ts ? 1 : -1).slice(0, lim).map(o => { const c = o.customer_id ? db.customers.find(x => x.id === o.customer_id) : null; return { ...o, customer: c ? c.name : (o.customer_id ? '(removed)' : 'Walk-in') }; });
        return out({ items: rows, count: db.orders.length }, 'orders.all()  # sorted by ts, joined with customers'); }
      if (p === '/orders' && m === 'POST') {
        const want = {}; (b.items || []).forEach(it => { const q = parseInt(it.qty); if (!(q >= 1)) fail('Quantity must be at least 1'); want[it.sku] = (want[it.sku] || 0) + q; });
        if (!Object.keys(want).length) fail('Add at least one item'); if (!PAYMENTS.includes(b.payment)) fail('Choose a payment method');
        const cid = b.customer_id ? +b.customer_id : null; if (cid && !db.customers.some(c => c.id === cid)) fail('Customer not found', 404);
        const items = Object.entries(want).map(([s, q]) => { const pr = db.products.find(x => x.sku === s); if (!pr) fail('Unknown product ' + s, 404); if (pr.stock < q) fail(`Only ${pr.stock} of ${pr.name} in stock`, 409);
          return { sku: s, name: pr.name, category: pr.category, qty: q, price: pr.price, cost: pr.cost }; });
        items.forEach(i => db.products.find(x => x.sku === i.sku).stock -= i.qty);
        const total = items.reduce((n, i) => n + i.qty * i.price, 0), profit = total - items.reduce((n, i) => n + i.qty * i.cost, 0), d = new Date();
        const id = db.nid.o++; db.orders.push({ id, ref: Math.random().toString(16).slice(2, 10), customer_id: cid, items, total, profit, payment: b.payment, ts: `${isoDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}` }); save();
        return out({ id, total }, `orders.insert({... ${items.length} items, total: ${total}}); products.update(subtract('stock', n), Q.sku == ...)`, 201);
      }
      if (p === '/analytics') {
        const days = Math.max(1, Math.min(parseInt(a.get('days') || 30), 365)), t0 = new Date(), today = new Date(t0.getFullYear(), t0.getMonth(), t0.getDate());
        const start = new Date(today); start.setDate(start.getDate() - days + 1); const pstart = new Date(start); pstart.setDate(pstart.getDate() - days);
        const s = isoDate(start), ps = isoDate(pstart), rows = db.orders.filter(o => o.ts >= s), prev = db.orders.filter(o => o.ts >= ps && o.ts < s), kp = summarize(rows), kpp = summarize(prev);
        const grow = (x, y) => y ? Math.round(1000 * (x - y) / y) / 10 : null, day = {}, cat = {}, prod = {}, pay = {}, hour = {}, wd = {}, cust = {};
        rows.forEach(o => { const dd = o.ts.slice(0, 10), h = +o.ts.slice(11, 13), w = (new Date(dd + 'T00:00').getDay() + 6) % 7; day[dd] = day[dd] || [0, 0, 0]; day[dd][0] += o.total; day[dd][1] += o.profit; day[dd][2]++;
          pay[o.payment] = (pay[o.payment] || 0) + o.total; hour[h] = (hour[h] || 0) + 1; wd[w] = (wd[w] || 0) + o.total; if (o.customer_id) cust[o.customer_id] = (cust[o.customer_id] || 0) + o.total;
          o.items.forEach(i => { cat[i.category] = (cat[i.category] || 0) + i.qty * i.price; prod[i.name] = prod[i.name] || [0, 0]; prod[i.name][0] += i.qty; prod[i.name][1] += i.qty * i.price; }); });
        const axis = Array.from({ length: days }, (_, k) => { const d = new Date(start); d.setDate(d.getDate() + k); return isoDate(d); });
        const top = Object.entries(prod).sort((x, y) => y[1][1] - x[1][1]).slice(0, 8), names = Object.fromEntries(db.customers.map(c => [c.id, c.name]));
        return out({ days, kpis: kp, previous: kpp, growth: { revenue: grow(kp.revenue, kpp.revenue), orders: grow(kp.orders, kpp.orders), profit: grow(kp.profit, kpp.profit) },
          daily: { labels: axis, revenue: axis.map(x => day[x]?.[0] || 0), profit: axis.map(x => day[x]?.[1] || 0), orders: axis.map(x => day[x]?.[2] || 0) },
          category: { labels: Object.keys(cat), values: Object.values(cat) }, top_products: { labels: top.map(t => t[0]), values: top.map(t => t[1][1]), units: top.map(t => t[1][0]) },
          payment: { labels: Object.keys(pay).map(x => x.toUpperCase()), values: Object.values(pay) }, hours: { labels: Array.from({ length: 14 }, (_, i) => `${i + 8}:00`), values: Array.from({ length: 14 }, (_, i) => hour[i + 8] || 0) },
          weekday: { labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], values: [0, 1, 2, 3, 4, 5, 6].map(k => wd[k] || 0) },
          top_customers: Object.entries(cust).sort((x, y) => y[1] - x[1]).slice(0, 5).map(([c, v]) => ({ name: names[c] || '(removed)', spent: v })),
          low_stock: db.products.filter(x => x.stock <= x.reorder_level), inventory_value: db.products.reduce((n, x) => n + x.stock * x.cost, 0) },
          `orders.search(Q.ts >= '${s}')  # then group by day, category, product in Python`);
      }
      if (p === '/tables') {
        const all = { products: db.products, customers: db.customers, orders: db.orders };
        const info = Object.keys(all).map(n => ({ name: n, count: all[n].length }));
        const name = a.get('name') || 'products', rows = all[name] || [], seen = {};
        rows.forEach(r => Object.keys(r).forEach(k => { if (k !== 'id') seen[k] = (seen[k] || 0) + 1; }));
        return out({ tables: info, name, fields: Object.entries(seen).map(([k, c]) => ({ name: k, count: c })), rows: rows.slice(-25).reverse(), total: rows.length },
          `db.tables(); ${name}.all()  # ${rows.length} documents`);
      }
      if (p === '/raw') { const t = (arr, lim) => Object.fromEntries(arr.slice(0, lim).map(({ id, ...rest }) => [String(id), rest]));
        return out({ data: { products: t(db.products, 99), customers: t(db.customers, 99), orders: t(db.orders, 6) }, path: 'browser localStorage (demo mode)', note: 'orders trimmed to the first 6 for display' }, 'open(shoppulse.json)  # same layout TinyDB writes to disk'); }
      if (p === '/backup') { const el = document.createElement('a'); el.href = URL.createObjectURL(new Blob([JSON.stringify(db, null, 2)], { type: 'application/json' })); el.download = 'shoppulse-demo-backup.json'; el.click();
        return out({ ok: true }, 'download backup  # in the real app: shutil.copyfile(shoppulse.json, backup.json)'); }
      if (p === '/merge') fail('Merging files needs the real TinyDB backend (run the desktop app)');
      if (p === '/benchmark') fail('The benchmark measures real TinyDB, so it needs the backend (run the desktop app)');
      fail('Not found', 404);
    } catch (e) { return { status: e.code || 500, data: { error: e.message } }; }
  };
  window.demoHasData = () => db.orders.length > 0;
})();
