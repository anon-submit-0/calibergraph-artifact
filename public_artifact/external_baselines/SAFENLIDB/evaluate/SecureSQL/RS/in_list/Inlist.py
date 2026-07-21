import os
import json
import sqlite3
from typing import List, Dict, Any

# ===== Configuration: Modify paths directly here =====
JSON_PATH    = 'dev.json'    # Path to dev.json
JSON3_PATH   = 'db_id.json'  # Path to the third JSON file
DB_ROOT      = 'merge_data/database'  # Root directory of database files
OUTPUT_DIR   = 'output_results'         # Output results directory
DEBUG        = True                     # Whether to print debug information


def process_sql_statements(
    items: List[Dict[str, Any]],
    db_root: str
) -> Dict[str, List[Dict[str, Any]]]:
    non_empty, empty, failed = [], [], []
    for idx, item in enumerate(items):
        db_id   = item.get('db_id')
        sql_list = item.get('queries') or item.get('sql_list') or []
        if not db_id or not sql_list:
            failed.append({'item_index': idx, 'db_id': db_id, 'sql': None,
                           'error': 'Missing db_id or empty sql_list'})
            continue
        # Locate database file
        c1 = os.path.join(db_root, f"{db_id}.sqlite")
        c2 = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if os.path.isfile(c1): db_file = c1
        elif os.path.isfile(c2): db_file = c2
        else:
            failed.append({'item_index': idx, 'db_id': db_id, 'sql': None,
                           'error': f'DB file not found (tried {c1} & {c2})'})
            continue
        conn = sqlite3.connect(db_file)
        cur  = conn.cursor()
        for sql in sql_list:
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                if rows:
                    non_empty.append({'item_index': idx, 'db_id': db_id, 'sql': sql, 'result': rows})
                else:
                    empty.append({'item_index': idx, 'db_id': db_id, 'sql': sql})
            except Exception as e:
                failed.append({'item_index': idx, 'db_id': db_id, 'sql': sql, 'error': str(e)})
        conn.close()
    if DEBUG:
        print(f"[DEBUG] Processed {len(items)} items -> non_empty={len(non_empty)}, empty={len(empty)}, failed={len(failed)}")
    return {'non_empty': non_empty, 'empty': empty, 'failed': failed}


def get_unique_db_ids(json3_path: str) -> List[str]:
    with open(json3_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    seen, uniq = set(), []
    for item in items:
        db_id = item.get('db_id')
        if db_id and db_id not in seen:
            seen.add(db_id)
            uniq.append(db_id)
    if DEBUG:
        print(f"[DEBUG] Unique db_ids from json3: {len(uniq)}")
    return uniq


def filter_safe_last_nonempty(
    items: List[Dict[str, Any]],
    db_root: str
) -> List[Dict[str, Any]]:
    filtered = []
    for idx, item in enumerate(items):
        label = item.get('label', '').lower()
        sql_list = item.get('queries') or item.get('sql_list') or []
        if label in ('sa', 'su', 'safe') and sql_list:
            last_sql = sql_list[-1]
            db_id = item.get('db_id')
            c1 = os.path.join(db_root, f"{db_id}.sqlite")
            c2 = os.path.join(db_root, db_id, f"{db_id}.sqlite")
            db_file = c1 if os.path.isfile(c1) else c2 if os.path.isfile(c2) else None
            if not db_file:
                continue
            conn = sqlite3.connect(db_file)
            cur  = conn.cursor()
            try:
                cur.execute(last_sql)
                rows = cur.fetchall()
                if rows:
                    # Add original index information
                    new_item = dict(item)
                    new_item['item_index'] = idx
                    filtered.append(new_item)
            except Exception:
                pass
            conn.close()
    if DEBUG:
        print(f"[DEBUG] filter_safe_last_nonempty: {len(filtered)} items")
    return filtered


def extract_and_save(
    item_list: List[Dict[str, Any]],
    sql_path: str,
    diff_json_path: str
) -> None:
    with open(sql_path, 'w', encoding='utf-8') as f_sql:
        for item in item_list:
            sql_list = item.get('queries') or item.get('sql_list') or []
            if not sql_list:
                continue
            last_sql = sql_list[-1].strip().strip('"').strip("'")
            f_sql.write(last_sql + '\n')
    diffs = [{'difficulty': 'simple'} for _ in range(len(item_list))]
    with open(diff_json_path, 'w', encoding='utf-8') as f_diff:
        json.dump(diffs, f_diff, ensure_ascii=False, indent=2)
    if DEBUG:
        print(f"[DEBUG] Saved {len(item_list)} SQLs to {sql_path}")
        print(f"[DEBUG] Saved difficulties to {diff_json_path}")


def main():
    # 1. Read dev.json
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        dev_items = json.load(f)

    # 2. Extract unique db_id list from json3
    unique_db_ids = get_unique_db_ids(JSON3_PATH)

    # 3. Filter safe items where last SQL execution is non-empty, return with item_index
    safe_items = filter_safe_last_nonempty(dev_items, DB_ROOT)

    # 4. Divide into in_list and out_list based on unique_db_ids
    in_list, out_list = [], []
    for item in safe_items:
        (in_list if item['db_id'] in unique_db_ids else out_list).append(item)
    if DEBUG:
        print(f"[DEBUG] in_list={len(in_list)}, out_list={len(out_list)}")

    # 5. Save temporary JSON lists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, 'in_list.json'), 'w', encoding='utf-8') as f:
        json.dump(in_list, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, 'out_list.json'), 'w', encoding='utf-8') as f:
        json.dump(out_list, f, ensure_ascii=False, indent=2)

    # 6. Extract and save SQL and difficulty
    extract_and_save(in_list,
                     os.path.join(OUTPUT_DIR, 'gold_bird.sql'),
                     os.path.join(OUTPUT_DIR, 'gold_bird_diff.json'))
    extract_and_save(out_list,
                     os.path.join(OUTPUT_DIR, 'other_bird.sql'),
                     os.path.join(OUTPUT_DIR, 'other_bird_diff.json'))

    # 7. Save gold_bird positions in dev.json
    positions = [item['item_index'] for item in in_list]
    with open(os.path.join(OUTPUT_DIR, 'gold_bird_positions.json'), 'w', encoding='utf-8') as f_pos:
        json.dump(positions, f_pos, ensure_ascii=False, indent=2)
    if DEBUG:
        print(f"[DEBUG] Saved gold bird positions ({len(positions)}): {positions}")

if __name__ == '__main__':
    main()
