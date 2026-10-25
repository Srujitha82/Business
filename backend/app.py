"""ShopPulse backend: Flask REST API on top of TinyDB.
Business: point-of-sale and analytics for a neighbourhood cafe and bakery.
Tables: products, customers, orders (each order embeds its line items as nested documents).
Every response includes a 'query' string so the UI can show the TinyDB call behind each action."""
import os, re, time, random, secrets, shutil, tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from importlib.metadata import version
from flask import Flask, jsonify, request
from tinydb import TinyDB, Query
from tinydb.operations import subtract, add
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

DB_PATH = os.environ.get('SHOPPULSE_DB', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'shoppulse.json'))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
products, customers, orders = db.table('products'), db.table('customers'), db.table('orders')
Q = Query()
app = Flask(__name__)
PAYMENTS = ['upi', 'cash', 'card']

@app.before_request
def preflight():
    if request.method == 'OPTIONS': return '', 204

@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return r

def err(msg, code=400): return jsonify(error=msg), code
def out(d): x = dict(d); x['id'] = d.doc_id; return x
def num(v, name, kind=float, minimum=0):
    try: x = kind(v)
    except (TypeError, ValueError): raise ValueError(f'{name} must be a number')
    if x < minimum: raise ValueError(f'{name} cannot be below {minimum}')
    return x

# ---------- seed data ----------
CATALOG = [  # sku, name, category, price, cost
    ('BEV01', 'Filter Coffee', 'Beverages', 40, 12), ('BEV02', 'Masala Chai', 'Beverages', 20, 6),
    ('BEV03', 'Cold Coffee', 'Beverages', 90, 30), ('BEV04', 'Fresh Lime Soda', 'Beverages', 50, 14),
    ('BAK01', 'Butter Croissant', 'Bakery', 70, 25), ('BAK02', 'Chocolate Muffin', 'Bakery', 60, 22),
    ('BAK03', 'Whole Wheat Bread', 'Bakery', 55, 30), ('BAK04', 'Sourdough Loaf', 'Bakery', 150, 70),
    ('SNK01', 'Veg Puff', 'Snacks', 30, 12), ('SNK02', 'Samosa', 'Snacks', 20, 7),
    ('SNK03', 'Club Sandwich', 'Snacks', 80, 32), ('SNK04', 'Cookie Pack', 'Snacks', 90, 40),
    ('MEL01', 'Veg Biryani', 'Meals', 140, 60), ('MEL02', 'Paneer Wrap', 'Meals', 110, 45),
    ('MEL03', 'Pasta Bowl', 'Meals', 160, 65), ('MEL04', 'Idli Combo', 'Meals', 60, 22)]
PEOPLE = ['Aarav', 'Meera', 'Karthik', 'Divya', 'Rohan', 'Ananya', 'Vikram', 'Priya', 'Suresh', 'Lakshmi', 'Arjun', 'Nisha']
HOUR_W = {8: 7, 9: 9, 10: 6, 11: 4, 12: 8, 13: 10, 14: 6, 15: 4, 16: 5, 17: 8, 18: 9, 19: 7, 20: 4, 21: 2}
CAT_BY_HOUR = lambda h: {'Beverages': 5, 'Bakery': 4, 'Snacks': 1, 'Meals': 1} if h < 11 else ({'Meals': 6, 'Snacks': 3, 'Beverages': 3, 'Bakery': 1} if h < 15 else {'Snacks': 5, 'Beverages': 5, 'Bakery': 3, 'Meals': 2})

