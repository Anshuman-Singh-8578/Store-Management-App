from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import joblib
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

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

engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

@app.get("/top-items")
def top_items(store_id: int, as_of_date: str, lookback_days: int = 14, top_n: int = 5):
    query = text("""
        SELECT item, SUM(sales) AS total_sales
        FROM sales
        WHERE store = :store_id
          AND date BETWEEN DATE_SUB(:as_of_date, INTERVAL :lookback_days DAY) AND :as_of_date
        GROUP BY item
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

    return [{"item": row.item, "total_sales": float(row.total_sales)} for row in result]
    
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

@app.post("/bill")
def create_bill(request: BillRequest):
    with engine.begin() as conn:  # begin() starts a transaction automatically
        # Get a new bill_id by finding the current max and adding 1
        result = conn.execute(text("SELECT COALESCE(MAX(bill_id), 0) + 1 AS next_id FROM transactions"))
        bill_id = result.scalar()

        for item in request.items:
            # Check enough stock exists before selling
            stock_check = conn.execute(
                text("SELECT current_stock FROM inventory WHERE item_id = :item_id"),
                {"item_id": item.item_id}
            ).scalar()

            if stock_check is None:
                raise Exception(f"Item {item.item_id} does not exist")
            if stock_check < item.quantity:
                raise Exception(f"Not enough stock for item {item.item_id}")

            # Record the sale
            conn.execute(
                text("""
                    INSERT INTO transactions (bill_id, item_id, quantity)
                    VALUES (:bill_id, :item_id, :quantity)
                """),
                {"bill_id": bill_id, "item_id": item.item_id, "quantity": item.quantity}
            )

            # Decrease stock
            conn.execute(
                text("""
                    UPDATE inventory
                    SET current_stock = current_stock - :quantity
                    WHERE item_id = :item_id
                """),
                {"quantity": item.quantity, "item_id": item.item_id}
            )

    return {"bill_id": bill_id, "message": "Bill recorded successfully"}

@app.get("/inventory")
def get_inventory():
    query = text("SELECT item_id, item_name, current_stock FROM inventory ORDER BY item_id")

    with engine.connect() as conn:
        result = conn.execute(query).fetchall()

    return [{"item_id": row.item_id, "item_name": row.item_name, "current_stock": row.current_stock} for row in result]

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