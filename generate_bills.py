from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import random
from datetime import datetime, timedelta

load_dotenv()

# --- Choose which database to update ---
USE_AIVEN = True

if USE_AIVEN:
    DB_USER = os.getenv("AIVEN_DB_USER")
    DB_PASSWORD = os.getenv("AIVEN_DB_PASSWORD")
    DB_HOST = os.getenv("AIVEN_DB_HOST")
    DB_PORT = os.getenv("AIVEN_DB_PORT")
    DB_NAME = os.getenv("AIVEN_DB_NAME")
    conn_str = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?use_pure=true"
else:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")
    conn_str = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_engine(conn_str)

random.seed(7)

with engine.connect() as conn:
    # Get all items so we can pick realistic random ones
    items = conn.execute(text("SELECT item_id FROM inventory")).fetchall()
    item_ids = [row.item_id for row in items]

    # Find the current highest bill_id so we don't collide with real bills
    result = conn.execute(text("SELECT COALESCE(MAX(bill_id), 0) AS max_id FROM transactions"))
    next_bill_id = result.scalar() + 1

    # A few items get "boosted" popularity so the reorder-suggestion feature has something to catch
    popular_items = random.sample(item_ids, 6)

    now = datetime.now()
    rows_inserted = 0

    for i in range(100):
        bill_id = next_bill_id + i

        # Random timestamp within the last 30 days
        days_ago = random.randint(0, 29)
        random_time = now - timedelta(days=days_ago, hours=random.randint(0, 12), minutes=random.randint(0, 59))

        # Each bill has 1-4 line items
        num_lines = random.randint(1, 4)

        # Bias toward popular items ~50% of the time, otherwise fully random
        line_items = []
        for _ in range(num_lines):
            if random.random() < 0.5:
                item_id = random.choice(popular_items)
            else:
                item_id = random.choice(item_ids)
            if item_id not in [li[0] for li in line_items]:
                line_items.append((item_id, random.randint(1, 5)))

        for item_id, quantity in line_items:
            conn.execute(
                text("""
                    INSERT INTO transactions (bill_id, item_id, quantity, sale_date)
                    VALUES (:bill_id, :item_id, :quantity, :sale_date)
                """),
                {"bill_id": bill_id, "item_id": item_id, "quantity": quantity, "sale_date": random_time}
            )
            rows_inserted += 1

    conn.commit()

print(f"Inserted {rows_inserted} transaction line items across 100 bills.")
print(f"Popular items (should show up as high-velocity): {popular_items}")