def make_orders(rnd, cust_ids, days, per_day=14):
    sku = {c[0]: c for c in CATALOG}; rows = []; today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for k in range(days, -1, -1):
        day = today - timedelta(days=k)
        n = int(per_day * (1 + 0.35 * (days - k) / days) * (1.5 if day.weekday() >= 5 else 1) * rnd.uniform(0.8, 1.2))
        if k == 0: n = max(3, n // 3)       # today is only partly done
        for _ in range(n):
            h = rnd.choices(list(HOUR_W), list(HOUR_W.values()))[0]
            if k == 0 and h > datetime.now().hour: h = max(8, datetime.now().hour - 1)
            weights = CAT_BY_HOUR(h); chosen = {}
            for _ in range(rnd.choice([1, 1, 2, 2, 3, 4])):
                cat = rnd.choices(list(weights), list(weights.values()))[0]
                s = rnd.choice([c for c in CATALOG if c[2] == cat])[0]; chosen[s] = chosen.get(s, 0) + rnd.choice([1, 1, 1, 2, 3])
            items = [{'sku': s, 'name': sku[s][1], 'category': sku[s][2], 'qty': q, 'price': sku[s][3], 'cost': sku[s][4]} for s, q in chosen.items()]
            total = sum(i['qty'] * i['price'] for i in items); cost = sum(i['qty'] * i['cost'] for i in items)
            rows.append({'ref': '%08x' % rnd.getrandbits(32), 'customer_id': rnd.choice(cust_ids) if rnd.random() < 0.4 else None, 'items': items,
                         'total': total, 'profit': total - cost, 'payment': rnd.choices(PAYMENTS, [55, 30, 15])[0],
                         'ts': (day + timedelta(hours=h, minutes=rnd.randint(0, 59))).isoformat(timespec='minutes')})
    return rows

@app.get('/api/health')
def health(): return jsonify(ok=True, db=DB_PATH, tinydb=version('tinydb'))

@app.post('/api/seed')
def seed():
    rnd = random.Random(42); db.drop_tables()
    products.insert_multiple([{'sku': s, 'name': n, 'category': c, 'price': p, 'cost': k, 'stock': rnd.randint(4, 70), 'reorder_level': 15} for s, n, c, p, k in CATALOG])
    ids = customers.insert_multiple([dict({'name': n, 'phone': '98%08d' % rnd.randint(0, 99999999)}, **({'email': n.lower() + '@example.com'} if i % 3 == 0 else {})) for i, n in enumerate(PEOPLE)])
    orders.insert_multiple(make_orders(rnd, ids, 60))
    return jsonify(ok=True, orders=len(orders), query='db.drop_tables(); products.insert_multiple([...]); customers.insert_multiple([...]); orders.insert_multiple([...])')

# ---------- products ----------
def clean_product(d):
    name, cat, sku = str(d.get('name', '')).strip(), str(d.get('category', '')).strip(), str(d.get('sku', '')).strip().upper()
    if not sku or not name or not cat: raise ValueError('SKU, name and category are required')
    return {'sku': sku, 'name': name, 'category': cat, 'price': num(d.get('price'), 'Price', float, 0.01), 'cost': num(d.get('cost'), 'Cost'),
            'stock': num(d.get('stock'), 'Stock', int), 'reorder_level': num(d.get('reorder_level', 15), 'Reorder level', int)}

@app.get('/api/products')
def list_products():
    q, parts = None, []
    def and_(c, t):
        nonlocal q; q = c if q is None else (q & c); parts.append(t)
    if request.args.get('category'): and_(Q.category == request.args['category'], f"(Q.category == '{request.args['category']}')")
    if request.args.get('q'): and_(Q.name.search(re.escape(request.args['q']), flags=re.I), f"Q.name.search('{request.args['q']}')")
    rows = products.search(q) if q is not None else products.all()
    if request.args.get('low'): rows = [r for r in rows if r['stock'] <= r['reorder_level']]; parts.append('stock <= reorder_level')
    return jsonify(items=[out(r) for r in rows], query=f"products.search({' & '.join(parts)})" if parts else 'products.all()')

@app.post('/api/products')
def add_product():
    try: doc = clean_product(request.get_json(force=True))
    except ValueError as e: return err(str(e))
    if products.contains(Q.sku == doc['sku']): return err('That SKU already exists', 409)
    return jsonify(id=products.insert(doc), query=f'products.insert({doc})'), 201

@app.put('/api/products/<int:i>')
def edit_product(i):
    if not products.contains(doc_id=i): return err('Not found', 404)
    try: doc = clean_product(request.get_json(force=True))
    except ValueError as e: return err(str(e))
    if products.contains((Q.sku == doc['sku']) & (~(Q.sku == products.get(doc_id=i)['sku']))): return err('That SKU already exists', 409)
    products.update(doc, doc_ids=[i]); return jsonify(id=i, query=f'products.update({doc}, doc_ids=[{i}])')

@app.delete('/api/products/<int:i>')
def del_product(i):
    if not products.contains(doc_id=i): return err('Not found', 404)
    products.remove(doc_ids=[i]); return jsonify(ok=True, query=f'products.remove(doc_ids=[{i}])')

# ---------- customers ----------
@app.get('/api/customers')
def list_customers():
    spent, count = defaultdict(float), defaultdict(int)
    for o in orders.all():
        if o.get('customer_id'): spent[o['customer_id']] += o['total']; count[o['customer_id']] += 1
    rows = [dict(out(c), orders=count[c.doc_id], spent=spent[c.doc_id]) for c in customers.all()]
    return jsonify(items=rows, query='customers.all() + aggregate orders by customer_id  # manual join')

@app.post('/api/customers')
def add_customer():
    d = request.get_json(force=True); name = str(d.get('name', '')).strip()
    if not name: return err('Name is required')
    doc = {'name': name, 'phone': str(d.get('phone', '')).strip()}
    if str(d.get('email', '')).strip(): doc['email'] = str(d['email']).strip()   # optional field: schema-less
    return jsonify(id=customers.insert(doc), query=f'customers.insert({doc})'), 201

@app.delete('/api/customers/<int:i>')
def del_customer(i):
    if not customers.contains(doc_id=i): return err('Not found', 404)
    customers.remove(doc_ids=[i]); return jsonify(ok=True, query=f'customers.remove(doc_ids=[{i}])')

# ---------- orders ----------
@app.get('/api/orders')
def list_orders():
    limit = request.args.get('limit', 15, type=int); pay = request.args.get('payment')
    rows = orders.search(Q.payment == pay) if pay else orders.all()
    rows = sorted(rows, key=lambda o: o['ts'], reverse=True)[:limit]
    res = []
    for o in rows:
        c = customers.get(doc_id=o['customer_id']) if o.get('customer_id') else None     # manual join
        res.append(dict(out(o), customer=c['name'] if c else ('(removed)' if o.get('customer_id') else 'Walk-in')))
    return jsonify(items=res, count=len(orders), query=f"orders.search(Q.payment == '{pay}')" if pay else 'orders.all()  # sorted by ts, joined with customers')

@app.post('/api/orders')
def new_order():
    d = request.get_json(force=True); want = defaultdict(int)
    for it in d.get('items', []):
        try: q = int(it.get('qty'))
        except (TypeError, ValueError): return err('Quantity must be a number')
        if q < 1: return err('Quantity must be at least 1')
        want[str(it.get('sku'))] += q
    if not want: return err('Add at least one item')
    if d.get('payment') not in PAYMENTS: return err('Choose a payment method')
    cid = d.get('customer_id') or None
    if cid is not None and not customers.contains(doc_id=int(cid)): return err('Customer not found', 404)
    items = []
    for s, q in want.items():
        p = products.get(Q.sku == s)
        if p is None: return err(f'Unknown product {s}', 404)
        if p['stock'] < q: return err(f"Only {p['stock']} of {p['name']} in stock", 409)
        items.append({'sku': s, 'name': p['name'], 'category': p['category'], 'qty': q, 'price': p['price'], 'cost': p['cost']})   # snapshot prices
    for it in items: products.update(subtract('stock', it['qty']), Q.sku == it['sku'])
    total = sum(i['qty'] * i['price'] for i in items); profit = total - sum(i['qty'] * i['cost'] for i in items)
    doc = {'ref': secrets.token_hex(4), 'customer_id': int(cid) if cid else None, 'items': items, 'total': total, 'profit': profit,
           'payment': d['payment'], 'ts': datetime.now().isoformat(timespec='minutes')}
    return jsonify(id=orders.insert(doc), total=total, query=f"orders.insert({{... {len(items)} items, total: {total}}}); products.update(subtract('stock', n), Q.sku == ...)"), 201

# ---------- analytics ----------
def summarize(rows):
    rev = sum(o['total'] for o in rows); prof = sum(o['profit'] for o in rows)
    return dict(revenue=rev, profit=prof, orders=len(rows), units=sum(i['qty'] for o in rows for i in o['items']),
                aov=round(rev / len(rows), 1) if rows else 0, margin=round(100 * prof / rev, 1) if rev else 0)

@app.get('/api/analytics')
def analytics():
    days = max(1, min(request.args.get('days', 30, type=int), 365)); today = datetime.now().date()
    start = today - timedelta(days=days - 1); prev_start = start - timedelta(days=days)
    rows = orders.search(Q.ts >= start.isoformat())
    prev = orders.search((Q.ts >= prev_start.isoformat()) & (Q.ts < start.isoformat()))
    kp, kpp = summarize(rows), summarize(prev)
    grow = lambda a, b: round(100 * (a - b) / b, 1) if b else None
    day = defaultdict(lambda: [0, 0, 0]); cat = defaultdict(float); prod = defaultdict(lambda: [0, 0.0]); pay = defaultdict(float)
    hour = defaultdict(int); wd = defaultdict(float); cust = defaultdict(float)
    for o in rows:
        dt = datetime.fromisoformat(o['ts']); d = day[dt.date().isoformat()]; d[0] += o['total']; d[1] += o['profit']; d[2] += 1
        pay[o['payment']] += o['total']; hour[dt.hour] += 1; wd[dt.weekday()] += o['total']
        if o.get('customer_id'): cust[o['customer_id']] += o['total']
        for i in o['items']:
            cat[i['category']] += i['qty'] * i['price']; prod[i['name']][0] += i['qty']; prod[i['name']][1] += i['qty'] * i['price']
    axis = [(start + timedelta(days=k)).isoformat() for k in range(days)]
    top = sorted(prod.items(), key=lambda kv: kv[1][1], reverse=True)[:8]
    names = {c.doc_id: c['name'] for c in customers.all()}
    low = [out(p) for p in products.all() if p['stock'] <= p['reorder_level']]
    return jsonify(days=days, kpis=kp, previous=kpp, growth={'revenue': grow(kp['revenue'], kpp['revenue']), 'orders': grow(kp['orders'], kpp['orders']), 'profit': grow(kp['profit'], kpp['profit'])},
        daily={'labels': axis, 'revenue': [day[x][0] for x in axis], 'profit': [day[x][1] for x in axis], 'orders': [day[x][2] for x in axis]},
        category={'labels': list(cat), 'values': list(cat.values())},
        top_products={'labels': [t[0] for t in top], 'values': [t[1][1] for t in top], 'units': [t[1][0] for t in top]},
        payment={'labels': [p.upper() for p in pay], 'values': list(pay.values())},
        hours={'labels': [f'{h}:00' for h in range(8, 22)], 'values': [hour[h] for h in range(8, 22)]},
        weekday={'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'values': [wd[k] for k in range(7)]},
        top_customers=[{'name': names.get(c, '(removed)'), 'spent': s} for c, s in sorted(cust.items(), key=lambda kv: kv[1], reverse=True)[:5]],
        low_stock=low, inventory_value=sum(p['stock'] * p['cost'] for p in products.all()),
        query=f"orders.search(Q.ts >= '{start.isoformat()}')  # then group by day, category, product in Python")

# ---------- tools ----------
@app.post('/api/merge')
def merge():
    path = (request.get_json(force=True) or {}).get('path', '')
    if not path.lower().endswith('.json') or not os.path.isfile(path): return err('Pick a valid ShopPulse .json file')
    if os.path.abspath(path) == os.path.abspath(DB_PATH): return err('That is the current database file')
    try:
        src = TinyDB(path); added = skipped = new_products = 0
        for p in src.table('products').all():
            if 'sku' in p and not products.contains(Q.sku == p['sku']): products.insert(dict(p)); new_products += 1
        for o in src.table('orders').all():
            if 'ref' not in o or orders.contains(Q.ref == o['ref']): skipped += 1; continue
            d = dict(o); d['customer_id'] = None       # customer ids differ per file, so merged orders become walk-ins
            orders.insert(d); added += 1
        src.close()
    except Exception as e: return err(f'Could not read file: {e}')
    return jsonify(added=added, skipped=skipped, new_products=new_products, query="for o in other.table('orders'): if not orders.contains(Q.ref == o['ref']): orders.insert(dict(o))")

@app.post('/api/backup')
def backup():
    path = (request.get_json(force=True) or {}).get('path', '')
    if not path.lower().endswith('.json'): return err('Choose a .json destination')
    shutil.copyfile(DB_PATH, path); return jsonify(ok=True, query="shutil.copyfile('shoppulse.json', backup.json)  # the whole business is one file")

@app.get('/api/raw')
def raw():
    import json
    with open(DB_PATH, encoding='utf-8') as f: data = json.load(f)
    small = {k: (dict(list(v.items())[:6]) if k == 'orders' else v) for k, v in data.items()}
    return jsonify(data=small, path=DB_PATH, note='orders trimmed to the first 6 for display', query='open(shoppulse.json)  # human-readable JSON on disk')

@app.get('/api/benchmark')
def benchmark():
    rnd = random.Random(7); ms = lambda x: round(x * 1000, 2)
    with tempfile.TemporaryDirectory() as tmp:
        b = TinyDB(os.path.join(tmp, 'b.json')); t = b.table('orders')
        rows = make_orders(rnd, [1, 2, 3], 700, per_day=14)[:10000]
        s = time.perf_counter(); t.insert_multiple(rows); ins = time.perf_counter() - s
        s = time.perf_counter(); agg = defaultdict(float)
        for o in t.all(): agg[o['ts'][:10]] += o['total']
        aggt = time.perf_counter() - s
        s = time.perf_counter(); t.search(Q.total > 500); scan = time.perf_counter() - s
        s = time.perf_counter(); t.get(doc_id=5000); direct = time.perf_counter() - s
        n = len(t); b.close()
        plain = TinyDB(os.path.join(tmp, 'p.json')); s = time.perf_counter()
        for o in rows[:200]: plain.insert(o)
        pt = time.perf_counter() - s; plain.close()
        cached = TinyDB(os.path.join(tmp, 'c.json'), storage=CachingMiddleware(JSONStorage)); s = time.perf_counter()
        for o in rows[:200]: cached.insert(o)
        cached.close(); ct = time.perf_counter() - s
    return jsonify(orders=n, insert_ms=ms(ins), aggregate_ms=ms(aggt), scan_ms=ms(scan), doc_id_ms=ms(direct), plain_200_ms=ms(pt), cached_200_ms=ms(ct),
                   query='orders.all() -> revenue per day;  orders.search(Q.total > 500);  orders.get(doc_id=5000)')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5050)), debug=False, threaded=False)   # TinyDB is not thread-safe
