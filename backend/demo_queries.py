"""ShopPulse: TinyDB hands-on demo.  Run:  python backend/demo_queries.py

Prints every TinyDB operation the case study talks about (create, read, update, delete,
nested queries, a manual JOIN, aggregation, 'indexing', caching) with its output,
so you can show it live or take screenshots for the slides.  Uses its own file
(backend/data/demo_queries.json) and never touches the app's database.
"""
import os
import random
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
DEMO_FILE = os.path.join(DATA, 'demo_queries.json')
os.makedirs(DATA, exist_ok=True)
if os.path.exists(DEMO_FILE):
    os.remove(DEMO_FILE)
os.environ['SHOPPULSE_DB'] = os.path.join(DATA, '_unused.json')   # keep app.py away from the real file

from tinydb import TinyDB, Query                                  # noqa: E402
from tinydb.operations import add, subtract                       # noqa: E402
from tinydb.storages import JSONStorage                           # noqa: E402
from tinydb.middlewares import CachingMiddleware                  # noqa: E402
from app import CATALOG, NAMES, make_orders                       # noqa: E402  (sample-data helpers)

Q = Query()


def title(text):
    print('\n' + '=' * 70 + '\n' + text + '\n' + '=' * 70)


def show(code, result):
    print(f'>>> {code}')
    print(f'    {result}\n')


db = TinyDB(DEMO_FILE, indent=2)
products, customers, orders = db.table('products'), db.table('customers'), db.table('orders')

# ------------------------------------------------------------------ 1. CREATE
title('1. CREATE  (tables appear on first insert, no CREATE TABLE needed)')
ids = products.insert_multiple([{'sku': s, 'name': n, 'category': c, 'price': p, 'cost': k,
                                 'stock': random.Random(i).randint(4, 70), 'reorder_level': 15}
                                for i, (s, n, c, p, k) in enumerate(CATALOG)])
show('products.insert_multiple([...16 documents...])', f'document ids {ids[0]}..{ids[-1]}')
cids = customers.insert_multiple([{'name': n, 'phone': '98%08d' % i,
                                   **({'email': n.lower() + '@example.com'} if i % 3 == 0 else {})}
                                  for i, n in enumerate(NAMES)])
show('customers.insert_multiple([...12 documents...])  # only some have "email"', f'{len(customers)} customers')
orders.insert_multiple(make_orders(random.Random(42), cids, 60))
show('orders.insert_multiple([...])  # each order embeds its line items', f'{len(orders)} orders')
show('db.tables()', db.tables())
show('orders.get(doc_id=1)  # one nested document', orders.get(doc_id=1))

# ------------------------------------------------------------------ 2. READ
title('2. READ  (Query objects instead of SQL WHERE)')
show("products.search(Q.category == 'Bakery')",
     [p['name'] for p in products.search(Q.category == 'Bakery')])
show('products.search((Q.price > 60) & (Q.stock < 30))   # AND',
     [(p['name'], p['price'], p['stock']) for p in products.search((Q.price > 60) & (Q.stock < 30))])
show("products.search((Q.category == 'Meals') | (Q.category == 'Snacks'))   # OR",
     len(products.search((Q.category == 'Meals') | (Q.category == 'Snacks'))))
show("products.search(~(Q.category == 'Beverages'))   # NOT", len(products.search(~(Q.category == 'Beverages'))))
show("products.search(Q.name.search('coffee', flags=2))   # regex, ignore case",
     [p['name'] for p in products.search(Q.name.search('coffee', flags=2))])
show('customers.search(Q.email.exists())   # schema-less: only documents that have the field',
     [c['name'] for c in customers.search(Q.email.exists())])
show('customers.search(~Q.email.exists())', len(customers.search(~Q.email.exists())))
show("orders.search(Q.items.any(Q.sku == 'BAK01'))   # query INSIDE the nested list",
     f"{len(orders.search(Q.items.any(Q.sku == 'BAK01')))} orders contain a croissant")
show("orders.search(Q.payment.one_of(['upi', 'card']) & (Q.total > 400))",
     len(orders.search(Q.payment.one_of(['upi', 'card']) & (Q.total > 400))))
