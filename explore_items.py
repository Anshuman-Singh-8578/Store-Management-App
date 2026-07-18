import pandas as pd

items = pd.read_csv("data/item_train.csv")

print(items.head())
print(items.info())
print("Unique stores:", items["store"].nunique())
print("Unique items:", items["item"].nunique())
