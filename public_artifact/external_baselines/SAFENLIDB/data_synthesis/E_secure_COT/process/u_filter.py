import json
import os

# Define required keys to check
required_keys = [
    "id",
    "db_id",
    "safe_condition",
    "specific_column",
    "safe_label",
    "sql_list",
    "questions",
    "SQL_COT",
    "label",
    "secure_cot",
]

# Check if a value is empty
def is_empty(value):
    if value is None:
        return True
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return True
    return False


def filter_json(input_path: str, output_path: str) -> None:
    """
    Read JSON data (list) from input_path,
    filter out items missing required_keys or with empty values,
    and write the result to output_path.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("The top-level structure of the input file should be a JSON list")

    filtered = []
    removed_count = 0

    for idx, item in enumerate(data):
        # Check all required fields
        if not isinstance(item, dict):
            removed_count += 1
            continue

        valid = True
        for key in required_keys:
            if key not in item or is_empty(item.get(key)):
                valid = False
                break


        if len(item["SQL_COT"]) == 0:
            print(1)
            removed_count += 1
            continue
        elif item["SQL_COT"][-1] is None:
            print(2)
            removed_count += 1
            continue
        if valid:
            filtered.append(item)
        else:
            removed_count += 1

    # Write the filtered list back to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    print(f"Total items: {len(data)}, Retained items: {len(filtered)}, Removed items: {removed_count}")


if __name__ == '__main__':

    in_path, out_path = "Syn_Ultimate.json", "Syn_Ultimate_clean.json"
    filter_json(in_path, out_path)