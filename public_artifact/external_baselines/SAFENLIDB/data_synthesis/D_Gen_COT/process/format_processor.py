import json
from pathlib import Path
from collections import OrderedDict

KEY_ORDER = [
    'id',
    'db_id',
    'safe_condition',
    'specific_value',
    'specific_column',
    'safe_label',
    'sql_list',
    'questions',
    'cot_content',
    'SQL_COT'
]

def process_json(input_path, output_path):
    """Process JSON file key order and validate data structure"""
    if not Path(input_path).exists():
        print(f'Error: Input file {input_path} does not exist')
        return False

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Validate required fields
    required_fields = set(KEY_ORDER)
    for idx, item in enumerate(data):
        missing = required_fields - set(item.keys())
        if missing:
            print(f'Error: Data item {idx} is missing fields {missing}')
            return False

    # Rebuild data format
    processed_data = []
    for item in data:
        ordered_item = OrderedDict()
        for key in KEY_ORDER:
            ordered_item[key] = item[key]
        processed_data.append(ordered_item)

    # Safe write
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    
    print(f'Successfully processed {len(processed_data)} data items')
    return True

if __name__ == '__main__':
    input_file = r'1.json'
    output_file = r'1.json'
    process_json(input_file, output_file)