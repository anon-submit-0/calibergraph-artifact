import json
from collections import defaultdict

# Read three JSON files
with open('map1.json', 'r', encoding='utf-8') as f:
    map_data = json.load(f)

with open('total_nl2sql_part_1.json', 'r', encoding='utf-8') as f:
    output_data = json.load(f)


# Grouping result dictionary: item_idx -> list of outputs (in order)
# Temporary structure: item_idx -> list of (output, db_id, item_id, sql_list)
temp_grouped = defaultdict(list)

# Group SQL data by item_idx
sql_grouped = defaultdict(list)
for sql_item in map_data:
    item_idx = sql_item['item_idx']
    sql_grouped[item_idx].append(sql_item['sql'])

# Iterate map_data and get corresponding items from output_data by index
for i, map_item in enumerate(map_data):
    item_idx = map_item['item_idx']
    db_id = map_item['db_id']
    item_id = map_item['item_id']
    output_text = output_data[i].get('output', None)
    if output_text is not None:
        temp_grouped[item_idx].append({
            "output": output_text,
            "db_id": db_id,
            "item_id": item_id,
            "sql_list": sql_grouped.get(item_idx, [])
        })

# Organize output structure
final_output = []
for item_idx, items in sorted(temp_grouped.items()):
    outputs = [x['output'] for x in items]
    sql_lists = [x['sql_list'] for x in items]
    db_id = items[0]['db_id']  # db_id should be the same in the same group
    item_id = items[0]['item_id']
    final_output.append({
        "item_idx": item_idx,
        "item_id": item_id,
        "db_id": db_id,
        "outputs": outputs,
        "sql_list": sql_lists[0] if sql_lists else []
    })

# Save to JSON file
with open('grouped_output.json', 'w', encoding='utf-8') as f:
    json.dump(final_output, f, ensure_ascii=False, indent=2)

print("Grouped output containing db_id and item_id saved to grouped_output.json")