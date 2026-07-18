import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

local_engine = create_engine(
    f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)

cloud_engine = create_engine(
    f"mysql+mysqlconnector://{os.getenv('AIVEN_DB_USER')}:{os.getenv('AIVEN_DB_PASSWORD')}@{os.getenv('AIVEN_DB_HOST')}:{os.getenv('AIVEN_DB_PORT')}/{os.getenv('AIVEN_DB_NAME')}?use_pure=true"
)

# --- Create sales table with a proper primary key first ---
with cloud_engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS sales"))
    conn.execute(text("""
        CREATE TABLE sales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE NOT NULL,
            store INT NOT NULL,
            item INT NOT NULL,
            sales INT NOT NULL
        )
    """))
    conn.commit()

# --- Load sales data into the pre-created table ---
print("Migrating sales...")
df = pd.read_sql_table("sales", local_engine)

chunk_size = 5000
total_rows = len(df)

for start in range(0, total_rows, chunk_size):
    end = start + chunk_size
    chunk = df.iloc[start:end]
    chunk.to_sql("sales", cloud_engine, if_exists="append", index=False)
    print(f"  -> uploaded rows {start} to {min(end, total_rows)} of {total_rows}")

print("sales migration complete.")

# --- Create inventory table with proper primary key ---
with cloud_engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS transactions"))  # drop first, since it references inventory
    conn.execute(text("DROP TABLE IF EXISTS inventory"))
    conn.execute(text("""
        CREATE TABLE inventory (
            item_id INT PRIMARY KEY,
            item_name VARCHAR(100) NOT NULL,
            current_stock INT NOT NULL DEFAULT 0
        )
    """))
    conn.execute(text("""
        CREATE TABLE transactions (
            transaction_id INT AUTO_INCREMENT PRIMARY KEY,
            bill_id INT NOT NULL,
            item_id INT NOT NULL,
            quantity INT NOT NULL,
            sale_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES inventory(item_id)
        )
    """))
    conn.commit()

# --- Load data into inventory and transactions ---
for table in ["inventory", "transactions"]:
    print(f"Migrating {table}...")
    df = pd.read_sql_table(table, local_engine)
    df.to_sql(table, cloud_engine, if_exists="append", index=False)
    print(f"  -> {len(df)} rows copied")

print("Migration complete.")