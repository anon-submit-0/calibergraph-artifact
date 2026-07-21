import json
import re

# Define a function to clean extra spaces and newlines in the string,
# and filter out SQL statements containing WITH keyword
def clean_text(text):
    if isinstance(text, str):
        # Check if it contains the WITH keyword (case-insensitive)
        if re.search(r'\bWITH\b', text, re.IGNORECASE):
            return ""
        # Replace multiple spaces with a single space, replace newlines with space
        text = re.sub(r'\s+', ' ', text)
        # Trim leading and trailing spaces
        text = text.strip()
    return text

# Load the selected_data.json file (relative path)
with open("selected_data.json", 'r', encoding="utf-8") as f:
    output = json.load(f)

# Load the db_ids.json file (relative path)
with open("db_ids.json", 'r', encoding="utf-8") as f:
    db_id = json.load(f)

added_result = []
for i in range(len(output)):
    output_id = output[i]
    middle_one = {}

    # Ensure the 'id' field exists
    if "id" not in output_id and i < len(db_id):
        for j in range(len(db_id)):
            if db_id[j] == output_id.get("db_id"):
                middle_one["id"] = j
                break
    else:
        middle_one["id"] = output_id.get("id")

    # Add 'db_id' field
    middle_one["db_id"] = output_id.get("db_id")

    # Process 'extracted_sql' field: clean extra spaces and newlines,
    # and filter out SQL statements containing WITH keyword
    if "extracted_sql" in output_id:
        output_text = output_id["extracted_sql"]
        # Clean the SQL text and filter out WITH statements
        cleaned_sql = clean_text(output_text)
        # Skip the record if cleaned SQL is empty after filtering
        if cleaned_sql == "":
            continue
        middle_one["extracted_sql"] = cleaned_sql

    # Add other fields
    for key, value in output_id.items():
        if key not in ["id", "db_id", "extracted_sql"]:
            middle_one[key] = value

    added_result.append(middle_one)

# Sort by 'id'
added_result = sorted(added_result, key=lambda x: x.get("id", float('inf')))

# Output the result to selected_data.json (relative path)
with open("selected_data.json", 'w', encoding="utf-8") as f:
    f.write(json.dumps(added_result, indent=2, ensure_ascii=False))
