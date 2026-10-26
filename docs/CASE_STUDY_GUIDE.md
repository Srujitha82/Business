# TinyDB Case Study: what you have to do, and what to say

## 0. What the assignment actually needs from the team
1. A **PPT** following the 11 sections below (rubric: concepts, critical analysis, applications, demo, presentation).
2. A **small live demo** (this repo): installation, schema, CRUD, queries.
3. A **comparison with MySQL** (rubric objective 2). Table in section 5 below.
4. **References** slide.

You do not have to show a perfect live run. If something fails, open the **GitHub Pages demo** or show screenshots
of `python backend/demo_queries.py`. But try the live run first: it is one command.

## 1. Slide plan (about 14 slides)
| # | Slide | Content |
|---|---|---|
| 1 | Title | "TinyDB: a tiny document database" + team names |
| 2 | Introduction | Lightweight, document-oriented database written in pure Python, no dependencies, no server. Created by Markus Siemens (GitHub: msiemens), open source, **MIT licence**. About 1,800 lines of code. Target: small apps that a SQL server would overwhelm. |
| 3 | Type and model | NoSQL, **document store**. Data = Python dicts saved as JSON. Tables = named groups of documents. Each document gets an integer `doc_id`. Best for: small desktop apps, scripts, prototypes, IoT/Raspberry Pi, config storage. |
| 4 | Architecture | Embedded library (runs inside your Python process, no client-server). Layers: **Table/Query API -> Middleware (e.g. CachingMiddleware) -> Storage (JSONStorage file, MemoryStorage)**. Show the diagram from the README. |
| 5 | Storage, indexing, queries | Storage: one JSON file, whole file read and rewritten per operation. Indexing: none (full scan; only `doc_id` direct access). Query processing: `Query()` objects evaluated on every document in Python, no optimizer. |
| 6 | Transactions and scaling | No ACID, no concurrency control, not for multi-thread/multi-process. No sharding or replication; scale = vertical only, and only to thousands of documents. Our Flask backend uses `threaded=False` because of this. |
| 7 | Core features | Query language = Python (`Q.price > 60`, `&`, `\|`, `~`, regex, `any()`, `exists()`). Operations `add`, `subtract`, `set`, `delete`, `upsert`. Extensible storages and middlewares. No built-in security, backup = copy the file, no triggers or stored procedures. |
| 8 | Strengths and limitations | Strengths: zero setup, readable file, schema-free, tiny, pure Python. Limits: slow on big data, no indexes/joins/transactions, no security, single user. |
| 9 | TinyDB vs MySQL | Table below. |
| 10 | Use cases | Prototypes, desktop tools (like ShopPulse), small Python scripts, bots, IoT devices, tests, config/cache files. Be honest: it is not used for large production systems. |
| 11 | Demo: ShopPulse | Screenshots: Database Tables tab, Dashboard, console bar with the TinyDB call, benchmark chart. |
| 12 | Performance | Our measured results (below): scan on 912 docs about 3 ms; CachingMiddleware makes 200 inserts about 35x faster. |
| 13 | Future and conclusion | Extensions (e.g. a Rust re-implementation `tinydb-rust` listed in the docs for speed), when to choose it, when to move to SQLite/MySQL/MongoDB. |
| 14 | References | See list at the bottom. |

## 2. TinyDB vs MySQL (slide 9)
| | TinyDB | MySQL |
|---|---|---|
| Model | Document (JSON-like dicts) | Relational (tables, rows, fixed columns) |
| Schema | None, fields can differ per document | Fixed, `CREATE TABLE` with types |
| Architecture | Embedded library, no server | Client-server |
| Query language | Python `Query` objects | SQL |
| JOIN / GROUP BY | No, done in Python | Yes, optimized |
| Indexes | None | B-tree, hash, full-text |
| Transactions | No ACID | Full ACID (InnoDB) |
| Concurrency | Single thread/process only | Many users |
| Security | None (file permissions only) | Users, roles, TLS, encryption |
| Backup | Copy the file | mysqldump, replication, binary logs |
| Scale | Thousands of documents | Millions to billions of rows |
| Setup | `pip install tinydb` | Install and run a server |
| Cost / licence | Free, MIT | Free community edition (GPL), owned by Oracle |

Same data in both: our `orders` document with nested `items` becomes **two tables** in MySQL
(`orders`, `order_items`) joined by `order_id`.

## 3. Our measured numbers (from `demo_queries.py` and the Tools > Benchmark tab, on one laptop)
| Test | Result |
|---|---|
| Search by field in 912 orders (full scan) | about 3 ms |
| Direct `doc_id` lookup | about 3 ms (TinyDB still reads the whole file, so no big gain) |
| 200 inserts, normal storage | about 180 ms (file rewritten every time) |
| 200 inserts, `CachingMiddleware` | about 5 ms (**about 35x faster**) |
| Benchmark tab: 10,000 orders | insert about 46 ms, aggregate about 55 ms, scan about 43 ms |
Your numbers will differ by machine. Re-run and use your own on the slide.

## 4. Likely questions and answers
- **Why TinyDB and not SQLite?** SQLite is better for most things. TinyDB was chosen to study the document model
  and a zero-setup embedded database, and to contrast it with MySQL.
- **Why embed order items?** Items are always read with their order, so no JOIN is needed. Trade-off: if a product
  is renamed, old orders keep the old name (which is actually correct for sales history).
- **Why is the Flask backend not threaded?** TinyDB is not thread-safe; its docs say not to use it from several threads.
- **How do you do a JOIN?** By hand: build a dict `customer id -> name` and look up (`list_customers` in `app.py`).
- **How do you prevent overselling?** `new_order` checks stock before `subtract('stock', qty)`. It is not a real
  transaction: two simultaneous sales could race, which is why the server is single-threaded.
- **Is there an index?** No. Every `search()` scans every document.
- **Backup/recovery?** Copy the JSON file (Tools > Back up). No point-in-time recovery.
- **Security?** None built in. Use OS file permissions or encrypt the file with a custom Storage.
- **When should you not use it?** Many users, large data, need for ACID, joins or security.

## 5. References (add the ones you actually read)
- TinyDB documentation: https://tinydb.readthedocs.io
- TinyDB source code and README: https://github.com/msiemens/tinydb
- TinyDB on PyPI: https://pypi.org/project/tinydb/
- MySQL Reference Manual: https://dev.mysql.com/doc/
- Flask documentation: https://flask.palletsprojects.com
- Chart.js documentation: https://www.chartjs.org/docs/
