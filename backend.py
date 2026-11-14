from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import hashlib
from datetime import date
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

load_dotenv()

DB_USER = os.getenv("SUPA_DB_USER")
DB_PASSWORD = os.getenv("SUPA_DB_PASSWORD")
DB_HOST = os.getenv("SUPA_DB_HOST")
DB_PORT = os.getenv("SUPA_DB_PORT")
DB_NAME = os.getenv("SUPA_DB_NAME")

engine = create_engine(
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-this-in-production")
serializer = URLSafeTimedSerializer(SECRET_KEY)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_token(token: str):
    try:
        return serializer.loads(token, max_age=8 * 60 * 60)
    except (BadSignature, SignatureExpired):
        return None

def require_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    return user

def get_current_user_id(username: str, conn) -> int:
    row = conn.execute(text("SELECT user_id FROM users WHERE username = :u"), {"u": username}).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="User not found")
    return row.user_id

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

@app.post("/signup")
def signup(request: SignupRequest):
    if len(request.password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT user_id FROM users WHERE username = :u OR email = :e"),
            {"u": request.username, "e": request.email}
        ).fetchone()
        if existing:
            return {"success": False, "error": "Username or email already taken"}

        conn.execute(
            text("INSERT INTO users (username, email, password_hash) VALUES (:u, :e, :p)"),
            {"u": request.username, "e": request.email, "p": hash_password(request.password)}
        )

    token = serializer.dumps({"username": request.username})
    return {"success": True, "token": token, "username": request.username}

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(request: LoginRequest):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM users WHERE username = :u"),
            {"u": request.username}
        ).fetchone()

    if row is None or hash_password(request.password) != row.password_hash:
        return {"success": False, "error": "Invalid username or password"}

    token = serializer.dumps({"username": request.username})
    return {"success": True, "token": token, "username": request.username}

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

BOGO_RULES = []

SEASONAL_DISCOUNTS = [
    {"name": "Chocolate Day", "keywords": ["chocolate", "dairy milk"], "percent": 15,
     "start": date(2026, 2, 9), "end": date(2026, 2, 9)}
]

@app.get("/inventory")
def get_inventory(user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("SELECT item_id, item_name, price, current_stock FROM inventory WHERE owner_user_id = :uid ORDER BY current_stock ASC"),
            {"uid": user_id}
        ).fetchall()
    return [{"item_id": r.item_id, "item_name": r.item_name, "price": r.price, "current_stock": r.current_stock} for r in result]

