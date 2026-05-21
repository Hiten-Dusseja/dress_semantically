import json
import re

input_file = "scraper_output/fashion_data.json"

# Load JSON data
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Clean and convert price
for item in data:
    price = item.get("price", "")

    # Extract first numeric price after ₹
    match = re.search(r"₹\s?([\d,]+)", price)

    if match:
        clean_price = match.group(1).replace(",", "")
        item["price"] = int(clean_price)

# Save back to same file
with open(input_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Prices cleaned and converted to integers.")