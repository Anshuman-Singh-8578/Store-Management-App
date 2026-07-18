import pandas as pd

# --- Load and clean ---
sales = pd.read_csv("data/train.csv", dtype={"StateHoliday": str}, low_memory=False)

# Convert Date to a real date type
sales["Date"] = pd.to_datetime(sales["Date"])

# Focus on Store 1 for now
store1 = sales[sales["Store"] == 1].copy()

# Keep only days the store was open (closed days aren't useful for forecasting demand)
store1_open = store1[store1["Open"] == 1].copy()

# Sort chronologically — critical before creating lag features
store1_open = store1_open.sort_values("Date")

# --- Feature engineering ---
# Sales exactly 7 open-days ago (captures weekly pattern)
store1_open["sales_lag_7"] = store1_open["Sales"].shift(7)

# Sales 1 open-day ago (captures short-term momentum)
store1_open["sales_lag_1"] = store1_open["Sales"].shift(1)

# --- More features ---
# Day of week is already numeric (1-6, since we dropped Sundays) — good as-is for now

# Drop rows where we don't have a full history yet (the first 7 open days)
model_data = store1_open.dropna(subset=["sales_lag_1", "sales_lag_7"]).copy()

print(model_data.shape)
print(model_data[["Date", "DayOfWeek", "Promo", "sales_lag_1", "sales_lag_7", "Sales"]].head())
# --- Check our work ---
print(store1_open[["Date", "Sales", "sales_lag_1", "sales_lag_7"]].head(10))
print(store1_open.shape)

# --- Train/test split (chronological, not random!) ---
# Use the last 30 open-days as our "test" set (unseen future), rest for training
train = model_data.iloc[:-30]
test = model_data.iloc[-30:]

print("Train size:", train.shape)
print("Test size:", test.shape)

# --- Prepare inputs (X) and target (y) ---
features = ["DayOfWeek", "Promo", "sales_lag_1", "sales_lag_7"]

X_train = train[features]
y_train = train["Sales"]

X_test = test[features]
y_test = test["Sales"]

# --- Train a simple model ---
from sklearn.linear_model import LinearRegression

model = LinearRegression()
model.fit(X_train, y_train)

# --- Predict and check accuracy ---
predictions = model.predict(X_test)

from sklearn.metrics import mean_absolute_error

mae = mean_absolute_error(y_test, predictions)
print("Mean Absolute Error:", mae)

# --- Try a Random Forest model ---
from sklearn.ensemble import RandomForestRegressor

rf_model = RandomForestRegressor(
    n_estimators=100,
    max_depth=5,          # limit how deep each tree can grow
    min_samples_leaf=5,   # each final decision must be based on at least 5 examples
    random_state=42
)
rf_model.fit(X_train, y_train)

rf_predictions = rf_model.predict(X_test)

rf_mae = mean_absolute_error(y_test, rf_predictions)
print("Random Forest MAE:", rf_mae)

# Check for overfitting: compare performance on training data vs test data
train_predictions = rf_model.predict(X_train)
train_mae = mean_absolute_error(y_train, train_predictions)
print("Random Forest Train MAE:", train_mae)
print("Random Forest Test MAE:", rf_mae)

import joblib

joblib.dump(rf_model, "model.pkl")
print("Model saved to model.pkl")