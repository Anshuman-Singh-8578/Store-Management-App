from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import joblib
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from datetime import date

# --- Discount rules ---

# Tiered discount on total bill amount (highest applicable tier wins)
TIER_DISCOUNTS = [
    (5000, 20),
    (1000, 10),
    (500, 5),
]

def get_tier_discount_percent(subtotal):
    for threshold, percent in TIER_DISCOUNTS:
        if subtotal >= threshold:
            return percent
    return 0

# Buy X of one item, get Y of another item free
BOGO_RULES = [
    {"trigger_item_id": 1, "trigger_qty": 2, "free_item_id": 25, "free_qty": 1, "label": "Buy 2 Amul Milk, get 1 Cadbury Dairy Milk free"}
]

# Category/seasonal discounts, active only within a date range
SEASONAL_DISCOUNTS = [
    {"name": "Chocolate Day", "keywords": ["chocolate", "dairy milk"], "percent": 15,
     "start": date(2026, 2, 9), "end": date(2026, 2, 9)}
]

#database loading
load_dotenv()

DB_USER = os.getenv("AIVEN_DB_USER")
DB_PASSWORD = os.getenv("AIVEN_DB_PASSWORD")
DB_HOST = os.getenv("AIVEN_DB_HOST")
DB_PORT = os.getenv("AIVEN_DB_PORT")
DB_NAME = os.getenv("AIVEN_DB_NAME")

engine = create_engine(
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?use_pure=true"
)

# --- Load the trained model once, when the server starts ---
model = joblib.load("model.pkl")

# --- Create the app ---
app = FastAPI()

# Allow our frontend (a plain HTML file) to call this backend from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Define what a valid request looks like ---
class PredictionRequest(BaseModel):
    day_of_week: int
    promo: int
    sales_lag_1: float
    sales_lag_7: float

# --- The actual endpoint ---
@app.post("/predict")
def predict(request: PredictionRequest):
    input_data = pd.DataFrame([{
        "DayOfWeek": request.day_of_week,
        "Promo": request.promo,
        "sales_lag_1": request.sales_lag_1,
        "sales_lag_7": request.sales_lag_7
    }])
    prediction = model.predict(input_data)[0]
    return {"predicted_sales": round(float(prediction), 2)}

from sqlalchemy import create_engine, text

DB_USER = os.getenv("AIVEN_DB_USER")
DB_PASSWORD = os.getenv("AIVEN_DB_PASSWORD")
DB_HOST = os.getenv("AIVEN_DB_HOST")
DB_NAME = os.getenv("AIVEN_DB_NAME")
DB_PORT = os.getenv("AIVEN_DB_PORT")

engine = create_engine(
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?use_pure=true"
)

@app.get("/top-items")
def top_items(store_id: int, as_of_date: str, lookback_days: int = 14, top_n: int = 5):
    query = text("""
        SELECT s.item, i.item_name, SUM(s.sales) AS total_sales
        FROM sales s
        JOIN inventory i ON s.item = i.item_id
        WHERE s.store = :store_id
          AND s.date BETWEEN DATE_SUB(:as_of_date, INTERVAL :lookback_days DAY) AND :as_of_date
        GROUP BY s.item, i.item_name
        ORDER BY total_sales DESC
        LIMIT :top_n
    """)

    params = {
        "store_id": store_id,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "top_n": top_n
    }

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()

    return [{"item": row.item, "item_name": row.item_name, "total_sales": float(row.total_sales)} for row in result]
    
class StockUpdateRequest(BaseModel):
    item_id: int
    quantity_added: int

@app.post("/stock-up")
def stock_up(request: StockUpdateRequest):
    query = text("""
        UPDATE inventory
        SET current_stock = current_stock + :quantity
        WHERE item_id = :item_id
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"quantity": request.quantity_added, "item_id": request.item_id})
        conn.commit()

        if result.rowcount == 0:
            return {"error": "Item not found"}

    return {"item_id": request.item_id, "message": "Stock updated"}

from typing import List

class BillItem(BaseModel):
    item_id: int
    quantity: int

class BillRequest(BaseModel):
    items: List[BillItem]

@app.get("/reorder-suggestions")
def reorder_suggestions(days: int = 14):
    query = text("""
        SELECT i.item_id, i.item_name, i.current_stock,
               COALESCE(SUM(t.quantity), 0) AS units_sold_recently
        FROM inventory i
        LEFT JOIN transactions t
          ON i.item_id = t.item_id AND t.sale_date >= DATE_SUB(NOW(), INTERVAL :days DAY)
        GROUP BY i.item_id, i.item_name, i.current_stock
        ORDER BY units_sold_recently DESC
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"days": days}).fetchall()

    LOW_STOCK_THRESHOLD = 15

    suggestions = []
    for row in result:
        daily_rate = row.units_sold_recently / days
        days_of_stock_left = row.current_stock / daily_rate if daily_rate > 0 else None

        velocity_flag = daily_rate > 0 and days_of_stock_left is not None and days_of_stock_left < 7
        low_stock_flag = row.current_stock < LOW_STOCK_THRESHOLD

        should_reorder = velocity_flag or low_stock_flag

        suggestions.append({
            "item_id": row.item_id,
            "item_name": row.item_name,
            "current_stock": row.current_stock,
            "units_sold_recently": row.units_sold_recently,
            "days_of_stock_left": round(days_of_stock_left) if days_of_stock_left is not None else None,
            "should_reorder": should_reorder,
            "reason": "selling fast" if velocity_flag else ("low stock" if low_stock_flag else None)
        })

    return suggestions

