import json
from collections import defaultdict

# Set input and output file paths
main_json_path = 'data_synthesis/C_NL_question_syn/process/grou_output.json'  # Main data file path
ref_json_path = 'data_synthesis/original_data/db_ids.json'  # Reference db_id file path
output_path = 'data_synthesis/C_NL_question_syn/output.json'  # Output file path

# Read main data
with open(main_json_path, 'r', encoding='utf-8') as f:
    main_data = json.load(f)

# Read reference data (assumed to be an id->db_id mapping dictionary or list)
with open(ref_json_path, 'r', encoding='utf-8') as f:
    ref_data = json.load(f)

print(f'Original data length: {len(main_data)}')
count = 0
result = []
for item in main_data:
    item_id = item.get('item_id')
    db_id = item.get('db_id')
    correct_dbid = ref_data.get(item_id)  # Ensure safe access using get()
    if correct_dbid is not None and db_id == correct_dbid:
        result.append(item)
    else:
        count += 1
print(f'Number of items with incorrect db_id removed: {count}')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f'Processing complete. Items classified by item_id and those with incorrect db_id removed. Results saved to {output_path}')