@app.get("/inventory/search")
def search_inventory(q: str, user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                SELECT item_id, item_name, price, current_stock FROM inventory
                WHERE owner_user_id = :uid AND item_name ILIKE :search_term
                ORDER BY item_name LIMIT 10
            """),
            {"uid": user_id, "search_term": f"%{q}%"}
        ).fetchall()
    return [{"item_id": r.item_id, "item_name": r.item_name, "price": r.price, "current_stock": r.current_stock} for r in result]

class ProductRequest(BaseModel):
    item_name: str
    price: int
    current_stock: int = 0

@app.post("/inventory/add")
def add_product(request: ProductRequest, user=Depends(require_auth)):
    with engine.begin() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("INSERT INTO inventory (item_name, price, current_stock, owner_user_id) VALUES (:name, :price, :stock, :uid) RETURNING item_id"),
            {"name": request.item_name, "price": request.price, "stock": request.current_stock, "uid": user_id}
        )
    return {"success": True, "item_id": result.fetchone().item_id}

@app.put("/inventory/{item_id}")
def update_product(item_id: int, request: ProductRequest, user=Depends(require_auth)):
    with engine.begin() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                UPDATE inventory SET item_name = :name, price = :price, current_stock = :stock
                WHERE item_id = :iid AND owner_user_id = :uid
            """),
            {"name": request.item_name, "price": request.price, "stock": request.current_stock, "iid": item_id, "uid": user_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found or not yours")
    return {"success": True}

@app.delete("/inventory/{item_id}")
def delete_product(item_id: int, user=Depends(require_auth)):
    with engine.begin() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("DELETE FROM inventory WHERE item_id = :iid AND owner_user_id = :uid"),
            {"iid": item_id, "uid": user_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found or not yours")
    return {"success": True}

class StockUpdateRequest(BaseModel):
    item_id: int
    quantity_added: int

@app.post("/stock-up")
def stock_up(request: StockUpdateRequest, user=Depends(require_auth)):
    with engine.begin() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("UPDATE inventory SET current_stock = current_stock + :quantity WHERE item_id = :item_id AND owner_user_id = :uid"),
            {"quantity": request.quantity_added, "item_id": request.item_id, "uid": user_id}
        )
        if result.rowcount == 0:
            return {"error": "Item not found or not yours"}
    return {"item_id": request.item_id, "message": "Stock updated"}

class BillItem(BaseModel):
    item_id: int
    quantity: int

class BillRequest(BaseModel):
    items: List[BillItem]

@app.post("/bill")
def create_bill(request: BillRequest, user=Depends(require_auth)):
    receipt_items = []
    today = date.today()

    with engine.begin() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(text("SELECT COALESCE(MAX(bill_id), 0) + 1 AS next_id FROM transactions"))
        bill_id = result.scalar()

        for item in request.items:
            row = conn.execute(
                text("SELECT item_name, price, current_stock FROM inventory WHERE item_id = :item_id AND owner_user_id = :uid"),
                {"item_id": item.item_id, "uid": user_id}
            ).fetchone()

            if row is None:
                raise Exception(f"Item {item.item_id} does not exist in your store")
            if row.current_stock < item.quantity:
                raise Exception(f"Not enough stock for item {item.item_id}")

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

        requested_qty = {item.item_id: item.quantity for item in request.items}
        for rule in BOGO_RULES:
            trigger_qty_bought = requested_qty.get(rule["trigger_item_id"], 0)
            free_units_earned = (trigger_qty_bought // rule["trigger_qty"]) * rule["free_qty"]

            if free_units_earned > 0:
                free_row = conn.execute(
                    text("SELECT item_name, price, current_stock FROM inventory WHERE item_id = :item_id AND owner_user_id = :uid"),
                    {"item_id": rule["free_item_id"], "uid": user_id}
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

@app.get("/reorder-suggestions")
def reorder_suggestions(days: int = 14, user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                SELECT i.item_id, i.item_name, i.current_stock,
                       COALESCE(SUM(t.quantity), 0) AS units_sold_recently
                FROM inventory i
                LEFT JOIN transactions t
                  ON i.item_id = t.item_id AND t.sale_date >= NOW() - INTERVAL '1 day' * :days
                WHERE i.owner_user_id = :uid
                GROUP BY i.item_id, i.item_name, i.current_stock
                ORDER BY units_sold_recently DESC
            """),
            {"days": days, "uid": user_id}
        ).fetchall()

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
def item_sales_history(item_id: int, days: int = 14, user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                SELECT DATE(t.sale_date) AS sale_day, SUM(t.quantity) AS units_sold
                FROM transactions t
                JOIN inventory i ON t.item_id = i.item_id
                WHERE t.item_id = :item_id AND i.owner_user_id = :uid
                  AND t.sale_date >= NOW() - INTERVAL '1 day' * :days
                GROUP BY DATE(t.sale_date)
                ORDER BY sale_day
            """),
            {"item_id": item_id, "uid": user_id, "days": days}
        ).fetchall()
    return [{"date": str(row.sale_day), "units_sold": row.units_sold} for row in result]

@app.get("/top-items")
def top_items(days: int = 14, top_n: int = 5, user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                SELECT i.item_id AS item, i.item_name, SUM(t.quantity) AS total_sales
                FROM transactions t
                JOIN inventory i ON t.item_id = i.item_id
                WHERE i.owner_user_id = :uid
                  AND t.sale_date >= NOW() - INTERVAL '1 day' * :days
                GROUP BY i.item_id, i.item_name
                ORDER BY total_sales DESC
                LIMIT :top_n
            """),
            {"uid": user_id, "days": days, "top_n": top_n}
        ).fetchall()
    return [{"item": r.item, "item_name": r.item_name, "total_sales": float(r.total_sales)} for r in result]

@app.get("/sales-history")
def sales_history(days: int = 30, user=Depends(require_auth)):
    with engine.connect() as conn:
        user_id = get_current_user_id(user["username"], conn)
        result = conn.execute(
            text("""
                SELECT DATE(t.sale_date) AS sale_day, SUM(t.quantity) AS total_units
                FROM transactions t
                JOIN inventory i ON t.item_id = i.item_id
                WHERE i.owner_user_id = :uid
                  AND t.sale_date >= NOW() - INTERVAL '1 day' * :days
                GROUP BY DATE(t.sale_date)
                ORDER BY sale_day
            """),
            {"uid": user_id, "days": days}
        ).fetchall()
    return [{"date": str(r.sale_day), "sales": r.total_units} for r in result]