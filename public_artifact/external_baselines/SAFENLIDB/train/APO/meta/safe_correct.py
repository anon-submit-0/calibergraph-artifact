import os
import re
import json
import sqlite3
import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError


def extract_secure_output(secure_text):
    matches = re.findall(r'<secure_output>(.*?)</secure_output>', secure_text, re.S)
    return matches[0].strip() if matches else None
def extract_secure_cot(secure_text):
    matches = re.findall(r'<secureCOT>(.*?)</secureCOT>', secure_text, re.S)
    return matches[0].strip() if matches else None

def extract_sql_output(secure_text):
    matches = re.findall(r'<sql_COT>(.*?)</sql_COT>', secure_text, re.S)
    return matches[0].strip() if matches else None


def extract_last_sql(sql_cot):
    blocks = re.findall(r'```sql(.*?)```', sql_cot, re.S | re.IGNORECASE)
    return blocks[-1].strip() if blocks else None

import time

def execute_sql(db_file, query):
    try:
        with sqlite3.connect(db_file) as conn:
            cur = conn.cursor()
            start_time = time.time()
            timeout = 4  # Set timeout to 4 seconds

            def progress_handler():
                if time.time() - start_time > timeout:
                    return 1
                return 0

            conn.set_progress_handler(progress_handler, 1000)
            cur.execute(query)
            return cur.fetchall()
    except sqlite3.OperationalError as e:
        if 'interrupted' in str(e):
            print("Query execution timed out after 4 seconds.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def main(json1_path, json2_path, db_path, output_path=None):
    with open(json1_path, 'r', encoding='utf-8') as f:
        original = json.load(f)
    if json2_path.endswith('.jsonl'):
        with open(json2_path, 'r', encoding='utf-8') as f:
            preds = [json.loads(line) for line in f]
    else:
        with open(json2_path, 'r', encoding='utf-8') as f:
            preds = json.load(f)

    beam = 8
    if len(preds) != len(original) * beam:
        print(f"Warning: Expected {len(original)*beam} predictions, got {len(preds)}")
        return

    preference_data = []
    timeout_count = 0
    s_c = s_r = un_c = un_r = 0

    for idx, item in enumerate(original):
        correct_label = extract_secure_output(item.get('secure_cot', ''))
        if correct_label != item.get('safe_label'):
            continue
        sql_list = item.get('sql_list', [])
        correct_sql = sql_list[-1]
        db_file = os.path.join(db_path, item['db_id'], f"{item['db_id']}.sqlite")
        if not os.path.exists(db_file):
            continue

        correct_res = execute_sql(db_file, correct_sql)
        if not correct_res:
            continue

        item_preds = preds[idx*beam:(idx+1)*beam]
        chosen_list = []
        rejected_list = []

        with ThreadPoolExecutor(max_workers=1) as executor:
            for p in item_preds:
                secure_out = extract_secure_output(p.get('predict', ''))
                if not secure_out:
                    continue
                sql_text = extract_last_sql(p.get('predict', ''))
                future = executor.submit(execute_sql, db_file, sql_text)
                try:
                    pred_res = future.result(timeout=120)
                except TimeoutError:
                    timeout_count += 1
                    continue

                if correct_label == 'safe':
                    if secure_out == 'safe' and pred_res == correct_res:
                        chosen_list.append(p)
                        s_c += 1
                    elif secure_out == 'safe' and pred_res != correct_res:
                        rejected_list.append(p)
                        s_r += 1
                else:
                    if secure_out == 'unsafe' and pred_res == correct_res:
                        chosen_list.append(p)
                        un_c += 1
                    elif secure_out == 'unsafe' and pred_res != correct_res:
                        rejected_list.append(p)
                        un_r += 1

        if chosen_list and rejected_list:
            # Random pairing and replace corresponding parts in rejected with chosen's secure_cot
            random.shuffle(chosen_list)
            random.shuffle(rejected_list)
            for cp, rp in zip(chosen_list, rejected_list):
                cp_predict = cp['predict']
                rp_predict = rp['predict']
                # Extract secure_cot content from chosen
                chosen_cot = extract_secure_cot(cp_predict)
                if chosen_cot:
                    # Replace <secure_output> tag content in rp_predict with new chosen_cot
                    rp_predict = re.sub(
                        r'(<secureCOT>)(.*?)(</secureCOT>)',
                        lambda m: f"{m.group(1)}{chosen_cot}{m.group(3)}",
                        rp_predict,
                        flags=re.S
                    )
                preference_data.append({
                    "conversations": [{"from": "human", "value": cp['prompt'].replace("user\n\n", "")}],
                    "chosen": {"from": "gpt", "value": cp_predict},
                    "rejected": {"from": "gpt", "value": rp_predict},
                    "label": correct_label
                })
                print("------------------------------")
                print(cp_predict)
                print(rp_predict)

    # Downsample to balance labels
    safe_pairs = [p for p in preference_data if p['label'] == 'safe']
    unsafe_pairs = [p for p in preference_data if p['label'] == 'unsafe']
    min_count = min(len(safe_pairs), len(unsafe_pairs))
    balanced_data = random.sample(safe_pairs, min_count) + random.sample(unsafe_pairs, min_count)
    random.shuffle(balanced_data)

    print(f"Size after downsampling: {len(balanced_data)}")
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as outf:
            json.dump(balanced_data, outf, ensure_ascii=False, indent=2)
            print(f"Preference data saved to {output_path}")
    else:
        print(json.dumps(balanced_data, ensure_ascii=False, indent=2))

    print(f"Total timeouts: {timeout_count}, safe_correct: {s_c}, safe_reject: {s_r}, unsafe_correct: {un_c}, unsafe_reject: {un_r}")
    # Print timeout statistics
    print(f"Total timeouts (skipped preds over 4s): {timeout_count}")
    print(s_c)
    print(s_r)
    print(un_c)
    print(un_r)


if __name__ == '__main__':
    json1_path = r"Cut_down2.json"
    json2_path = r"k_8.jsonl"
    db_path = r"databases"
    out = r"DPO_2.json"
    main(json1_path, json2_path, db_path, out)
