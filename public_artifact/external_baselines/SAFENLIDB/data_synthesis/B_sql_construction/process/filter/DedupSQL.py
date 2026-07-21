# Remove duplicate SQL statements under the same id

import json
import os


def remove_duplicate_sql(data):
    """Remove duplicate SQL statements under the same id"""
    # Create a dictionary to store unique SQL for each id
    id_sql_map = {}

    for item in data:
        item_id = item.get("id")
        if not item_id or "extracted_sql" not in item:
            continue

        # Convert the SQL list to a tuple to use as a dictionary key
        sql_tuple = tuple(item["extracted_sql"])

        if item_id not in id_sql_map:
            id_sql_map[item_id] = {sql_tuple: item}
        else:
            # If this SQL combination already exists, skip it
            if sql_tuple in id_sql_map[item_id]:
                continue
            # Otherwise add this new SQL combination
            id_sql_map[item_id][sql_tuple] = item

    # Recombine the deduplicated data into a list
    deduplicated_data = []
    for id_dict in id_sql_map.values():
        deduplicated_data.extend(id_dict.values())

    return deduplicated_data


def main():
    # Set input and output file paths
    input_path = r"U_column_direct.json"
    output_path = r"U_column_direct.json"

    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} does not exist")
        return

    # Read input file
    try:
        with open(input_path, 'r', encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取输入文件时出错: {e}")
        return

    # Record original data item count
    original_count = len(data)
    print(f"Original data item count: {original_count}")

    # Remove duplicate SQL
    deduplicated_data = remove_duplicate_sql(data)
    deduped_count = len(deduplicated_data)
    print(f"Deduplicated data item count: {deduped_count}")
    print(f"Removed {original_count - deduped_count} duplicate items")

    # Save deduplicated results
    try:
        with open(output_path, 'w', encoding="utf-8") as f:
            json.dump(deduplicated_data, f, indent=2, ensure_ascii=False)
        print(f"Deduplicated data saved to: {output_path}")
    except Exception as e:
        print(f"WRONG: {e}")


if __name__ == "__main__":
    main()