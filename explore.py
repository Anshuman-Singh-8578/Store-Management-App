import pandas as pd

# Load the sales data, telling pandas how to read the tricky column properly
sales = pd.read_csv("data/train.csv", dtype={"StateHoliday": str}, low_memory=False)

# Filter to just Store #1 — like "SELECT * FROM train WHERE Store = 1" in SQL
store1 = sales[sales["Store"] == 1]

# Sort by date so it's in chronological order
store1 = store1.sort_values("Date")

print(store1.head())
print(store1.shape)   # (rows, columns) — like COUNT(*) but also tells you column count

import matplotlib.pyplot as plt

# Convert the Date column from text into an actual date type
# so matplotlib knows how to space it out on a timeline correctly
'''store1["Date"] = pd.to_datetime(store1["Date"])

plt.figure(figsize=(14, 5))
plt.plot(store1["Date"], store1["Sales"])
plt.title("Store 1 - Daily Sales Over Time")
plt.xlabel("Date")
plt.ylabel("Sales")
plt.show()'''

# Look at just January 2013 to see the pattern up close
'''zoomed = store1[(store1["Date"] >= "2013-01-01") & (store1["Date"] <= "2013-02-28")]

plt.figure(figsize=(14, 5))
plt.plot(zoomed["Date"], zoomed["Sales"], marker="o")
plt.title("Store 1 - January-February 2013 (Zoomed In)")
plt.xlabel("Date")
plt.ylabel("Sales")
plt.xticks(rotation=45)
plt.show()'''

# Average sales for each day of the week, across the whole dataset for Store 1
avg_by_day = store1.groupby("DayOfWeek")["Sales"].mean()
print(avg_by_day)

# Keep only days the store was actually open
store1_open = store1[store1["Open"] == 1].copy()

print(store1_open.shape)
print(store1_open["Sales"].describe())