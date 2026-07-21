import json
import re

# Read the original JSON file
with open(
        'output_cells.json',
        'r', encoding='utf-8') as f:
    data = json.load(f)
with open(
        'db_ids.json',
        'r', encoding='utf-8') as f:
    db_list = json.load(f)
# Create a new data structure
result = []

# Counter to track the number of skipped entries
skipped_count = 0

for idx, item in enumerate(data):
    output_text = item['output']

    # Try multiple format matches
    # Handle cases with asterisks or other formats
    safe_condition_patterns = [
        r'(?:safe_condition:|Safe condition:)\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*Safe condition:\*\*\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*Safety condition:\*\*\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*Safety Condition:\*\*\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*Safe Condition:\*\*\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*safe_condition:\*\*\s*(.*?\.)(?=\s|\n|$)',
        r'\*\*Safety Condition\*\*\s*(.*?\.)(?=\s|\n|$)',
    ]

    safe_condition_match = None
    for pattern in safe_condition_patterns:
        match = re.search(pattern, output_text, re.IGNORECASE)
        if match:
            safe_condition_match = match
            break

    specific_column_patterns = [
        r'(?:specific_column:|specific_column:\s*)\s*(\[.*?\])(?:\n|$)',
        r'\*\*specific_column:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific column:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific Column:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific Column\*\*\s*(\[.*?\])(?:\n|$)'


    ]

    specific_column_match = None
    for pattern in specific_column_patterns:
        match = re.search(pattern, output_text, re.IGNORECASE)
        if match:
            specific_column_match = match
            break

    specific_value_patterns = [
        r'(?:specific_value:|specific_values?:)\s*(\[.*?\])(?:\n|$)',
        r'\*\*specific_value:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific value:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*specific_values:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific Value:\*\*\s*(\[.*?\])(?:\n|$)',
        r'\*\*Specific Value\*\*\s*(\[.*?\])(?:\n|$)'
    ]

    specific_value_match = None
    for pattern in specific_value_patterns:
        match = re.search(pattern, output_text, re.IGNORECASE)
        if match:
            specific_value_match = match
            break

    # Extract matched content or set to None
    safe_condition = None
    if safe_condition_match:
        safe_condition = safe_condition_match.group(1).strip()
        # Remove possible asterisks
        safe_condition = safe_condition.replace('*', '').strip()

    specific_column = None
    if specific_column_match:
        specific_column = specific_column_match.group(1).strip()
        # Remove possible asterisks
        specific_column = specific_column.replace('*', '').strip()

    specific_value = None
    if specific_value_match:
        specific_value = specific_value_match.group(1).strip()
        # Remove possible asterisks
        specific_value = specific_value.replace('*', '').strip()

    # Set to "None" if not found
    safe_condition = safe_condition if safe_condition else "None"
    specific_column = specific_column if specific_column else "None"
    specific_value = specific_value if specific_value else "None"

    # Skip this entry if both safe_condition and specific_column are not found
    if safe_condition == "None":
        skipped_count += 1
        continue
    if specific_column == "None":
        skipped_count += 1
        continue
    # Process each item in specific_column
    should_skip = False
    if specific_column != "None" and specific_column.startswith("[") and specific_column.endswith("]"): 
        # Remove surrounding brackets and split by comma
        columns_str = specific_column[1:-1].strip()
        if columns_str:  # 确保不是空列表
            columns = [col.strip() for col in columns_str.split(',')]
            
            # Process each column, remove parentheses and content inside
            processed_columns = []
            for col in columns:
                # Use regex to remove parentheses and content inside
                col_name = re.sub(r'\([^)]*\)', '', col).strip()
                processed_columns.append(col_name)
            
            # Check if each column exists in the input
            input_text = item.get('input', '')
            for col_name in processed_columns:
                if col_name and col_name not in input_text:
                    should_skip = True
                    skipped_count += 1
                    break
    
    if should_skip:
        continue

    # Create a new entry
    new_item = {
        "id":idx,
        "db_id": db_list[idx],
        "safe_condition": safe_condition,
        "specific_column": specific_column,
        "specific_value": specific_value
    }

    result.append(new_item)

# Save as a new JSON file
with open(
        'omni_cells.json',
        'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Extraction completed, saved to omni_cells.json file, skipped {skipped_count} entries")