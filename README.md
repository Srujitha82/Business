# ShopPulse: sales and inventory analytics for a neighbourhood cafe

Database case study project for **TinyDB** (document-oriented, pure-Python, file-based database).
Backend: Python **Flask** REST API on TinyDB. Frontend: HTML, CSS, JavaScript and Chart.js.
The same frontend also runs inside an **Electron** window (optional).

```
Browser / Electron window (frontend/)  --HTTP/JSON-->  Flask API (backend/app.py)  -->  TinyDB  -->  shoppulse.json
```

**Business problem:** a small cafe and bakery runs on one billing laptop. It needs to record sales, track stock and
see what sells, with no database server and no monthly software bill. Everything lives in one readable JSON file.

**Data model (3 TinyDB tables):** `products`, `customers`, `orders`. Each order **embeds its line items** as nested
documents, so reading a sale needs no JOIN. In MySQL this would be `orders` + `order_items` tables.

## Run it (easiest: Python only)
1. Install **Python 3.9+** (tick "Add Python to PATH" on Windows).
2. **Windows:** double-click `run.bat`.  **Mac/Linux:** `bash run.sh`
   (or manually: `pip install -r backend/requirements.txt` then `python backend/app.py`).
3. Open **http://127.0.0.1:5050** (use `127.0.0.1`, not `localhost`).
4. Go to **Tools > Load sample data** (60 days, about 900 orders), then open **Dashboard**.

The database file is created at `backend/data/shoppulse.json`.

## Optional: desktop (Electron) window
Needs Node.js LTS as well: `pip install -r backend/requirements.txt`, `npm install`, `npm start`.
(`main.js` starts and stops the Python backend automatically.)

## No install at all: GitHub Pages demo
`frontend/` is a static site. If no backend is found it switches to **demo mode** (data kept in the browser, 60 days of sample
sales, the equivalent TinyDB call shown for every action). Merge and Benchmark need the real backend.
Publish: push to GitHub, then **Settings > Pages > Deploy from a branch > main / (root)**.
Link: `https://<your-username>.github.io/<repo-name>/`

## Hands-on demo from the command line
```
python backend/demo_queries.py
```
Prints CRUD, AND/OR/NOT, regex, nested-document queries, `exists()`, `upsert`, a manual JOIN and GROUP BY,
scan-vs-lookup timing and the CachingMiddleware speed-up, each with its output. Good for screenshots on slides.

## The "Database Tables" tab
Shows every TinyDB table with its row count, the **fields found** in its documents (for example `email: 4 / 12 docs`
proves the schema is flexible) and the latest rows. Nested order items appear as `3 nested: 2x Samosa, ...`.

## Live demo script (5 minutes)
| Step | What to do | What it shows |
|---|---|---|
| 1 | Tools > Load sample data | `insert_multiple`, tables created on first insert |
| 2 | Database Tables tab: products, customers, orders | the 3 tables, nested documents, optional `email` field |
| 3 | Dashboard: switch 7 / 30 / 60 days | `search(Q.ts >= ...)` plus Python aggregation, live charts |
| 4 | Products: filter by category, low stock only | `search` with `&`, regex `search()` |
| 5 | Add a product, edit it, delete it | `insert`, `update`, `remove` |
| 6 | Sales: ring up a sale, then try to oversell | nested documents, `subtract`, error handling |
| 7 | Database Tables > orders | the new sale is the newest document |
| 8 | Tools > Run benchmark | scan vs lookup, `CachingMiddleware` chart |
| 9 | Tools > Show raw JSON | the whole business is one readable file |
| 10 | Terminal: `python backend/demo_queries.py` | every query type with output |

The bar at the bottom of the window always shows the exact TinyDB call behind the last action. Point to it.

## Honest limitations (use on your slides)
- No GROUP BY or JOIN: totals are aggregated in Python.
- No indexes: every query scans the table, and TinyDB re-reads the file on every operation.
- No ACID transactions and not thread-safe, so the backend serves one request at a time (`threaded=False`).
- Merged orders from another outlet become walk-ins, because customer ids are per file.
- No authentication or encryption: anyone with the file can read it.

## Files
| Path | Purpose |
|---|---|
| `backend/app.py` | Flask API and all TinyDB logic |
| `backend/demo_queries.py` | command-line hands-on demo |
| `frontend/` | UI, charts, demo mode (`index.html`, `app.js`, `demo.js`, `styles.css`, `vendor/chart.umd.js`) |
| `main.js`, `preload.js`, `package.json` | optional Electron wrapper |
| `docs/CASE_STUDY_GUIDE.md` | what to put on each slide, MySQL comparison, viva answers |
