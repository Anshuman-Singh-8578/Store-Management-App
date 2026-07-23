# General Store — Demand Insights & Billing System

A full-stack retail management app combining SQL-driven sales analytics, item-level demand tracking, and a supermarket-style point-of-sale system with automatic inventory updates and discount logic.

**Live demo:** [https://store-management-ai.netlify.app](https://store-management-ai.netlify.app)
**Backend API:** [https://store-management-app-86sz.onrender.com/docs](https://store-management-app-86sz.onrender.com/docs)

> Note: the backend runs on a free-tier host and may take 30-60 seconds to wake up on first load.

---

## What this does

Small shops often track inventory and sales on paper or basic spreadsheets, making it hard to know what's actually selling, what's about to run out, and how much to reorder. This app gives a shop owner:

- A **product catalog browsable by category**, with a real point-of-sale billing flow (search, add to cart, checkout, itemized receipt)
- **Automatic inventory deduction** on every sale, with atomic transaction handling so a failed sale never leaves partial data behind
- **Per-item sales history** (last 7/14 days) to see exactly how a specific product has been performing
- **Automatic restock suggestions**, flagging items that are either selling fast relative to stock, or just low in absolute terms
- **Discount logic**: tiered discounts on bill total, "Buy X Get Y Free" promotions, and time-boxed seasonal category discounts
- **Top-selling items** over any custom date range, and a 30-day sales trend chart

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Frontend       │─────▶│   Backend         │─────▶│   Database       │
│   HTML/CSS/JS     │      │   FastAPI          │      │   MySQL (Aiven)  │
│   (Netlify)       │      │   (Render)         │      │                   │
└─────────────────┘      └──────────────────┘      └─────────────────┘
```

- **Frontend**: Vanilla HTML/CSS/JS (no framework) — multi-page single-file app with client-side routing, Chart.js for data visualization, a product grid with category filtering, and a dedicated cart/checkout flow.
- **Backend**: FastAPI (Python), exposing REST endpoints for billing, inventory, and analytics.
- **Database**: MySQL, hosted on Aiven. Three core tables: `sales` (historical demand data), `inventory` (live stock + pricing), `transactions` (per-sale, per-item log).
- **Deployment**: GitHub → Render (backend, auto-deploy on push) and Netlify (frontend, static hosting).

---

## Key technical details

**Atomic billing transactions.** Every sale writes to `transactions` and decrements `inventory` inside a single database transaction (`engine.begin()`), so a multi-item bill either fully succeeds or fully rolls back — verified by deliberately testing an insufficient-stock scenario mid-bill and confirming no partial writes occurred.

**Discount engine.** Applied server-side at checkout:
- Tiered discount on paid subtotal (₹500 → 5%, ₹1000 → 10%, ₹5000 → 20%)
- "Buy X Get Y Free" rules (e.g. buy 2 of item A, get 1 of item B free), computed via integer division on requested quantities, with its own stock check before granting the free item
- Seasonal category discounts, active only within a configured date range

**Reorder suggestions.** Combines two signals: sales velocity (units sold in the last N days ÷ N, projected against current stock to estimate days-of-stock-remaining) and an absolute low-stock threshold, so an item gets flagged whether it's selling fast *or* just running low regardless of recent activity.

**Secrets handling.** Database credentials are read from environment variables (`python-dotenv` locally, Render's environment variable store in production) — never hardcoded or committed to source control.

---

## Tech stack

`Python` · `FastAPI` · `SQLAlchemy` · `MySQL` · `scikit-learn` (data exploration) · `pandas` · `HTML/CSS/JavaScript` · `Chart.js` · `Render` · `Netlify` · `Aiven`

---

## Running locally

```bash
# Backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Create a .env file with your database credentials (see .env.example)

uvicorn backend:app --reload
```

Then open `frontend/index.html` in a browser (update `API_URL` in the script to `http://127.0.0.1:8000` for local testing).

---

## Possible next steps

- Multi-store support (currently scoped to a single store)
- Role-based login (cashier vs. owner views)
- Exportable sales reports (CSV/PDF)
