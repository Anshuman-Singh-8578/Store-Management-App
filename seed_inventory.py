from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

# A believable small-shop product list, one per item_id (1-50)
item_names = [
    "Whole Milk 1L", "Brown Bread", "White Bread", "Free-Range Eggs (12)", "Butter 250g",
    "Cheddar Cheese", "Greek Yogurt", "Orange Juice 1L", "Apple Juice 1L", "Bananas (1kg)",
    "Red Apples (1kg)", "Tomatoes (1kg)", "Onions (1kg)", "Potatoes (2kg)", "Carrots (1kg)",
    "Basmati Rice 5kg", "Whole Wheat Flour 5kg", "Sugar 1kg", "Salt 1kg", "Cooking Oil 1L",
    "Black Tea 250g", "Instant Coffee 100g", "Biscuits (Family Pack)", "Chocolate Bar", "Potato Chips",
    "Instant Noodles (Pack of 5)", "Pasta 500g", "Tomato Ketchup", "Mayonnaise", "Peanut Butter",
    "Bottled Water 1L", "Soft Drink 1.5L", "Energy Drink", "Green Tea Bags", "Honey 500g",
    "Dish Soap", "Laundry Detergent", "Toilet Paper (6 Rolls)", "Hand Soap", "Toothpaste",
    "Shampoo 200ml", "Body Lotion", "Tissues (Box)", "Trash Bags (Roll)", "Batteries (AA, 4-pack)",
    "Light Bulb", "Matches (Box)", "Candles (Pack of 4)", "Notebook", "Pen (Pack of 5)"
]

with engine.connect() as conn:
    for item_id, name in enumerate(item_names, start=1):
        conn.execute(
            text("""
                INSERT INTO inventory (item_id, item_name, current_stock)
                VALUES (:item_id, :item_name, :stock)
                ON DUPLICATE KEY UPDATE item_name = :item_name
            """),
            {"item_id": item_id, "item_name": name, "stock": 100}
        )
    conn.commit()

print("Inventory seeded with real item names.")