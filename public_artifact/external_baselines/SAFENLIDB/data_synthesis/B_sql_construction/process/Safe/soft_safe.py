import json
import random
import os
import re
from collections import defaultdict

# === Path Definitions ===
selected_data_path = "selected_data.json"
cell_path = "omni_cells_filtered.json"
column_path = "omni_whole_column_filtered.json"
output_path = "process/p111.json"

# === Load JSON ===
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

selected_data = load_json(selected_data_path)
column_conditions = load_json(column_path)
cell_conditions = load_json(cell_path)

# === Group by db_id ===
def group_by_db(items):
    result = defaultdict(list)
    for item in items:
        result[item['db_id']].append(item)
    return result

column_dict = group_by_db(column_conditions)
cell_dict = group_by_db(cell_conditions)
data_by_db = group_by_db(selected_data)

# === Extract Column Names (no table names, no types) ===
def extract_column_names(specific_column_str):
    if not specific_column_str or specific_column_str == "None":
        return []
    raw_cols = specific_column_str.strip("[]").split(",")
    col_names = []
    for col in raw_cols:
        parts = col.strip().split()
        if parts:
            table_col = parts[0]  # table.column
            if '.' in table_col:
                col_name = table_col.split('.')[1].strip()
            else:
                col_name = table_col.strip()
            col_names.append(col_name.lower())
    return col_names

# === Check if SQL is safe ===
def is_sql_safe(sql, forbidden_columns):
    sql_lower = sql.lower()
    for col in forbidden_columns:
        pattern = r'\b' + re.escape(col) + r'\b'
        if re.search(pattern, sql_lower):
            return False
    return True

# === Build Output Entry ===
def build_safe_entry(db_id, condition, sql_pool, entry_id):
    forbidden_cols = extract_column_names(condition.get('specific_column', ''))
    if not forbidden_cols:
        return None

    # Filter safe SQL
    safe_sqls = [item['extracted_sql'] for item in sql_pool if is_sql_safe(item['extracted_sql'], forbidden_cols)]
    if not safe_sqls:
        return None

    selected_sqls = random.sample(safe_sqls, min(random.choice([1, 2, 3]), len(safe_sqls)))
    return {
        "id": entry_id,
        "db_id": db_id,
        "label": "Aggregation",
        "safe_condition": condition.get("safe_condition", ""),
        "specific_column": condition.get("specific_column", ""),
        "specific_value": condition.get("specific_value", "None"),
        "extracted_sql": selected_sqls,
        "cot_content": "",
        "safe_label": "safe"
    }

# === Main Process ===
final_output = []
next_id = 0

all_db_ids = set(data_by_db.keys())
print(f"Total number of databases: {len(all_db_ids)}")

for db_id in all_db_ids:
    sql_pool = data_by_db[db_id]

    # Try a column condition
    column_conditions = column_dict.get(db_id, [])
    if column_conditions:
        condition = random.choice(column_conditions)
        entry = build_safe_entry(db_id, condition, sql_pool, next_id)
        if entry:
            final_output.append(entry)
            next_id += 1

    # Try a cell condition
    cell_conditions = cell_dict.get(db_id, [])
    if cell_conditions:
        condition = random.choice(cell_conditions)
        entry = build_safe_entry(db_id, condition, sql_pool, next_id)
        if entry:
            final_output.append(entry)
            next_id += 1

# === Save Results ===
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(final_output, f, indent=2, ensure_ascii=False)

print(f"A total of {len(final_output)} safe data entries were generated and saved to: {output_path}")
