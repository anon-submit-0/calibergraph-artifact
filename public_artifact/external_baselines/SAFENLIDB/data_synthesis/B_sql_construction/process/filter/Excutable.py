# Filter SQL statements that do not contain specific_column

import json
import re
import os
import sqlite3


def extract_column_names(specific_column):
    # Use regex to match pattern table.column(type)
    matches = re.findall(r'\b\w+\.(?P<column>\w+)\s*\([^)]*\)', specific_column)
    return matches


def get_db_path(db_id):
    """Get database file path based on database ID"""
    possible_paths = [
        f"databases\\{db_id}\\{db_id}.sqlite"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def check_sql_executable(db_id, sql_text):
    """Check if SQL statement can be executed in the database"""
    db_path = get_db_path(db_id)
    if not db_path:
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN")
        cursor.execute(sql_text)
        cursor.execute("ROLLBACK")
        return True
    except Exception as e:
        error_msg = str(e)
        # Dynamically identify error types
        if "no such table" in error_msg.lower():
            error_type = "TABLE_NOT_EXIST"
        elif "no such column" in error_msg.lower():
            error_type = "COLUMN_NOT_EXIST"
        elif "syntax error" in error_msg.lower():
            error_type = "SYNTAX_ERROR"
        elif "incomplete input" in error_msg.lower():
            error_type = "INCOMPLETE_INPUT"
        else:
            # Extract the first part of the error message as error type
            error_parts = error_msg.split(":", 1)
            if len(error_parts) > 1 and error_parts[0].strip():
                error_type = error_parts[0].strip().upper().replace(" ", "_")
            else:
                error_type = "OTHER_ERROR"
        return {"error": error_msg, "type": error_type}
    finally:
        if 'conn' in locals() and conn:
            conn.close()


def check_sql_contains_any_column(extracted_sql, column_names, db_id=None):
    """Check if all SQL statements as a whole contain specified column names and are executable"""
    # Initialize results for two checks
    column_check_passed = False
    executable_check_passed = True
    
    # Check 1: Verify if SQL contains all specified column names
    # Concatenate all SQL statements into one string
    all_sql_text = ""
    for i in range(len(extracted_sql)):
        all_sql_text += extracted_sql[i]
    # Check if the concatenated text contains all specified column names
    correct = 0
    for column_name in column_names:
        if column_name in all_sql_text:
            correct += 1
    if correct == len(column_names):
        column_check_passed = True
    
    # Check 2: Unconditionally check if SQL is executable
    if db_id:
        for i in range(len(extracted_sql)):
            sql_result = check_sql_executable(db_id, extracted_sql[i])
            if sql_result is not True:
                # If any SQL is not executable, execution check fails
                executable_check_passed = False
                # Print non-executable SQL statements
                for i in range(len(extracted_sql)):
                    print(extracted_sql[i])
                break
    
    # Return True only if both column check and execution check pass
    if column_check_passed and executable_check_passed:
        return True
    else:
        # Return error info if execution check fails and error info exists
        if not executable_check_passed and isinstance(sql_result, dict):
            return sql_result
        return False


def main():
    # Set input and output file paths
    input_path = r"Infer_column.json"
    output_path = r"U_cells_vio.json"
    error_path = r"output_errors2.json"

    # Initialize error statistics - use dictionary default for dynamic error types
    error_stats = {}

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

            # Check if all SQL statements as a whole contain any specified column names and verify executability
            db_id = item.get("db_id")
            result = check_sql_contains_any_column(item["extracted_sql"], column_names, db_id)
            if result is True:
                # If contains, keep the entire data item
                filtered_data.append(item)
            else:
                # If not, add to error data list
                if isinstance(result, dict) and "type" in result:
                    error_type = result["type"]

                    if error_type not in error_stats:
                        error_stats[error_type] = 0
                    error_stats[error_type] += 1
                    item["error_info"] = result
                error_data.append(item)
                removed_items_count += 1
        else:
            # If item lacks extracted_sql or specific_column field, add to error data
            error_data.append(item)
            removed_items_count += 1

    # Save filtered results
    with open(output_path, 'w', encoding="utf-8") as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    # Save error data
    with open(error_path, 'w', encoding="utf-8") as f:
        json.dump(error_data, f, indent=2, ensure_ascii=False)

    print(f"Processing complete! Total items processed: {total_items_count}")
    print(f"Total removed items: {removed_items_count} (at least one SQL statement is not executable)")
    print(f"Items retained: {len(filtered_data)}")
    print(f"Results saved to: {output_path}")
    print(f"Error data saved to: {error_path}")
    print("\nError type statistics:")
    for error_type, count in error_stats.items():
        print(f"{error_type}: {count}")


if __name__ == "__main__":
    main()