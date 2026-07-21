import json
import os


def extract_db_ids_json(tables_json_path, output_path, limit=2000):
    """Extract database IDs from tables.json and save them as a JSON list to a file, with a limit on the number of entries"""
    # Read the tables.json file
    try:
        with open(tables_json_path, 'r', encoding='utf-8') as f:
            tables_data = json.load(f)
    except Exception as e:
        print(f"Error reading input file: {e}")
        return False

    # If a limit is set, only process the specified number of databases
    if limit and limit > 0:
        tables_data = tables_data[:limit]
        print(f"Note: Only processing the first {limit} databases")

    db_ids = []

    # Iterate over each database and extract the db_id
    for db_info in tables_data:
        # Get the database ID
        db_id = db_info.get('db_id', '')
        if db_id:
            db_ids.append(db_id)
            print(f"Extracted database ID: {db_id}")
        else:
            print(f"Warning: Found a database entry without a db_id")

    # Write to output file (JSON format)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write the entire list to the file in JSON format
            json.dump(db_ids, f, ensure_ascii=False, indent=2)
        print(f"Extracted a total of {len(db_ids)} database IDs")
        print(f"Conversion complete, output file: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"Error writing to output file: {e}")
        return False


if __name__ == "__main__":
    # Set input and output file paths
    tables_json_path = "tables.json"
    output_path = "db_ids.json"

    # Check if input file exists
    if not os.path.exists(tables_json_path):
        print(f"Error: Input file {tables_json_path} does not exist")
    else:
        # Execute extraction with default limit of 2000 entries
        extract_db_ids_json(tables_json_path, output_path)