@app.get("/item-sales-history")
def item_sales_history(item_id: int, days: int = 14):
    query = text("""
        SELECT DATE(sale_date) AS sale_day, SUM(quantity) AS units_sold
        FROM transactions
        WHERE item_id = :item_id
          AND sale_date >= DATE_SUB(NOW(), INTERVAL :days DAY)
        GROUP BY DATE(sale_date)
        ORDER BY sale_day
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"item_id": item_id, "days": days}).fetchall()

    return [{"date": str(row.sale_day), "units_sold": row.units_sold} for row in result]

@app.post("/bill")
def create_bill(request: BillRequest):
    receipt_items = []
    today = date.today()

    with engine.begin() as conn:
        result = conn.execute(text("SELECT COALESCE(MAX(bill_id), 0) + 1 AS next_id FROM transactions"))
        bill_id = result.scalar()

        # --- Process each requested item ---
        for item in request.items:
            row = conn.execute(
                text("SELECT item_name, price, current_stock FROM inventory WHERE item_id = :item_id"),
                {"item_id": item.item_id}
            ).fetchone()

            if row is None:
                raise Exception(f"Item {item.item_id} does not exist")
            if row.current_stock < item.quantity:
                raise Exception(f"Not enough stock for item {item.item_id}")

            # Check seasonal discount for this item
            seasonal_percent = 0
            seasonal_label = None
            for deal in SEASONAL_DISCOUNTS:
                if deal["start"] <= today <= deal["end"]:
                    if any(k in row.item_name.lower() for k in deal["keywords"]):
                        seasonal_percent = deal["percent"]
                        seasonal_label = deal["name"]
                        break

            line_total = row.price * item.quantity
            seasonal_discount_amount = round(line_total * seasonal_percent / 100)
            line_total_after_seasonal = line_total - seasonal_discount_amount

            conn.execute(
                text("INSERT INTO transactions (bill_id, item_id, quantity) VALUES (:bill_id, :item_id, :quantity)"),
                {"bill_id": bill_id, "item_id": item.item_id, "quantity": item.quantity}
            )
            conn.execute(
                text("UPDATE inventory SET current_stock = current_stock - :quantity WHERE item_id = :item_id"),
                {"quantity": item.quantity, "item_id": item.item_id}
            )

            receipt_items.append({
                "item_id": item.item_id, "item_name": row.item_name, "price": row.price,
                "quantity": item.quantity, "line_total": line_total_after_seasonal,
                "seasonal_discount": seasonal_discount_amount, "seasonal_label": seasonal_label,
                "is_free": False
            })

        # --- Check Buy X Get Y free rules ---
        requested_qty = {item.item_id: item.quantity for item in request.items}
        for rule in BOGO_RULES:
            trigger_qty_bought = requested_qty.get(rule["trigger_item_id"], 0)
            free_units_earned = (trigger_qty_bought // rule["trigger_qty"]) * rule["free_qty"]

            if free_units_earned > 0:
                free_row = conn.execute(
                    text("SELECT item_name, price, current_stock FROM inventory WHERE item_id = :item_id"),
                    {"item_id": rule["free_item_id"]}
                ).fetchone()

                if free_row and free_row.current_stock >= free_units_earned:
                    conn.execute(
                        text("INSERT INTO transactions (bill_id, item_id, quantity) VALUES (:bill_id, :item_id, :quantity)"),
                        {"bill_id": bill_id, "item_id": rule["free_item_id"], "quantity": free_units_earned}
                    )
                    conn.execute(
                        text("UPDATE inventory SET current_stock = current_stock - :quantity WHERE item_id = :item_id"),
                        {"quantity": free_units_earned, "item_id": rule["free_item_id"]}
                    )
                    receipt_items.append({
                        "item_id": rule["free_item_id"], "item_name": free_row.item_name, "price": free_row.price,
                        "quantity": free_units_earned, "line_total": 0,
                        "seasonal_discount": 0, "seasonal_label": None,
                        "is_free": True, "free_reason": rule["label"]
                    })

        # --- Tiered discount on paid subtotal ---
        paid_subtotal = sum(line["line_total"] for line in receipt_items if not line["is_free"])
        tier_percent = get_tier_discount_percent(paid_subtotal)
        tier_discount_amount = round(paid_subtotal * tier_percent / 100)

        grand_total = paid_subtotal - tier_discount_amount

    return {
        "bill_id": bill_id,
        "items": receipt_items,
        "paid_subtotal": paid_subtotal,
        "tier_discount_percent": tier_percent,
        "tier_discount_amount": tier_discount_amount,
        "grand_total": grand_total
    }

@app.get("/inventory")
def get_inventory():
    query = text("SELECT item_id, item_name, price, current_stock FROM inventory ORDER BY item_id")

    with engine.connect() as conn:
        result = conn.execute(query).fetchall()

    return [
        {"item_id": row.item_id, "item_name": row.item_name, "price": row.price, "current_stock": row.current_stock}
        for row in result
    ]

@app.get("/inventory/search")
def search_inventory(q: str):
    query = text("""
        SELECT item_id, item_name, price, current_stock
        FROM inventory
        WHERE item_name LIKE :search_term
        ORDER BY item_name
        LIMIT 10
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"search_term": f"%{q}%"}).fetchall()

    return [
        {"item_id": row.item_id, "item_name": row.item_name, "price": row.price, "current_stock": row.current_stock}
        for row in result
    ]

@app.get("/sales-history")
def sales_history(store_id: int = 1, days: int = 30):
    query = text("""
        SELECT date, SUM(sales) AS total_sales
        FROM sales
        WHERE store = :store_id
        GROUP BY date
        ORDER BY date DESC
        LIMIT :days
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"store_id": store_id, "days": days}).fetchall()

    rows = [{"date": str(row.date), "sales": row.total_sales} for row in result]
    rows.reverse()
    return rows