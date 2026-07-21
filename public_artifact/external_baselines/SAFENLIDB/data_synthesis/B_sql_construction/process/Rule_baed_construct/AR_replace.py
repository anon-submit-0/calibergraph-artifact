import json
import re


def extract_column_names(specific_column):
    matches = re.findall(r'\b\w+\.(?P<column>\w+)\s*\([^)]*\)', specific_column)
    return matches


def main():

    json1_path = r'U_column_infer.json'
    json2_path = r'selected_data.json'
    output_path = 'path_to_output.json'


    with open(json1_path, 'r', encoding='utf-8') as f:
        json1_data = json.load(f)

    with open(json2_path, 'r', encoding='utf-8') as f:
        json2_data = json.load(f)

    result = []

    for item1 in json1_data:
        item_id = item1.get('id')
        specific_column = item1.get('specific_column', '')
        extracted_sql = item1.get('extracted_sql', [])

        column_names = extract_column_names(specific_column)

        for item2 in json2_data:
            if item2.get('id') == item_id:
                exout_sql = item2.get('extracted_sql', '')

                if not any(column in exout_sql for column in column_names):

                    valid_sqls = [sql for sql in extracted_sql if len(sql) >= 2]
                    for i in range(len(valid_sqls)):
                        if i ==0:
                            vaa = [valid_sqls[0]]
                            vaa.append(exout_sql)
                        else:
                            vaa.append(valid_sqls[i])



                    new_item = {
                        "id": item_id,
                        "db_id": item1.get('db_id'),
                        "safe_condition": item1.get('safe_condition'),
                        "specific_column": specific_column,
                        "specific_value": item1.get('specific_value'),
                        "extracted_sql": vaa
                    }


                    result.append(new_item)
                    break
                break
        continue

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)




if __name__ == "__main__":
    main()