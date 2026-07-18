import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = "root"
DB_PASSWORD = "***REMOVED***"
DB_HOST = "localhost"
DB_NAME = "demand_predictor"

engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

def top_selling_items(store_id, as_of_date, lookback_days=14, top_n=5):
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
        result = pd.read_sql_query(query, conn, params=params)

    return result

# --- Test it ---
print(top_selling_items(store_id=1, as_of_date="2017-12-31", lookback_days=14, top_n=5))