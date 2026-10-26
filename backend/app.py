"""ShopPulse backend (simplified): a small Flask API on top of TinyDB.

Three tables: products, customers, orders.
Each order stores its line items inside itself (nested list), so no JOIN is needed to read a sale.
Every response has a 'query' text so the UI can show the TinyDB call behind each action.
"""
import os
import random
import shutil
import json
import time
import tempfile
from datetime import datetime, timedelta
from importlib.metadata import version

from flask import Flask, jsonify, request, send_from_directory
from tinydb import TinyDB, Query
from tinydb.operations import subtract
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

# ---------------------------------------------------------------- setup
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('SHOPPULSE_DB', os.path.join(HERE, 'data', 'shoppulse.json'))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = TinyDB(DB_PATH, indent=2)
products = db.table('products')
customers = db.table('customers')
orders = db.table('orders')
Q = Query()

app = Flask(__name__)
FRONTEND = os.path.join(HERE, '..', 'frontend')   # served at http://127.0.0.1:5050/ (no Node needed)
PAYMENTS = ['upi', 'cash', 'card']


@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 204


@app.after_request
def allow_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response


# ---------------------------------------------------------------- helpers
def error(message, code=400):
    return jsonify(error=message), code


def with_id(doc):
    """TinyDB keeps the id outside the document, so copy it in for the UI."""
    item = dict(doc)
    item['id'] = doc.doc_id
    return item


