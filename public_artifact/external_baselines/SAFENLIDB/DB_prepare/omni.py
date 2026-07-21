import json
import os
import sqlite3


def get_db_path(db_id):
    """Get database file path by database ID"""
    # Try several possible paths
    possible_paths = [
        f"databases\\{db_id}\\{db_id}.sqlite"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def query_example_values(db_path, table_name, column_name, limit=4):
    """Query example values for specified table and column"""
    if not db_path or not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Try to query distinct values of the column, limited to 'limit' number
        try:
            cursor.execute(
                f"SELECT DISTINCT \"{column_name}\" FROM \"{table_name}\" WHERE \"{column_name}\" IS NOT NULL LIMIT 10")
            values = list({str(row[0]) for row in cursor.fetchall()})

            if len(values) >= 3:
                return values[:3]
            elif len(values) == 2:
                return values[:2]
            elif len(values) == 1:
                return values[:1]
            return []
        except sqlite3.OperationalError:
            # Return default value if query fails
            return []
    except Exception as e:
        print(f"Error querying database: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()


def convert_tables_to_all_with_column(tables_json_path, output_path, limit=None):
    # Read tables.json file
    with open(tables_json_path, 'r', encoding='utf-8') as f:
        tables_data = json.load(f)

    # If a limit is set, only process the specified number of databases
    if limit and limit > 0:
        tables_data = tables_data[:limit]
        print(f"Note: Only processing the first {limit} databases")

    all_with_column_data = []

    # Iterate over each database
    for db_info in tables_data:
        # Get database ID
        db_id = db_info.get('db_id', '')

        # Get database file path
        db_path = get_db_path(db_id)
        if db_path:
            print(f"Found database: {db_id} path: {db_path}")
        else:
            print(f"Database not found: {db_id}, using default example value")

        # Get table information
        table_names = db_info.get('table_names_original', [])
        column_names = db_info.get('column_names_original', [])
        column_types = db_info.get('column_types', [])

        # Get primary key information
        primary_keys = db_info.get('primary_keys', [])

        # Get foreign key information
        foreign_keys = db_info.get('foreign_keys', [])

        # Build database schema description
        schema_desc = ""

        # Process each table
        for table_idx, table_name in enumerate(table_names):
            schema_desc += f"table {table_name} , columns = [ "

            # Find all columns belonging to the table
            table_columns = []
            column_counter = 0  # New column counter
            for col_idx, (tab_idx, col_name) in enumerate(column_names):
                if tab_idx == table_idx:
                    # Get original column name and type
                    col_type = column_types[col_idx].lower() if col_idx < len(column_types) else "text"
                    col_type = col_type.replace('integer', 'int')
                    # Check if it is a primary key
                    is_primary = col_idx in primary_keys
                    primary_key_str = " | primary key" if is_primary else ""
                    col_desc = f"{table_name}.{col_name} ( {col_type}{primary_key_str} )"
                    table_columns.append(col_desc)
                    # Stop processing when 6 valid columns are reached
                    if column_counter >= 6:
                        break
                    column_counter += 1  # Increment counter

            # Add column to table description
            schema_desc += ", ".join(table_columns) + " ]\n"

        # Add foreign key information
        if foreign_keys:
            schema_desc += "foreign keys :\n"
            for fk in foreign_keys:
                # Get foreign key column and referenced column information
                fk_col_idx = fk[0]
                ref_col_idx = fk[1]

                if fk_col_idx < len(column_names) and ref_col_idx < len(column_names):
                    fk_tab_idx, fk_col_name = column_names[fk_col_idx]
                    ref_tab_idx, ref_col_name = column_names[ref_col_idx]

                    if fk_tab_idx < len(table_names) and ref_tab_idx < len(table_names):
                        fk_tab_name = table_names[fk_tab_idx]
                        ref_tab_name = table_names[ref_tab_idx]

                        schema_desc += f"{fk_tab_name}.{fk_col_name} = {ref_tab_name}.{ref_col_name}\n"
        else:
            schema_desc += "foreign keys : None\n"

        # Add database schema to results
        all_with_column_data.append(schema_desc)

    # Write to output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_with_column_data, f, ensure_ascii=False, indent=2)

    print(f"Conversion complete, output file: {os.path.basename(output_path)}")


if __name__ == "__main__":
    # Set input and output file paths
    tables_json_path = "tables.json"
    output_path = "omni_2000.json"

    # Check if input file exists
    if not os.path.exists(tables_json_path):
        print(f"Error: Input file {tables_json_path} does not exist")
    else:
        # Execute conversion, only process first 10 databases
        convert_tables_to_all_with_column(tables_json_path, output_path, limit=2000)