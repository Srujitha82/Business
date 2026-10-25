# ShopPulse: sales and inventory analytics for a neighbourhood cafe

Case study project for **TinyDB**. Frontend: Electron (HTML, CSS, JavaScript, Chart.js). Backend: Python Flask REST API using TinyDB.

```
Electron window (frontend/)  --HTTP/JSON-->  Flask API (backend/app.py)  -->  TinyDB  -->  shoppulse.json
        main.js starts and stops the Python backend automatically
```

**Business problem:** a small cafe and bakery runs on one billing laptop. It needs to record sales, track stock and see what sells, with no server and no monthly software bill. Everything lives in a single JSON file.

**Data model (3 TinyDB tables):** `products`, `customers`, `orders`. Each order **embeds its line items** as nested documents, so reading or aggregating sales needs no JOIN. In MySQL this would be `orders` + `order_items` tables.

## Try it online (GitHub Pages demo)
The `frontend/` folder is a static site. On GitHub Pages it runs in **demo mode**: no backend is found, so the app keeps its data in your browser, loads 60 days of sample sales and shows the equivalent TinyDB call for every action. Merge and Benchmark need the real backend, so they are disabled online.

Publish: push this repo to GitHub, then **Settings > Pages > Deploy from a branch > main / (root)**. The link is `https://<your-username>.github.io/<repo-name>/`.

## Run on Windows (real TinyDB backend)
1. Install **Node.js LTS** (nodejs.org) and **Python 3** (tick "Add Python to PATH").
2. Open Command Prompt in this folder:
   ```
   pip install -r backend/requirements.txt
   npm install
   npm start
   ```
3. In the app, go to **Tools > Load sample data**, then open **Dashboard**.

The database file lives in Electron's user-data folder (`%APPDATA%\shoppulse\shoppulse.json`). To run the backend alone: `python backend/app.py` (API on http://127.0.0.1:5050).

## Demo script (5 minutes, maps to the rubric)
| Step | What to do | What it shows |
|---|---|---|
| 1 | Tools > Load sample data | `insert_multiple`, tables created on first insert |
| 2 | Dashboard: switch 7 / 30 / 60 days | `search(Q.ts >= ...)` plus Python aggregation, 5 live charts |
| 3 | Products: filter by category, low stock only | `search` with `&`, regex `search()` |
| 4 | Add a product, edit it, delete it | `insert`, `update`, `remove` |
| 5 | Customers: add one with an email, one without | schema-less documents |
| 6 | Sales: ring up a sale, then try to oversell | nested documents, `subtract`, error handling |
| 7 | Dashboard again | the new sale appears in the charts |
| 8 | Tools > Merge another outlet's file | offline consolidation by `ref` |
| 9 | Tools > Run benchmark | scan vs doc_id lookup, `CachingMiddleware` chart |
| 10 | Tools > Show raw JSON | the whole business is one readable file |

The bar at the bottom of the window always shows the exact TinyDB call behind the last action. Point to it during the demo.

## Honest limitations (use on your slides)
- No GROUP BY or JOIN: totals are aggregated in Python.
- No indexes: every query scans the table.
- No ACID and not thread-safe, so the backend serves one request at a time.
- Merged orders from another outlet become walk-ins, because customer ids are per file.
- No authentication: anyone with the file can read it.

## Files
`main.js` Electron main process · `preload.js` file dialogs · `frontend/` UI, charts and demo mode · `backend/app.py` API and TinyDB logic
