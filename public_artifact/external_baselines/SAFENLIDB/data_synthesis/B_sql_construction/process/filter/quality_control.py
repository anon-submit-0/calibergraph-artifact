# Filter SQL statements that do not contain specific_column

import json
import re
import os


def extract_column_names(specific_column):
    """Extract column names from specific_column, excluding table names and content inside parentheses"""
    # Use regex to match pattern table.column(type)
    matches = re.findall(r'\b\w+\.(?P<column>\w+)\s*\([^)]*\)', specific_column)
    return matches


def check_sql_contains_any_column(extracted_sql, column_names):
    """Check if all SQL statements as a whole contain any specified column names"""
    # Concatenate all SQL statements into one string
    all_sql_text = ""
    for i in range(len(extracted_sql)):
        all_sql_text += extracted_sql[i]
    # Check if the concatenated text contains any specified column names
    correct = 0
    for column_name in column_names:
        if column_name in all_sql_text:
            correct+=1
        else:
            continue
    if correct == len(column_names):
        return True
    return False


def main():
    # Set input and output file paths
    input_path = r"column_infer.json"
    output_path = r"U_cells_infer.json"
    error_path = r"output_errors2.json"

    # Read input file
    with open(input_path, 'r', encoding="utf-8") as f:
        data = json.load(f)

    # Filter SQL statements
    total_items_count = len(data)
    removed_items_count = 0
    filtered_data = []
    error_data = []

    for item in data:
        if "extracted_sql" in item and "specific_column" in item:
            column_names = extract_column_names(item["specific_column"])
            print(column_names)


            if check_sql_contains_any_column(item["extracted_sql"], column_names):
                filtered_data.append(item)
            else:
                error_data.append(item)
                removed_items_count += 1
        else:
            error_data.append(item)
            removed_items_count += 1

    # Save filtered results
    with open(output_path, 'w', encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    # Save error data
    with open(error_path, 'w', encoding="utf-8") as f:
        json.dump(error_data, f, indent=2, ensure_ascii=False)

    print(f"Processing complete! Total items processed: {total_items_count}")
    print(f"Total removed items: {removed_items_count} (all SQL statements do not contain specified columns)")
    print(f"Items retained: {len(filtered_data)}")
    print(f"Results saved to: {output_path}")
    print(f"Error data saved to: {error_path}")


if __name__ == "__main__":
    main()