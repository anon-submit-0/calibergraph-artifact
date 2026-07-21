import json
from collections import defaultdict

# Read three JSON files
with open('map1.json', 'r', encoding='utf-8') as f:
    map_data = json.load(f)

with open('total_nl2sql_part_1.json', 'r', encoding='utf-8') as f:
    output_data = json.load(f)

with open('sql_grouped.json', 'r', encoding='utf-8') as f:
    sql_cot_content = json.load(f)

# Iterate over map_data and get corresponding items from output_data by index
for i, map_item in enumerate(map_data):
    item_idx = map_item['item_idx']
    db_id = map_item['db_id']
    item_id = map_item['item_id']
    output_text = output_data[i].get('output', None)
    if output_text is not None:
        sql_cot_content[item_idx].append({"secure_cot": output_data[i]['output']})

with open('grou_output.json', 'w', encoding='utf-8') as f:
    json.dump(sql_cot_content, f, ensure_ascii=False, indent=2)