show("orders.count(Q.payment == 'cash')", orders.count(Q.payment == 'cash'))

# ------------------------------------------------------------------ 3. UPDATE
title('3. UPDATE')
before = products.get(Q.sku == 'BEV01')['stock']
products.update(subtract('stock', 5), Q.sku == 'BEV01')
show("products.update(subtract('stock', 5), Q.sku == 'BEV01')",
     f"stock {before} -> {products.get(Q.sku == 'BEV01')['stock']}")
products.update({'price': 45}, Q.sku == 'BEV01')
show("products.update({'price': 45}, Q.sku == 'BEV01')", f"price now {products.get(Q.sku == 'BEV01')['price']}")
products.update(add('stock', 50), Q.category == 'Bakery')
show("products.update(add('stock', 50), Q.category == 'Bakery')   # many documents at once",
     [(p['name'], p['stock']) for p in products.search(Q.category == 'Bakery')])
products.upsert({'sku': 'NEW01', 'name': 'Brownie', 'category': 'Bakery', 'price': 80, 'cost': 30,
                 'stock': 20, 'reorder_level': 10}, Q.sku == 'NEW01')
show("products.upsert({...NEW01...}, Q.sku == 'NEW01')   # insert if missing, update if present",
     products.get(Q.sku == 'NEW01')['name'])

# ------------------------------------------------------------------ 4. DELETE
title('4. DELETE')
products.remove(Q.sku == 'NEW01')
show("products.remove(Q.sku == 'NEW01')", f"still exists? {products.contains(Q.sku == 'NEW01')}")
removed = orders.remove(Q.total < 30)
show('orders.remove(Q.total < 30)', f'{len(removed)} orders removed')

# ------------------------------------------------------------------ 5. JOIN / AGGREGATE
title('5. NO JOIN, NO GROUP BY: done by hand in Python')
names = {c.doc_id: c['name'] for c in customers.all()}
spent = {}
for o in orders.all():
    if o.get('customer_id'):
        spent[o['customer_id']] = spent.get(o['customer_id'], 0) + o['total']
top = sorted(spent.items(), key=lambda kv: kv[1], reverse=True)[:3]
show('manual JOIN orders.customer_id -> customers.name  (top 3 spenders)', [(names[c], t) for c, t in top])
by_cat = {}
for o in orders.all():
    for i in o['items']:
        by_cat[i['category']] = by_cat.get(i['category'], 0) + i['qty'] * i['price']
show('manual GROUP BY category  (SUM of qty * price)', by_cat)
print('    In MySQL:  SELECT category, SUM(qty*price) FROM order_items GROUP BY category;\n')

# ------------------------------------------------------------------ 6. PERFORMANCE
title('6. "INDEXING": TinyDB has none, every search scans the whole table')


def ms(fn):
    t = time.perf_counter()
    fn()
    return round((time.perf_counter() - t) * 1000, 2)


last_doc = orders.all()[-1]
last_ref, last_id = last_doc['ref'], last_doc.doc_id
show("orders.search(Q.ref == '<last order ref>')   # scan of every document",
     f"{ms(lambda: orders.search(Q.ref == last_ref))} ms")
show('orders.get(doc_id=<last id>)                  # direct lookup by id',
     f'{ms(lambda: orders.get(doc_id=last_id))} ms  (TinyDB still reads the whole file)')
rows = make_orders(random.Random(7), [1, 2, 3], 300)[:200]
plain = TinyDB(os.path.join(DATA, '_plain.json'))
cached = TinyDB(os.path.join(DATA, '_cached.json'), storage=CachingMiddleware(JSONStorage))
a = ms(lambda: [plain.insert(r) for r in rows])
b = ms(lambda: [cached.insert(r) for r in rows])
plain.close()
cached.close()
for f in ('_plain.json', '_cached.json', '_unused.json'):
    p = os.path.join(DATA, f)
    if os.path.exists(p):
        os.remove(p)
show('200 inserts, normal storage (file rewritten every time)', f'{a} ms')
show('200 inserts, CachingMiddleware (file written once)', f'{b} ms  ->  about {round(a / max(b, 0.01))}x faster')

db.close()
print(f'Done. The whole database is one readable file: {DEMO_FILE}')
