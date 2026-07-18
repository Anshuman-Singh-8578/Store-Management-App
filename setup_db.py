import pandas as pd
from sqlalchemy import create_engine

# --- Connection details ---
# Replace 'your_password' with your actual MySQL root password
DB_USER = "root"
DB_PASSWORD = "***REMOVED***"
DB_HOST = "localhost"
DB_NAME = "demand_predictor"

# Create a connection to MySQL
engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

# --- Load CSV and push it into MySQL ---
items = pd.read_csv("data/item_train.csv")

items.to_sql("sales", engine, if_exists="replace", index=False)

print("Data loaded into MySQL table 'sales'")