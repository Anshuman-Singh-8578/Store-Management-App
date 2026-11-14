from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import hashlib
import random
from datetime import datetime, timedelta

load_dotenv()

# --- Connect to Supabase ---
DB_USER = os.getenv("supa_DB_USER")
DB_PASSWORD = os.getenv("supa_DB_PASSWORD")
DB_HOST = os.getenv("supa_DB_HOST")
DB_PORT = os.getenv("supa_DB_PORT", "5432")
DB_NAME = os.getenv("supa_DB_NAME")

engine = create_engine(
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- Demo account credentials ---
USERNAME = "admin"
EMAIL = "admin@shelfsense.demo"
PASSWORD = "test123"

# --- 50 items: name, price, stock ---
items = [
    ("Amul Toned Milk 500ml",           30,  120),
    ("Amul Butter 100g",                55,   80),
    ("Britannia Bread 400g",            45,   90),
    ("Farm Fresh Eggs (6 pcs)",         42,   75),
    ("Amul Cheese Slices (10 pcs)",    120,   60),
    ("Nestle Curd 400g",                40,   85),
    ("Real Orange Juice 1L",           110,   50),
    ("Tropicana Apple Juice 1L",       120,   50),
    ("Bananas (1 dozen)",               60,  100),
    ("Red Apples (1kg)",               180,   70),
    ("Tomatoes (1kg)",                  40,  110),
    ("Onions (1kg)",                    35,  130),
    ("Potatoes (1kg)",                  30,  140),
    ("Carrots (1kg)",                   50,   65),
    ("Fresh Spinach (500g)",            25,   55),
    ("Fortune Basmati Rice 5kg",       480,   40),
    ("Aashirvaad Atta 5kg",            260,   45),
    ("Tata Sugar 1kg",                  45,   90),
    ("Tata Salt 1kg",                   25,  100),
    ("Fortune Sunflower Oil 1L",       150,   60),
    ("Tata Tea Gold 250g",             140,   55),
    ("Nescafe Classic Coffee 100g",    260,   35),
    ("Parle-G Biscuits (Family Pack)",  40,  120),
    ("Britannia Good Day Biscuits",     35,  110),
    ("Cadbury Dairy Milk 55g",          50,  150),
    ("Lay's Potato Chips 52g",          20,  160),
    ("Maggi Noodles (Pack of 4)",       56,   95),
    ("Sunfeast Pasta 500g",             65,   50),
    ("Kissan Tomato Ketchup 500g",     105,   45),
    ("Del Monte Mayonnaise 250g",      130,   40),
    ("Pintola Peanut Butter 350g",     250,   30),
    ("Bisleri Water 1L",                20,  200),
    ("Coca-Cola 1.5L",                  90,   80),
    ("Red Bull Energy Drink 250ml",    125,   60),
    ("Tetley Green Tea Bags (25 pcs)", 150,   40),
    ("Dabur Honey 500g",               220,   35),
    ("Vim Dishwash Liquid 500ml",       95,   55),
    ("Surf Excel Detergent 1kg",       145,   45),
    ("Origami Toilet Paper (6 Rolls)", 180,   50),
    ("Lifebuoy Hand Soap 125g",         40,   90),
    ("Colgate Strong Teeth 200g",       55,   75),
    ("Head & Shoulders Shampoo 180ml", 210,   40),
    ("Nivea Body Lotion 200ml",        190,   35),
    ("Origami Facial Tissues (Box)",    60,   65),
    ("OK Trash Bags (Roll of 15)",      85,   50),
    ("Duracell AA Batteries (4-pack)", 120,   40),
    ("Philips LED Bulb 9W",             90,   45),
    ("Local Matchbox",                   2,  300),
    ("Classmate Notebook 172pg",        40,   60),
    ("Cello Ball Pen (Pack of 5)",      45,   70),
]

random.seed(42)

with engine.begin() as conn:
    # --- 1. Create or reuse demo user ---
    existing = conn.execute(
        text("SELECT user_id FROM users WHERE username = :u"),
        {"u": USERNAME}
    ).fetchone()

    if existing:
        user_id = existing.user_id
        print(f"User '{USERNAME}' already exists (user_id={user_id}), reusing.")
    else:
        result = conn.execute(
            text("INSERT INTO users (username, email, password_hash) VALUES (:u, :e, :p) RETURNING user_id"),
            {"u": USERNAME, "e": EMAIL, "p": hash_password(PASSWORD)}
        )
        user_id = result.fetchone().user_id
        print(f"Created user '{USERNAME}' (user_id={user_id}).")

    # --- 2. Clear existing inventory and transactions for this user ---
    # Get existing item ids for this user
    existing_items = conn.execute(
        text("SELECT item_id FROM inventory WHERE owner_user_id = :uid"),
        {"uid": user_id}
    ).fetchall()
    existing_item_ids = [r.item_id for r in existing_items]

    if existing_item_ids:
        conn.execute(
            text("DELETE FROM transactions WHERE item_id = ANY(:ids)"),
            {"ids": existing_item_ids}
        )
        conn.execute(
            text("DELETE FROM inventory WHERE owner_user_id = :uid"),
            {"uid": user_id}
        )
        print(f"Cleared {len(existing_item_ids)} existing items and their transactions.")

    # --- 3. Insert inventory items ---
    item_ids = []
    for name, price, stock in items:
        result = conn.execute(
            text("INSERT INTO inventory (item_name, price, current_stock, owner_user_id) VALUES (:name, :price, :stock, :uid) RETURNING item_id"),
            {"name": name, "price": price, "stock": stock, "uid": user_id}
        )
        item_ids.append(result.fetchone().item_id)

    print(f"Inserted {len(item_ids)} inventory items.")

    # --- 4. Generate 1000 realistic bills ---
    # Pick 10 "popular" items that appear more frequently
    popular_ids = random.sample(item_ids, 10)

    now = datetime.now()
    rows_inserted = 0
    bill_count = 0

    # Get current max bill_id to avoid collisions
    max_bill = conn.execute(text("SELECT COALESCE(MAX(bill_id), 0) AS m FROM transactions")).scalar()
    next_bill_id = max_bill + 1

    for i in range(1000):
        bill_id = next_bill_id + i

        # Random timestamp within the last 60 days, weighted toward recent
        days_ago = int(random.triangular(0, 60, 5))  # skewed toward recent
        sale_time = now - timedelta(
            days=days_ago,
            hours=random.randint(8, 21),   # store hours 8am-9pm
            minutes=random.randint(0, 59)
        )

        # Each bill has 1-5 line items, no duplicate items per bill
        num_lines = random.randint(1, 5)
        chosen_items = []

        for _ in range(num_lines):
            # 60% chance of picking a popular item
            if random.random() < 0.6:
                item_id = random.choice(popular_ids)
            else:
                item_id = random.choice(item_ids)
            if item_id not in [x[0] for x in chosen_items]:
                quantity = random.randint(1, 4)
                chosen_items.append((item_id, quantity))

        for item_id, quantity in chosen_items:
            conn.execute(
                text("INSERT INTO transactions (bill_id, item_id, quantity, sale_date) VALUES (:bid, :iid, :qty, :sd)"),
                {"bid": bill_id, "iid": item_id, "qty": quantity, "sd": sale_time}
            )
            rows_inserted += 1

        bill_count += 1

    print(f"Generated {bill_count} bills with {rows_inserted} total line items.")
    print(f"\nPopular items (high velocity for reorder alerts):")
    for iid in popular_ids:
        name = items[item_ids.index(iid)][0]
        print(f"  - {name}")

print(f"\nDemo setup complete!")
print(f"  Username : {USERNAME}")
print(f"  Password : {PASSWORD}")
print(f"  Items    : {len(items)}")
print(f"  Bills    : 1000")
