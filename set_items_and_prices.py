from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# --- Choose which database to update: AIVEN or LOCAL ---
# Set USE_AIVEN = True to update your live cloud database,
# or False to update your local MySQL for local testing.
USE_AIVEN = False

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

# (item_id, item_name, price_in_rupees)
items = [
    (1,  "Amul Toned Milk 500ml",           30),
    (2,  "Amul Butter 100g",                55),
    (3,  "Britannia Bread 400g",            45),
    (4,  "Farm Fresh Eggs (6 pcs)",         42),
    (5,  "Amul Cheese Slices (10 pcs)",     120),
    (6,  "Nestle Curd 400g",                40),
    (7,  "Real Orange Juice 1L",            110),
    (8,  "Tropicana Apple Juice 1L",        120),
    (9,  "Bananas (1 dozen)",               60),
    (10, "Red Apples (1kg)",                180),
    (11, "Tomatoes (1kg)",                  40),
    (12, "Onions (1kg)",                    35),
    (13, "Potatoes (1kg)",                  30),
    (14, "Carrots (1kg)",                   50),
    (15, "Fresh Spinach (500g)",            25),
    (16, "Fortune Basmati Rice 5kg",        480),
    (17, "Aashirvaad Atta 5kg",             260),
    (18, "Tata Sugar 1kg",                  45),
    (19, "Tata Salt 1kg",                   25),
    (20, "Fortune Sunflower Oil 1L",        150),
    (21, "Tata Tea Gold 250g",              140),
    (22, "Nescafe Classic Coffee 100g",     260),
    (23, "Parle-G Biscuits (Family Pack)",  40),
    (24, "Britannia Good Day Biscuits",     35),
    (25, "Cadbury Dairy Milk 55g",          50),
    (26, "Lay's Potato Chips 52g",          20),
    (27, "Maggi Noodles (Pack of 4)",       56),
    (28, "Sunfeast Pasta 500g",             65),
    (29, "Kissan Tomato Ketchup 500g",      105),
    (30, "Del Monte Mayonnaise 250g",       130),
    (31, "Pintola Peanut Butter 350g",      250),
    (32, "Bisleri Water 1L",                20),
    (33, "Coca-Cola 1.5L",                  90),
    (34, "Red Bull Energy Drink 250ml",     125),
    (35, "Tetley Green Tea Bags (25 pcs)",  150),
    (36, "Dabur Honey 500g",                220),
    (37, "Vim Dishwash Liquid 500ml",       95),
    (38, "Surf Excel Detergent 1kg",        145),
    (39, "Origami Toilet Paper (6 Rolls)",  180),
    (40, "Lifebuoy Hand Soap 125g",         40),
    (41, "Colgate Strong Teeth 200g",       55),
    (42, "Head & Shoulders Shampoo 180ml",  210),
    (43, "Nivea Body Lotion 200ml",         190),
    (44, "Origami Facial Tissues (Box)",    60),
    (45, "OK Trash Bags (Roll of 15)",      85),
    (46, "Duracell AA Batteries (4-pack)",  120),
    (47, "Philips LED Bulb 9W",             90),
    (48, "Local Matchbox",                  2),
    (49, "Classmate Notebook 172pg",        40),
    (50, "Cello Ball Pen (Pack of 5)",      45),
]

with engine.connect() as conn:
    for item_id, name, price in items:
        conn.execute(
            text("""
                INSERT INTO inventory (item_id, item_name, price, current_stock)
                VALUES (:item_id, :name, :price, 100)
                ON DUPLICATE KEY UPDATE item_name = :name, price = :price
            """),
            {"item_id": item_id, "name": name, "price": price}
        )
    conn.commit()

print(f"Updated {len(items)} items with real names and prices.")