def to_number(value, label, kind=float, minimum=0):
    try:
        number = kind(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a number')
    if number < minimum:
        raise ValueError(f'{label} cannot be below {minimum}')
    return number


def sum_orders(rows):
    """Revenue, profit and friends for a list of orders."""
    revenue = sum(o['total'] for o in rows)
    profit = sum(o['profit'] for o in rows)
    units = sum(item['qty'] for o in rows for item in o['items'])
    return {
        'revenue': revenue,
        'profit': profit,
        'orders': len(rows),
        'units': units,
        'aov': round(revenue / len(rows), 1) if rows else 0,
        'margin': round(100 * profit / revenue, 1) if revenue else 0,
    }


def growth(now, before):
    return round(100 * (now - before) / before, 1) if before else None


# ---------------------------------------------------------------- sample data
CATALOG = [  # sku, name, category, price, cost
    ('BEV01', 'Filter Coffee', 'Beverages', 40, 12), ('BEV02', 'Masala Chai', 'Beverages', 20, 6),
    ('BEV03', 'Cold Coffee', 'Beverages', 90, 30), ('BEV04', 'Fresh Lime Soda', 'Beverages', 50, 14),
    ('BAK01', 'Butter Croissant', 'Bakery', 70, 25), ('BAK02', 'Chocolate Muffin', 'Bakery', 60, 22),
    ('BAK03', 'Whole Wheat Bread', 'Bakery', 55, 30), ('BAK04', 'Sourdough Loaf', 'Bakery', 150, 70),
    ('SNK01', 'Veg Puff', 'Snacks', 30, 12), ('SNK02', 'Samosa', 'Snacks', 20, 7),
    ('SNK03', 'Club Sandwich', 'Snacks', 80, 32), ('SNK04', 'Cookie Pack', 'Snacks', 90, 40),
    ('MEL01', 'Veg Biryani', 'Meals', 140, 60), ('MEL02', 'Paneer Wrap', 'Meals', 110, 45),
    ('MEL03', 'Pasta Bowl', 'Meals', 160, 65), ('MEL04', 'Idli Combo', 'Meals', 60, 22),
]
NAMES = ['Aarav', 'Meera', 'Karthik', 'Divya', 'Rohan', 'Ananya',
         'Vikram', 'Priya', 'Suresh', 'Lakshmi', 'Arjun', 'Nisha']
BUSY_HOURS = [8, 9, 10, 12, 13, 14, 17, 18, 19, 20]   # hours when the cafe is busier


def make_orders(rnd, customer_ids, days, per_day=14):
    """Create fake orders for the last `days` days."""
    rows = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for days_ago in range(days, -1, -1):
        day = today - timedelta(days=days_ago)
        count = per_day * (1.5 if day.weekday() >= 5 else 1)   # busier weekends
        count = int(count * rnd.uniform(0.8, 1.2))
        if days_ago == 0:
            count = 3                                           # today is only partly done

        for _ in range(count):
            hour = rnd.choice(BUSY_HOURS) if days_ago else 8
            items = []
            for sku, name, category, price, cost in rnd.sample(CATALOG, rnd.randint(1, 3)):
                items.append({'sku': sku, 'name': name, 'category': category,
                              'qty': rnd.choice([1, 1, 2, 3]), 'price': price, 'cost': cost})
            total = sum(i['qty'] * i['price'] for i in items)
            cost = sum(i['qty'] * i['cost'] for i in items)
            customer = rnd.choice(customer_ids) if rnd.random() < 0.4 else None   # others are walk-ins
            when = day + timedelta(hours=hour, minutes=rnd.randint(0, 59))
            rows.append({
                'ref': '%08x' % rnd.getrandbits(32),
                'customer_id': customer,
                'items': items,
                'total': total,
                'profit': total - cost,
                'payment': rnd.choice(PAYMENTS),
                'ts': when.isoformat(timespec='minutes'),
            })
    return rows


@app.get('/api/health')
def health():
    return jsonify(ok=True, db=DB_PATH, tinydb=version('tinydb'))


@app.post('/api/seed')
def seed():
    rnd = random.Random(42)
    db.drop_tables()

    products.insert_multiple([
        {'sku': sku, 'name': name, 'category': cat, 'price': price, 'cost': cost,
         'stock': rnd.randint(4, 70), 'reorder_level': 15}
        for sku, name, cat, price, cost in CATALOG
    ])

    people = []
    for i, name in enumerate(NAMES):
        person = {'name': name, 'phone': '98%08d' % rnd.randint(0, 99999999)}
        if i % 3 == 0:
            person['email'] = name.lower() + '@example.com'   # only some have an email
        people.append(person)
    customer_ids = customers.insert_multiple(people)

    orders.insert_multiple(make_orders(rnd, customer_ids, 60))
    return jsonify(ok=True, orders=len(orders),
                   query='db.drop_tables(); products.insert_multiple([...]); '
                         'customers.insert_multiple([...]); orders.insert_multiple([...])')


# ---------------------------------------------------------------- products
def read_product(data):
    """Check and clean the product form."""
    sku = str(data.get('sku', '')).strip().upper()
    name = str(data.get('name', '')).strip()
    category = str(data.get('category', '')).strip()
    if not sku or not name or not category:
        raise ValueError('SKU, name and category are required')
    return {
        'sku': sku, 'name': name, 'category': category,
        'price': to_number(data.get('price'), 'Price', float, 0.01),
        'cost': to_number(data.get('cost'), 'Cost'),
        'stock': to_number(data.get('stock'), 'Stock', int),
        'reorder_level': to_number(data.get('reorder_level', 15), 'Reorder level', int),
    }


@app.get('/api/products')
def list_products():
    category = request.args.get('category')
    text = request.args.get('q')

    if category and text:
        rows = products.search((Q.category == category) & Q.name.search(text, flags=2))
        shown = f"products.search((Q.category == '{category}') & Q.name.search('{text}'))"
    elif category:
        rows = products.search(Q.category == category)
        shown = f"products.search(Q.category == '{category}')"
    elif text:
        rows = products.search(Q.name.search(text, flags=2))   # flags=2 means ignore case
        shown = f"products.search(Q.name.search('{text}'))"
    else:
        rows = products.all()
        shown = 'products.all()'

    if request.args.get('low'):
        rows = [p for p in rows if p['stock'] <= p['reorder_level']]
        shown += ' + filter stock <= reorder_level'
    return jsonify(items=[with_id(p) for p in rows], query=shown)


@app.post('/api/products')
def add_product():
    try:
        doc = read_product(request.get_json(force=True))
    except ValueError as e:
        return error(str(e))
    if products.contains(Q.sku == doc['sku']):
        return error('That SKU already exists', 409)
    return jsonify(id=products.insert(doc), query=f'products.insert({doc})'), 201


@app.put('/api/products/<int:product_id>')
def edit_product(product_id):
    old = products.get(doc_id=product_id)
    if old is None:
        return error('Not found', 404)
    try:
        doc = read_product(request.get_json(force=True))
    except ValueError as e:
        return error(str(e))
    # the new SKU must not belong to a different product
    clash = products.get(Q.sku == doc['sku'])
    if clash is not None and clash.doc_id != product_id:
        return error('That SKU already exists', 409)
    products.update(doc, doc_ids=[product_id])
    return jsonify(id=product_id, query=f'products.update({doc}, doc_ids=[{product_id}])')


@app.delete('/api/products/<int:product_id>')
def delete_product(product_id):
    if not products.contains(doc_id=product_id):
        return error('Not found', 404)
    products.remove(doc_ids=[product_id])
    return jsonify(ok=True, query=f'products.remove(doc_ids=[{product_id}])')


# ---------------------------------------------------------------- customers
@app.get('/api/customers')
def list_customers():
    # TinyDB has no JOIN, so add up each customer's orders by hand.
    spent, count = {}, {}
    for order in orders.all():
        cid = order.get('customer_id')
        if cid:
            spent[cid] = spent.get(cid, 0) + order['total']
            count[cid] = count.get(cid, 0) + 1

    items = []
    for c in customers.all():
        item = with_id(c)
        item['orders'] = count.get(c.doc_id, 0)
        item['spent'] = spent.get(c.doc_id, 0)
        items.append(item)
    return jsonify(items=items, query='customers.all() + add up orders by customer_id  # manual join')


@app.post('/api/customers')
def add_customer():
    data = request.get_json(force=True)
    name = str(data.get('name', '')).strip()
    if not name:
        return error('Name is required')
    doc = {'name': name, 'phone': str(data.get('phone', '')).strip()}
    email = str(data.get('email', '')).strip()
    if email:
        doc['email'] = email       # optional field: TinyDB does not need a fixed schema
    return jsonify(id=customers.insert(doc), query=f'customers.insert({doc})'), 201


@app.delete('/api/customers/<int:customer_id>')
def delete_customer(customer_id):
    if not customers.contains(doc_id=customer_id):
        return error('Not found', 404)
    customers.remove(doc_ids=[customer_id])
    return jsonify(ok=True, query=f'customers.remove(doc_ids=[{customer_id}])')


# ---------------------------------------------------------------- orders
@app.get('/api/orders')
def list_orders():
    limit = request.args.get('limit', 15, type=int)
    payment = request.args.get('payment')

    if payment:
        rows = orders.search(Q.payment == payment)
        shown = f"orders.search(Q.payment == '{payment}')"
    else:
        rows = orders.all()
        shown = 'orders.all()  # newest first, customer name looked up by hand'

    newest = sorted(rows, key=lambda o: o['ts'], reverse=True)[:limit]
    items = []
    for o in newest:
        item = with_id(o)
        if not o.get('customer_id'):
            item['customer'] = 'Walk-in'
        else:
            c = customers.get(doc_id=o['customer_id'])
            item['customer'] = c['name'] if c else '(removed)'
        items.append(item)
    return jsonify(items=items, count=len(orders), query=shown)


@app.post('/api/orders')
def new_order():
    data = request.get_json(force=True)

    # 1. add up the quantity wanted for each SKU
    wanted = {}
    for line in data.get('items', []):
        try:
            qty = int(line.get('qty'))
        except (TypeError, ValueError):
            return error('Quantity must be a number')
        if qty < 1:
            return error('Quantity must be at least 1')
        sku = str(line.get('sku'))
        wanted[sku] = wanted.get(sku, 0) + qty
    if not wanted:
        return error('Add at least one item')
    if data.get('payment') not in PAYMENTS:
        return error('Choose a payment method')

    customer_id = data.get('customer_id') or None
    if customer_id is not None:
        customer_id = int(customer_id)
        if not customers.contains(doc_id=customer_id):
            return error('Customer not found', 404)

    # 2. check stock and copy the current price into the order
    items = []
    for sku, qty in wanted.items():
        product = products.get(Q.sku == sku)
        if product is None:
            return error(f'Unknown product {sku}', 404)
        if product['stock'] < qty:
            return error(f"Only {product['stock']} of {product['name']} in stock", 409)
        items.append({'sku': sku, 'name': product['name'], 'category': product['category'],
                      'qty': qty, 'price': product['price'], 'cost': product['cost']})

    # 3. reduce stock, then save the order
    for item in items:
        products.update(subtract('stock', item['qty']), Q.sku == item['sku'])

    total = sum(i['qty'] * i['price'] for i in items)
    profit = total - sum(i['qty'] * i['cost'] for i in items)
    order = {
        'ref': '%08x' % random.getrandbits(32),
        'customer_id': customer_id,
        'items': items,
        'total': total,
        'profit': profit,
        'payment': data['payment'],
        'ts': datetime.now().isoformat(timespec='minutes'),
    }
    return jsonify(id=orders.insert(order), total=total,
                   query=f"orders.insert({{... {len(items)} items, total: {total}}}); "
                         f"products.update(subtract('stock', n), Q.sku == ...)"), 201


# ---------------------------------------------------------------- analytics
@app.get('/api/analytics')
def analytics():
    days = max(1, min(request.args.get('days', 30, type=int), 365))
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    prev_start = start - timedelta(days=days)

    # TinyDB has no GROUP BY: fetch the rows, then add them up in Python.
    rows = orders.search(Q.ts >= start.isoformat())
    prev = orders.search((Q.ts >= prev_start.isoformat()) & (Q.ts < start.isoformat()))
    now_kpi, prev_kpi = sum_orders(rows), sum_orders(prev)

    per_day = {}        # date -> [revenue, profit, order count]
    per_category = {}   # category -> revenue
    per_product = {}    # product name -> [units, revenue]
    per_payment = {}    # payment -> revenue
    per_hour = {}       # hour -> order count
    per_weekday = {}    # 0..6 -> revenue
    per_customer = {}   # customer id -> spent

    for o in rows:
        when = datetime.fromisoformat(o['ts'])
        d = per_day.setdefault(when.date().isoformat(), [0, 0, 0])
        d[0] += o['total']
        d[1] += o['profit']
        d[2] += 1
        per_payment[o['payment']] = per_payment.get(o['payment'], 0) + o['total']
        per_hour[when.hour] = per_hour.get(when.hour, 0) + 1
        per_weekday[when.weekday()] = per_weekday.get(when.weekday(), 0) + o['total']
        if o.get('customer_id'):
            per_customer[o['customer_id']] = per_customer.get(o['customer_id'], 0) + o['total']
        for i in o['items']:
            money = i['qty'] * i['price']
            per_category[i['category']] = per_category.get(i['category'], 0) + money
            p = per_product.setdefault(i['name'], [0, 0])
            p[0] += i['qty']
            p[1] += money

    dates = [(start + timedelta(days=k)).isoformat() for k in range(days)]
    zero = [0, 0, 0]
    top_products = sorted(per_product.items(), key=lambda kv: kv[1][1], reverse=True)[:8]
    top_customers = sorted(per_customer.items(), key=lambda kv: kv[1], reverse=True)[:5]
    names = {c.doc_id: c['name'] for c in customers.all()}
    all_products = products.all()

    return jsonify(
        days=days,
        kpis=now_kpi,
        previous=prev_kpi,
        growth={'revenue': growth(now_kpi['revenue'], prev_kpi['revenue']),
                'orders': growth(now_kpi['orders'], prev_kpi['orders']),
                'profit': growth(now_kpi['profit'], prev_kpi['profit'])},
        daily={'labels': dates,
               'revenue': [per_day.get(x, zero)[0] for x in dates],
               'profit': [per_day.get(x, zero)[1] for x in dates],
               'orders': [per_day.get(x, zero)[2] for x in dates]},
        category={'labels': list(per_category), 'values': list(per_category.values())},
        top_products={'labels': [name for name, _ in top_products],
                      'values': [v[1] for _, v in top_products],
                      'units': [v[0] for _, v in top_products]},
        payment={'labels': [p.upper() for p in per_payment], 'values': list(per_payment.values())},
        hours={'labels': [f'{h}:00' for h in range(8, 22)],
               'values': [per_hour.get(h, 0) for h in range(8, 22)]},
        weekday={'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                 'values': [per_weekday.get(k, 0) for k in range(7)]},
        top_customers=[{'name': names.get(cid, '(removed)'), 'spent': s} for cid, s in top_customers],
        low_stock=[with_id(p) for p in all_products if p['stock'] <= p['reorder_level']],
        inventory_value=sum(p['stock'] * p['cost'] for p in all_products),
        query=f"orders.search(Q.ts >= '{start.isoformat()}')  # then add up by day, category, product in Python",
    )



@app.get('/api/tables')
def tables():
    """Show every TinyDB table: row count, the fields found in its documents, and its rows."""
    names = sorted(db.tables())
    name = request.args.get('name') or (names[0] if names else None)
    limit = request.args.get('limit', 25, type=int)
    info = [{'name': n, 'count': len(db.table(n))} for n in names]
    if name not in names:
        return jsonify(tables=info, name=name, fields=[], rows=[], total=0,
                       query='db.tables()', note='No tables yet. Use Tools > Load sample data.')
    rows = db.table(name).all()
    # TinyDB has no fixed schema, so list the fields that appear and how many documents have each.
    seen = {}
    for r in rows:
        for key in r:
            seen[key] = seen.get(key, 0) + 1
    fields = [{'name': k, 'count': c} for k, c in seen.items()]
    newest = [with_id(r) for r in rows[-limit:]][::-1]       # newest rows first
    return jsonify(tables=info, name=name, fields=fields, rows=newest, total=len(rows),
                   query=f"db.tables(); {name}.all()  # {len(rows)} documents, showing the last {len(newest)}")

# ---------------------------------------------------------------- tools
@app.post('/api/merge')
def merge():
    """Copy new products and orders from another outlet's file into this one."""
    path = (request.get_json(force=True) or {}).get('path', '')
    if not path.lower().endswith('.json') or not os.path.isfile(path):
        return error('Pick a valid ShopPulse .json file')
    if os.path.abspath(path) == os.path.abspath(DB_PATH):
        return error('That is the current database file')

    added = skipped = new_products = 0
    try:
        other = TinyDB(path)
        for p in other.table('products').all():
            if 'sku' in p and not products.contains(Q.sku == p['sku']):
                products.insert(dict(p))
                new_products += 1
        for o in other.table('orders').all():
            if 'ref' not in o or orders.contains(Q.ref == o['ref']):
                skipped += 1            # already here (same ref) or not a ShopPulse order
                continue
            order = dict(o)
            order['customer_id'] = None   # customer ids differ per file, so these become walk-ins
            orders.insert(order)
            added += 1
        other.close()
    except Exception as e:
        return error(f'Could not read file: {e}')
    return jsonify(added=added, skipped=skipped, new_products=new_products,
                   query="for o in other.table('orders'): if not orders.contains(Q.ref == o['ref']): orders.insert(dict(o))")


@app.post('/api/backup')
def backup():
    path = (request.get_json(force=True) or {}).get('path', '')
    if not path.lower().endswith('.json'):
        return error('Choose a .json destination')
    shutil.copyfile(DB_PATH, path)
    return jsonify(ok=True, query="shutil.copyfile('shoppulse.json', backup.json)  # the whole business is one file")


@app.get('/api/raw')
def raw():
    with open(DB_PATH, encoding='utf-8') as f:
        data = json.load(f)
    if 'orders' in data:   # orders are a dict of id -> order; show only a few
        data['orders'] = dict(list(data['orders'].items())[:6])
    return jsonify(data=data, path=DB_PATH, note='orders trimmed to the first 6 for display',
                   query='open(shoppulse.json)  # human-readable JSON on disk')


@app.get('/api/benchmark')
def benchmark():
    """Time a few TinyDB operations on 10,000 fake orders in a temporary file."""
    def timed(func):
        start = time.perf_counter()
        func()
        return round((time.perf_counter() - start) * 1000, 2)   # milliseconds

    rows = make_orders(random.Random(7), [1, 2, 3], 700)[:10000]
    with tempfile.TemporaryDirectory() as tmp:
        big = TinyDB(os.path.join(tmp, 'big.json'))
        table = big.table('orders')
        insert_ms = timed(lambda: table.insert_multiple(rows))
        aggregate_ms = timed(lambda: [o['total'] for o in table.all()])
        scan_ms = timed(lambda: table.search(Q.total > 500))       # reads every row
        doc_id_ms = timed(lambda: table.get(doc_id=5000))          # direct lookup
        count = len(table)
        big.close()

        # 200 inserts: normal storage writes the file every time, the cache writes once.
        plain = TinyDB(os.path.join(tmp, 'plain.json'))
        plain_ms = timed(lambda: [plain.insert(o) for o in rows[:200]])
        plain.close()
        cached = TinyDB(os.path.join(tmp, 'cached.json'), storage=CachingMiddleware(JSONStorage))
        cached_ms = timed(lambda: [cached.insert(o) for o in rows[:200]])
        cached.close()

    return jsonify(orders=count, insert_ms=insert_ms, aggregate_ms=aggregate_ms, scan_ms=scan_ms,
                   doc_id_ms=doc_id_ms, plain_200_ms=plain_ms, cached_200_ms=cached_ms,
                   query='orders.all() -> revenue per day;  orders.search(Q.total > 500);  orders.get(doc_id=5000)')



# ---------------------------------------------------------------- web UI
# Serving the frontend from Flask means the project runs with Python only:  python backend/app.py
@app.get('/')
def home():
    return send_from_directory(FRONTEND, 'index.html')


@app.get('/<path:name>')
def frontend_files(name):
    return send_from_directory(FRONTEND, name)


if __name__ == '__main__':
    # TinyDB is not thread-safe, so serve one request at a time.
    print('ShopPulse running -> open http://127.0.0.1:%s in your browser' % os.environ.get('PORT', 5050))
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5050)), debug=False, threaded=False)
