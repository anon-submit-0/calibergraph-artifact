import json
import random
import re

from ipykernel.kernelapp import launch_new_instance


def parse_columns(spec_col_str):
    # Remove enclosing brackets and split by comma
    cols = spec_col_str.strip().lstrip('[').rstrip(']').split(',')
    col_names = []
    for col in cols:
        col = col.strip()
        # Extract the part before '(' if present
        name = col.split('(')[0].strip()
        if name:
            col_names.append(name)
    return col_names


def generate_safe_entries(
    json_original_path,
    json1_path,
    json3_path,
    output_path,
    entries_per_length=1500,
    seed=42
):
    random.seed(seed)

    # Load files
    with open(json_original_path, 'r', encoding='utf-8') as f:
        original = json.load(f)
    with open(json1_path, 'r', encoding='utf-8') as f:
        safe_defs = json.load(f)
    with open(json3_path, 'r', encoding='utf-8') as f:
        id_map = json.load(f)

    # Build safe definition lookup by db_id (take first if multiple)
    safe_by_db = {entry['db_id']: entry for entry in safe_defs}

    # Group original entries by db_id, filtering out SQLs containing any sensitive column
    sql_entries = {}
    for item in original:
        db = item.get('db_id')
        if db not in safe_by_db:
            continue
        spec_cols = parse_columns(safe_by_db[db]['specific_column'])
        sql = item.get('sql') or item.get('sql_list')
        # ensure single string sql
        if isinstance(sql, list):
            # flatten lists if present
            sqls = sql
            for sql in sqls:
                pass
        sql = sql if isinstance(sql, str) else ''
        # Skip if contains any sensitive column name
        if any(col in sql for col in spec_cols):
            continue
        # Append entry
        sql_entries.setdefault(db, []).append({
            'sql': sql,
            'question': item.get('question', ''),
            'cot': item.get('cot', '')
        })

    # Prepare new entries
    new_entries = []
    lengths = [1, 2, 3]
    for length in lengths:
        valid_dbs = [db for db, items in sql_entries.items() if len(items) >= length]
        if not valid_dbs:
            raise ValueError(f"No db_ids with at least {length} safe SQL entries.")
        for _ in range(entries_per_length):
            db = random.choice(valid_dbs)
            items = random.sample(sql_entries[db], length)
            id__ = -1
            for i in range(len(id_map)):
                if id_map[i] == db:
                    id__ = i
                    break
            if id__ == -1:
                print(f"Warning: No corresponding data for the item, skipped")
                continue

            # Build the new item
            entry = {
                'id': id__,
                'db_id': db,
                'safe_condition': safe_by_db[db]['safe_condition'],
                'specific_value': safe_by_db[db].get('specific_value', ''),
                'specific_column': safe_by_db[db]['specific_column'],
                'safe_label': 'safe',
                'sql_list': [it['sql'] for it in items],
                'questions': [it['question'] for it in items],
                'cot_content': '',
                'SQL_COT': [it['cot'] for it in items],
                'label': 'safe'
            }
            run = 0
            for question in entry['questions']:
                if "**Assistant**" in question:
                    run = 1
                    break
            if run == 1:
                print("Warning: Item contains **Assistant**, skipped")
                continue
            new_entries.append(entry)

    # Merge with original dataset
    merged = safe_defs+new_entries
    print(f"Merged {len(new_entries)} new safe entries with original dataset.")
    print(len(merged))

    # Write out
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(new_entries)} new safe entries and merged. Output written to {output_path}")


if __name__ == '__main__':
    generate_safe_entries(
        'selected_data.json',
        'U_put11.json',
        'db_ids.json',
        'merged_output.json'
    )
